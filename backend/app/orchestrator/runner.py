from datetime import datetime

from app.models.execution import InsightExecution
from app.orchestrator.state import State
from app.orchestrator.errors import (
    RecoverableError,
    FatalError,
    CancelledError,
)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.analytics.trends import build_trends_report
from app.rag.retriever import retrieve_context
from app.llm.client import generate_explanation
from app.insights.validator import validate_explanation

from app.orchestrator.hashing import (
    build_source_hash,
    find_reusable_execution,
)

class InsightRunner:

    PIPELINE_VERSION = "3.0"
    PROMPT_VERSION = "1.0"
    
    def _build_prompt(self, metrics: dict, rag: list) -> str:
        return f"""
            You are a financial insight system.

            Metrics:
            {metrics}

            Context:
            {rag}

            Rules:
            - Do not invent numbers
            - Do not give advice
            - Only explain facts

            Write a concise explanation.
        """

    async def run(self, db: AsyncSession, user_id: int, insight_type: str):
        # -------------------------------------------------
        # STEP 1 — PRECOMPUTE ANALYTICS FOR HASH
        # -------------------------------------------------
        metrics = await build_trends_report(db, user_id)

        source_hash = await build_source_hash(
            db=db,
            user_id=user_id,
            insight_type=insight_type,
            pipeline_version=self.PIPELINE_VERSION,
            prompt_version=self.PROMPT_VERSION,
            model_version="phi3:mini",
            embedding_version="v1",
        )

        # -------------------------------------------------
        # STEP 2 — REUSE CHECK
        # -------------------------------------------------
        reusable = await find_reusable_execution(
            db, user_id, insight_type, source_hash
        )

        if reusable:
            return reusable, {
                "metrics": reusable.analytics_snapshot,
                "explanation": reusable.llm_output,
                "cached": True,
            }

        # -------------------------------------------------
        # STEP 3 — CREATE NEW EXECUTION
        # -------------------------------------------------
        execution = await self._acquire_lock(db, user_id, insight_type, source_hash)
        if execution is None:
            raise RuntimeError("Execution lock acquisition failed")

        execution.source_hash = source_hash
        execution.model_version = "phi3:mini"
        execution.embedding_version = "v1"
        execution.analytics_snapshot = metrics

        # 🔴 CRITICAL — make execution visible to polling clients
        await db.commit()
        await db.refresh(execution)

        await self._set_state(db, execution, State.RUNNING)
        await db.commit()

        try:
            # ---------------- RAG ----------------
            rag_context = await retrieve_context(
                query=str(metrics),
                user_id=user_id
            )
            execution.rag_snapshot = rag_context  # Store as list

            # ---------------- PROMPT ----------------
            prompt = self._build_prompt(metrics, rag_context)
            execution.prompt_snapshot = prompt

            # ---------------- LLM ----------------
            llm_output = await generate_explanation(prompt)
            execution.llm_output = llm_output

            # ---------------- VALIDATION ----------------
            # ✅ PASS RAG TEXT TO VALIDATOR
            # 🔹 COMBINE RAG CHUNKS INTO SINGLE STRING FOR VALIDATION
            rag_text = "\n".join(rag_context) if rag_context else ""
            if not validate_explanation(llm_output, metrics, rag_text=rag_text):
                execution.step_failed = "validation"
                raise RecoverableError("Validation failed")

            final = {
                "metrics": metrics,
                "explanation": llm_output,
                "rag_context": rag_context,  # ✅ Include RAG in response
            }

            await self._set_state(db, execution, State.SUCCESS)
            return execution, final

        except RecoverableError:
            execution.step_failed = "validation"
            await self._fallback(db, execution)

            return execution, {
                "metrics": metrics,
                "explanation": "Insight failed validation",
                "fallback": True,
            }

        except Exception as e:
            execution.step_failed = "unknown"
            await self._fail(db, execution, e)

            return execution, {
                "error": str(e),
                "failed": True
            }


    # ---------------- INTERNALS ---------------- #

    async def _acquire_lock(self, db: AsyncSession, user_id: int, insight_type: str, source_hash: str):
        # 1️⃣ Check existing ACTIVE execution
        stmt_active = select(InsightExecution).where(
            InsightExecution.user_id == user_id,
            InsightExecution.insight_type == insight_type,
            InsightExecution.source_hash == source_hash,
            InsightExecution.status.in_([State.PENDING, State.RUNNING, State.LOCKED])
        )

        result = await db.execute(stmt_active)
        active = result.scalar_one_or_none()

        if active:
            return active

        # 2️⃣ Check cached SUCCESS execution
        stmt_success = select(InsightExecution).where(
            InsightExecution.user_id == user_id,
            InsightExecution.insight_type == insight_type,
            InsightExecution.source_hash == source_hash,
            InsightExecution.status == State.SUCCESS
        ).order_by(InsightExecution.completed_at.desc())

        result = await db.execute(stmt_success)
        cached = result.scalar_one_or_none()

        if cached:
            return cached

        # 3️⃣ Create new execution
        execution = InsightExecution(
            user_id=user_id,
            insight_type=insight_type,
            source_hash=source_hash,
            pipeline_version=self.PIPELINE_VERSION,
            prompt_template_version=self.PROMPT_VERSION,
            status=State.LOCKED,
            started_at=datetime.utcnow(),
        )

        try:
            db.add(execution)
            await db.commit()
            await db.refresh(execution)
            return execution

        except IntegrityError:
            await db.rollback()
            retry = await db.execute(stmt_active)
            return retry.scalar_one()


    async def _set_state(self, db, execution, state):
        execution.status = state
        await db.commit()
        await db.refresh(execution)


    async def _cancel(self, db, execution):
        execution.status = State.CANCELLED
        execution.completed_at = datetime.utcnow()
        await db.commit()


    async def _fallback(self, db, execution):
        execution.status = State.FALLBACK
        execution.completed_at = datetime.utcnow()
        await db.commit()


    async def _fail(self, db, execution, error):
        execution.status = State.FAILED
        execution.error_message = str(error)
        execution.completed_at = datetime.utcnow()
        await db.commit()
from datetime import datetime, timedelta
import logging

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
from app.validation.diagnostic import build_validation_report
from app.validation.decision import decide, explain_decision, ExecutionDecision
from app.insights.artifact_service import create_artifact_from_execution

from app.orchestrator.hashing import (
    build_source_hash,
    find_reusable_execution,
)

logger = logging.getLogger(__name__)

MAX_EXECUTION_TIME_SECONDS = 120


class InsightRunner:

    PIPELINE_VERSION = "3.0"
    PROMPT_VERSION = "1.1"

    # =====================================================
    # HELPER METHODS
    # =====================================================

    def _is_stale(self, execution: InsightExecution) -> bool:
        """
        Detect if an execution has been running too long (zombie).
        
        Returns True if:
        - Status is active (pending/running/locked)
        - AND started_at was more than MAX_EXECUTION_TIME ago
        """
        if not execution.started_at:
            return False
        
        now = datetime.utcnow()
        elapsed = now - execution.started_at
        
        return elapsed.total_seconds() > MAX_EXECUTION_TIME_SECONDS
    

    async def _mark_stale_as_failed(self, db: AsyncSession, execution: InsightExecution):
        """
        Mark a stale execution as failed so it doesn't block future requests.
        """
        execution.status = State.FAILED
        execution.error_code = "stale_execution"
        execution.error_message = f"Execution exceeded max runtime of {MAX_EXECUTION_TIME_SECONDS}s"
        execution.step_failed = "timeout"
        execution.completed_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(execution)


    def _format_categories(self, categories: list) -> str:
        """Format categories for prompt clarity."""
        return "\n".join([
            f"- {cat['category']}: {cat['total']}"
            for cat in categories
        ])
    

    def _build_prompt(self, metrics: dict, rag: list) -> str:
        """
        Build a constrained prompt that minimizes hallucination.
        Emphasizes aggregate metrics over individual transactions.
        """
        
        # Limit RAG to prevent confusion with individual transactions
        rag_text = "\n\n".join(rag[:1])[:500] if rag else "No additional context"
        
        return f"""You are generating a financial insight.

STRICT RULES:
- Write EXACTLY 2-3 sentences
- Use ONLY numbers from the "Approved Data" section below
- DO NOT add analysis beyond what the numbers show
- DO NOT mention user IDs, document entries, or data not listed
- DO NOT invent transaction amounts
- Stop after completing your explanation

Approved Data:

Rolling averages:
- 30-day: {metrics['rolling']['30_day_avg']}
- 60-day: {metrics['rolling']['60_day_avg']}
- 90-day: {metrics['rolling']['90_day_avg']}

Monthly comparison:
- Current month: {metrics['monthly']['current_month']}
- Previous month: {metrics['monthly']['previous_month']}
- Change: {metrics['monthly']['percent_change']}%

Category totals:
{self._format_categories(metrics['categories'])}

Supporting context (for reference only, do not use specific amounts):
{rag_text}

Write 2-3 sentences explaining the spending trend using ONLY the aggregate numbers above."""


    def _clean_llm_output(self, raw_output: str) -> str:
        """
        Clean LLM output to 2-3 sentences max.
        Removes separator lines and excess content.
        """
        # Remove separator lines
        if "-----" in raw_output or "---" in raw_output:
            raw_output = raw_output.split("-----")[0].split("---")[0].strip()
        
        # Limit to 3 sentences
        sentences = raw_output.split('. ')
        if len(sentences) > 3:
            return '. '.join(sentences[:3]) + '.'
        
        return raw_output


    def _build_validation_report(
        self,
        llm_output: str,
        metrics: dict,
        rag_snapshot: list
    ) -> tuple:
        """
        Build validation report and decision.
        Returns (report, decision)
        """
        rag_text = "\n".join(rag_snapshot) if rag_snapshot else ""
        report = build_validation_report(llm_output, metrics, rag_text)
        decision = decide(report)
        return report, decision


    def _build_result_dict(
        self,
        metrics: dict,
        explanation: str,
        rag_context: list,
        decision: ExecutionDecision,
        report,
        cached: bool = False
    ) -> dict:
        """
        Build standardized result dictionary with validation info.
        Eliminates duplicate result building logic.
        """
        return {
            "metrics": metrics,
            "explanation": explanation,
            "rag_context": rag_context,
            "cached": cached,
            "decision": decision.value,
            "validation": {
                "numbers_ok": report.numbers_ok,
                "forbidden_language_ok": report.forbidden_language_ok,
                "rag_supported": report.rag_supported,
                "has_content": report.has_content,
                "reasoning_quality": report.reasoning_quality,
                "classification_hint": report.classification_hint,
                "issues": report.issues,
            }
        }


    async def _try_create_artifact(
        self,
        db: AsyncSession,
        execution: InsightExecution,
        result: dict
    ):
        """
        Attempt artifact creation, log errors but don't crash.
        """
        if execution.status == State.SUCCESS:
            try:
                artifact = await create_artifact_from_execution(db, execution, result)
                if artifact:
                    logger.info(f"Artifact {artifact.id} for execution {execution.id}")
            except Exception as e:
                logger.error(f"Artifact creation failed for execution {execution.id}: {e}")


    # =====================================================
    # MAIN EXECUTION PIPELINE
    # =====================================================

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
        
        logger.info(f"Computed source_hash: {source_hash}")

        # -------------------------------------------------
        # STEP 2 — REUSE CHECK
        # -------------------------------------------------
        reusable = await find_reusable_execution(
            db, user_id, insight_type, source_hash
        )

        if reusable:
            logger.info(f"Reusing execution {reusable.id} (status: {reusable.status})")
            
            # Rebuild validation for cached execution
            report, decision = self._build_validation_report(
                reusable.llm_output,
                reusable.analytics_snapshot,
                reusable.rag_snapshot or []
            )

            # Build standardized result
            result = self._build_result_dict(
                metrics=reusable.analytics_snapshot,
                explanation=reusable.llm_output,
                rag_context=reusable.rag_snapshot or [],
                decision=decision,
                report=report,
                cached=True
            )

            # Try artifact creation/lookup
            await self._try_create_artifact(db, reusable, result)
            
            return reusable, result

        logger.info(f"No reusable execution found for hash {source_hash}")

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
            execution.rag_snapshot = rag_context

            # ---------------- PROMPT ----------------
            prompt = self._build_prompt(metrics, rag_context)
            execution.prompt_snapshot = prompt

            # ---------------- LLM ----------------
            llm_raw = await generate_explanation(prompt)
            llm_output = self._clean_llm_output(llm_raw)
            execution.llm_output = llm_output

            # ---------------- VALIDATION ----------------
            report, decision = self._build_validation_report(
                llm_output,
                metrics,
                rag_context or []
            )
            
            decision_explanation = explain_decision(report, decision)
            logger.info(f"Validation decision: {decision.value} - {decision_explanation}")

            # ---------------- ACT ON DECISION ----------------
            
            if decision == ExecutionDecision.SUPPRESS:
                # Treat as failure - no explanation stored
                execution.step_failed = "validation_suppressed"
                await self._fail(db, execution, Exception(decision_explanation))
                
                return execution, {
                    "error": "Insight suppressed due to validation failure",
                    "decision": decision.value,
                    "reason": decision_explanation,
                    "failed": True
                }
            
            elif decision == ExecutionDecision.FALLBACK:
                # Store degraded insight (analytics only)
                execution.step_failed = "validation_fallback"
                await self._fallback(db, execution)
                
                return execution, {
                    "metrics": metrics,
                    "explanation": "Spending trend analysis available but explanation failed validation. See metrics for details.",
                    "fallback": True,
                    "decision": decision.value,
                    "reason": decision_explanation,
                    "validation": {
                        "numbers_ok": report.numbers_ok,
                        "forbidden_language_ok": report.forbidden_language_ok,
                        "rag_supported": report.rag_supported,
                        "has_content": report.has_content,
                        "reasoning_quality": report.reasoning_quality,
                        "classification_hint": report.classification_hint,
                        "issues": report.issues,
                    }
                }
            
            else:  # SUCCESS
                # Build final result
                final = self._build_result_dict(
                    metrics=metrics,
                    explanation=llm_output,
                    rag_context=rag_context or [],
                    decision=decision,
                    report=report,
                    cached=False
                )

                await self._set_state(db, execution, State.SUCCESS)
                
                # Try artifact creation
                await self._try_create_artifact(db, execution, final)
                
                return execution, final

        except CancelledError:
            await self._cancel(db, execution)
            raise

        except RecoverableError as e:
            # This shouldn't happen anymore (decision engine handles it)
            # But keep for backward compatibility
            execution.step_failed = "validation_legacy"
            await self._fallback(db, execution)

            return execution, {
                "metrics": metrics,
                "explanation": llm_output,
                "fallback": True,
                "reason": str(e)
            }

        except Exception as e:
            execution.step_failed = "unknown"
            await self._fail(db, execution, e)

            return execution, {
                "error": str(e),
                "failed": True
            }


    # =====================================================
    # INTERNAL STATE MANAGEMENT
    # =====================================================

    async def _acquire_lock(
        self,
        db: AsyncSession,
        user_id: int,
        insight_type: str,
        source_hash: str
    ):
        """
        Acquire execution lock with stale detection.
        Returns existing active/cached execution or creates new one.
        """
        
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
            # Check if stale (zombie detection)
            if self._is_stale(active):
                await self._mark_stale_as_failed(db, active)
                # Fall through to create new execution
            else:
                # Fresh execution — reuse it
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
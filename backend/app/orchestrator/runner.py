from datetime import datetime, UTC

from app.models.execution import InsightExecution
from app.orchestrator.state import State
from app.orchestrator.errors import (
    RecoverableError,
    FatalError,
    CancelledError,
)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


class InsightRunner:

    PIPELINE_VERSION = "3.0"
    PROMPT_VERSION = "1.0"


    async def run(self, db: AsyncSession, user_id: int, insight_type: str):
        execution = await self._acquire_lock(db, user_id, insight_type)
        if execution is None:
            raise RuntimeError("Execution lock acquisition failed")

        try:

            await self._set_state(db, execution, State.RUNNING)

            # --- PLACEHOLDERS (Milestone 3 will fill these) ---
            metrics = None
            rag_context = None
            prompt = None
            llm_output = None
            final = None
            # -----------------------------------------------

            await self._set_state(db, execution, State.SUCCESS)

            return final


        except CancelledError:

            await self._cancel(db, execution)
            raise


        except RecoverableError:

            await self._fallback(db, execution)
            return None


        except Exception as e:

            await self._fail(db, execution, e)
            raise


    # ---------------- INTERNALS ---------------- #

    async def _acquire_lock(self, db, user_id, insight_type):
        execution = InsightExecution(
            user_id=user_id,
            insight_type=insight_type,

            pipeline_version=self.PIPELINE_VERSION,
            prompt_template_version=self.PROMPT_VERSION,

            status=State.LOCKED,
            started_at=datetime.now(UTC),
        )

        try:

            db.add(execution)
            await db.commit()
            await db.refresh(execution)

            return execution

        except Exception:

            await db.rollback()

            stmt = select(InsightExecution).where(
                InsightExecution.user_id == user_id,
                InsightExecution.insight_type == insight_type,
                InsightExecution.status.in_(
                    [State.PENDING, State.RUNNING, State.LOCKED]
                )
            )

            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                return existing

            # No active execution found → retry insert
            raise RuntimeError("Failed to acquire execution lock")


    async def _set_state(self, db, execution, state):

        execution.status = state
        await db.commit()


    async def _cancel(self, db, execution):

        execution.status = State.CANCELLED
        execution.completed_at = datetime.now(UTC)
        await db.commit()


    async def _fallback(self, db, execution):

        execution.status = State.FALLBACK
        execution.completed_at = datetime.now(UTC)
        await db.commit()


    async def _fail(self, db, execution, error):

        execution.status = State.FAILED
        execution.error_message = str(error)
        execution.completed_at = datetime.now(UTC)
        await db.commit()

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.models.base import Base


class Plan(Base):
    """
    Stores a completed VaultAI V3 plan run.

    Idempotency: one row per (user_id, plan_type, source_hash).
    If a duplicate request arrives, plan_persist returns the existing
    row without recomputing — same pattern as Insight.

    Mirrors InsightExecution patterns exactly:
      - Integer PK, no UUID
      - user_id is plain Integer (no ForeignKey — same as InsightExecution)
      - JSON for structured data, Text for long strings, String(64) for hashes
    """

    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)

    # ── Identity ──────────────────────────────────────────────────────────
    user_id   = Column(Integer, nullable=False, index=True)
    plan_type = Column(String(20), nullable=False)
    # "budget" | "invest" | "goal" | "simulate" | "combined"

    # ── Idempotency fingerprint ───────────────────────────────────────────
    # sha256(user_id + plan_type + request_params + pipeline_version)
    source_hash      = Column(String(64), nullable=False)
    pipeline_version = Column(String(20), nullable=False)

    # ── Status ────────────────────────────────────────────────────────────
    status   = Column(String(20), nullable=False)  # "success" | "degraded"
    degraded = Column(Boolean, default=False, nullable=False)

    # ── Simulation outputs ────────────────────────────────────────────────
    # Written by budget_optimize / goal_simulate / sim_run — never by LLM nodes
    projected_outcomes = Column(JSON)
    assumptions        = Column(JSON)

    # ── LLM output ────────────────────────────────────────────────────────
    # explanation_filtered only — raw llm_explanation is never persisted
    explanation = Column(Text)

    # ── Execution metadata ────────────────────────────────────────────────
    graph_trace   = Column(JSON)   # ordered list of node names that ran
    audit_payload = Column(JSON)   # v2_load_metrics, degradation reasons, etc.
    confidence    = Column(JSON)   # {overall, data_coverage, assumption_risk}

    # ── Timestamps ───────────────────────────────────────────────────────
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # One success plan per (user, type, hash) — same pattern as Insight
    __table_args__ = (
        UniqueConstraint("user_id", "plan_type", "source_hash",
                         name="uq_plan_user_type_hash"),
    )
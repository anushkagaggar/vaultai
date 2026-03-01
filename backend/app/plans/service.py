"""
VaultAI V3 — plans/service.py
==============================
Database write layer called by plan_persist node in graph.py.

SESSION PATTERN
---------------
This module never creates its own session. The AsyncSession is passed in
explicitly from the route handler → state["request_params"]["_db"] →
extracted by plan_persist → forwarded here as the `db` argument.

Why: get_db() in database.py is an async generator dependency used via
Depends(get_db) in routes. The yielded session must flow through to
service.py. Creating a second session here would open a separate
transaction that knows nothing about the request lifecycle.

Flow:
    route handler
        │  db: AsyncSession = Depends(get_db)
        │  state["request_params"]["_db"] = db
        ↓
    graph.ainvoke(state)
        ↓
    plan_persist node
        │  db = state["request_params"]["_db"]
        ↓
    persist_plan(state, db)   ← this file

Author: VaultAI V3
"""

from __future__ import annotations

import hashlib
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.plan import Plan
from app.agents.State import ValidationStatus

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "3.0"


def _plan_type_str(state: dict) -> str:
    """Return plan_type as a plain string regardless of whether it's an enum or str."""
    plan_type = state.get("plan_type")
    if hasattr(plan_type, "value"):
        return plan_type.value       # PlanType.BUDGET  →  "budget"
    return str(plan_type) if plan_type is not None else ""


def compute_source_hash(state: dict) -> str:
    clean_params = {
        k: v
        for k, v in (state.get("request_params") or {}).items()
        if not k.startswith("_")
    }

    payload = json.dumps(
        {
            "user_id":          state.get("user_id"),
            "plan_type":        _plan_type_str(state),
            "request_params":   clean_params,
            "pipeline_version": PIPELINE_VERSION,
        },
        sort_keys=True,
        default=str,
    )

    return hashlib.sha256(payload.encode()).hexdigest()


def build_confidence(state: dict) -> dict:
    load_metrics  = (state.get("audit_payload") or {}).get("v2_load_metrics", {})
    days_avail    = load_metrics.get("data_days_available", 0)
    degraded      = state.get("degraded", False)
    val_status    = state.get("validation_status")

    data_coverage = {90: 1.0, 60: 0.8, 30: 0.5}.get(days_avail, 0.2)

    if val_status == ValidationStatus.PASSED:
        val_score = 1.0
    elif val_status == ValidationStatus.FAILED:
        val_score = 0.3
    else:
        val_score = 0.6

    degraded_penalty = 0.2 if degraded else 0.0
    overall = round(
        data_coverage * 0.5 + val_score * 0.3 + (0.2 - degraded_penalty), 2
    )
    overall = max(0.0, min(1.0, overall))

    return {
        "overall":         overall,
        "data_coverage":   data_coverage,
        "assumption_risk": (
            "low"    if overall >= 0.8 else
            "medium" if overall >= 0.5 else
            "high"
        ),
    }


async def persist_plan(state: dict, db: AsyncSession) -> dict:
    source_hash = compute_source_hash(state)
    confidence  = build_confidence(state)
    user_id_int = int(state.get("user_id", 0))
    plan_type   = _plan_type_str(state)   # plain string from here down, always
    val = state.get("validation_status")

    existing_audit = state.get("audit_payload") or {}
    final_audit = {
        **existing_audit,
        "source_hash":       source_hash,
        "pipeline_version":  PIPELINE_VERSION,
        "graph_trace":       state.get("graph_trace", []),
        "degraded":          state.get("degraded", False),
        "validation_status": val.value if hasattr(val, "value") else str(val),
    }

    # ── Idempotency check ─────────────────────────────────────────────────
    stmt = select(Plan).where(
        Plan.user_id     == user_id_int,
        Plan.plan_type   == plan_type,
        Plan.source_hash == source_hash,
    )
    result   = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        logger.info(
            "persist_plan: reusing plan id=%s (hash=%.12s)", existing.id, source_hash
        )
        return {
            "plan_id":       existing.id,
            "confidence":    confidence,
            "source_hash":   source_hash,
            "audit_payload": final_audit,
        }

    # ── Insert new plan ───────────────────────────────────────────────────
    plan = Plan(
        user_id            = user_id_int,
        plan_type          = plan_type,
        source_hash        = source_hash,
        pipeline_version   = PIPELINE_VERSION,
        status             = "degraded" if state.get("degraded") else "success",
        degraded           = bool(state.get("degraded", False)),
        projected_outcomes = state.get("projected_outcomes"),
        assumptions        = state.get("assumptions"),
        explanation        = state.get("explanation_filtered"),
        graph_trace        = state.get("graph_trace", []),
        audit_payload      = final_audit,
        confidence         = confidence,
    )

    try:
        db.add(plan)
        await db.commit()
        await db.refresh(plan)

    except IntegrityError:
        # Race condition: another request inserted same hash between SELECT and INSERT
        await db.rollback()
        result   = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            logger.info(
                "persist_plan: race condition resolved — reusing id=%s", existing.id
            )
            return {
                "plan_id":       existing.id,
                "confidence":    confidence,
                "source_hash":   source_hash,
                "audit_payload": final_audit,
            }
        raise   # unexpected IntegrityError — route returns 500

    logger.info(
        "persist_plan: wrote plan id=%s type=%s degraded=%s (hash=%.12s)",
        plan.id, plan.plan_type, plan.degraded, source_hash,
    )

    return {
        "plan_id":       plan.id,
        "confidence":    confidence,
        "source_hash":   source_hash,
        "audit_payload": final_audit,
    }
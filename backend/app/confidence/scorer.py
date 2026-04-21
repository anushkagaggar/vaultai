import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ConfidenceInput:
    """
    All inputs needed to compute confidence score.
    Collected from analytics snapshot + execution metadata.

    LLMOps: plan_type added as optional field with default "unknown"
    so existing calls in collector.py require zero changes.
    """
    # Transaction data
    total_transactions: int

    # Time window
    first_expense_at: Optional[datetime]
    last_expense_at: Optional[datetime]

    # Behavior signals
    current_month: float
    previous_month: float

    # Classification result
    classification: str  # "success" or "fallback"

    # LLMOps: optional — used for Prometheus label only
    plan_type: str = "unknown"


@dataclass
class ConfidenceBreakdown:
    """Full breakdown of confidence computation."""
    coverage_score: float
    window_score: float
    stability_score: float
    explanation_score: float
    final_confidence: float


# =====================================================
# SIGNAL 1: COVERAGE SCORE
# =====================================================

def compute_coverage_score(total_transactions: int) -> float:
    if total_transactions <= 0:
        return 0.0
    return 1.0 - math.exp(-total_transactions / 25.0)


# =====================================================
# SIGNAL 2: HISTORY WINDOW SCORE
# =====================================================

def compute_window_score(
    first_expense_at: Optional[datetime],
    last_expense_at: Optional[datetime]
) -> float:
    if not first_expense_at or not last_expense_at:
        return 0.0
    delta = last_expense_at - first_expense_at
    days = max(delta.days, 0)
    return 1.0 - math.exp(-days / 90.0)


# =====================================================
# SIGNAL 3: STABILITY SCORE
# =====================================================

def compute_stability_score(current_month: float, previous_month: float) -> float:
    denominator = max(abs(previous_month), 1.0)
    relative_change = abs(current_month - previous_month) / denominator
    return math.exp(-relative_change)


# =====================================================
# SIGNAL 4: EXPLANATION RELIABILITY
# =====================================================

def compute_explanation_score(classification: str) -> float:
    return {"success": 1.0, "fallback": 0.65}.get(classification.lower(), 0.0)


# =====================================================
# FINAL CONFIDENCE COMBINER
# =====================================================

def compute_confidence(inputs: ConfidenceInput) -> ConfidenceBreakdown:
    """
    Combine all signals into final confidence score.

    Weights (unchanged from original):
    0.35 × coverage | 0.25 × window | 0.25 × stability | 0.15 × explanation

    LLMOps additions (Phase 1 + Phase 3):
    - Emits a structured log event via log_confidence_scored
    - Pushes all four sub-scores to Prometheus confidence_gauge
    Both additions are wrapped in try/except so they never affect correctness.
    """
    coverage    = compute_coverage_score(inputs.total_transactions)
    window      = compute_window_score(inputs.first_expense_at, inputs.last_expense_at)
    stability   = compute_stability_score(inputs.current_month, inputs.previous_month)
    explanation = compute_explanation_score(inputs.classification)

    raw_confidence = (
        0.35 * coverage +
        0.25 * window +
        0.25 * stability +
        0.15 * explanation
    )

    final = round(min(max(raw_confidence, 0.0), 1.0), 2)

    breakdown = ConfidenceBreakdown(
        coverage_score    = round(coverage, 4),
        window_score      = round(window, 4),
        stability_score   = round(stability, 4),
        explanation_score = round(explanation, 4),
        final_confidence  = final,
    )

    plan_type = getattr(inputs, "plan_type", "unknown") or "unknown"

    # ── LLMOps Phase 1 — structured log ──────────────────────────────────
    try:
        from app.agents.ops_logger import log_confidence_scored
        log_confidence_scored(
            plan_type       = plan_type,
            overall         = final,
            data_coverage   = coverage,
            window_score    = window,
            stability_score = stability,
            rag_score       = explanation,
            degraded        = inputs.classification.lower() == "fallback",
        )
    except Exception:
        pass

    # ── LLMOps Phase 3 — Prometheus gauges ───────────────────────────────
    try:
        from app.metrics import confidence_gauge
        confidence_gauge.labels(f"{plan_type}_overall").set(final)
        confidence_gauge.labels(f"{plan_type}_coverage").set(coverage)
        confidence_gauge.labels(f"{plan_type}_window").set(window)
        confidence_gauge.labels(f"{plan_type}_stability").set(stability)
        confidence_gauge.labels(f"{plan_type}_rag").set(explanation)
    except Exception:
        pass

    return breakdown
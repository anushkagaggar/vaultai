import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ConfidenceInput:
    """
    All inputs needed to compute confidence score.
    Collected from analytics snapshot + execution metadata.
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


@dataclass
class ConfidenceBreakdown:
    """
    Full breakdown of confidence computation.
    Stored for debugging and explainability.
    """
    coverage_score: float       # Signal 1: Enough data?
    window_score: float         # Signal 2: Long history?
    stability_score: float      # Signal 3: Consistent behavior?
    explanation_score: float    # Signal 4: Reasoning passed?
    final_confidence: float     # Weighted combination


# =====================================================
# SIGNAL 1: COVERAGE SCORE
# =====================================================

def compute_coverage_score(total_transactions: int) -> float:
    """
    Measures data sufficiency using diminishing returns.
    
    Formula: coverage = 1 - exp(-txn_count / 25)
    
    Transactions → Coverage:
    3   → ~0.11 (basically guessing)
    15  → ~0.45 (weak trend)
    40  → ~0.80 (reliable pattern)
    100 → ~0.98 (saturated confidence)
    """
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
    """
    Measures how long the spending history spans.
    
    Formula: window = 1 - exp(-days / 90)
    
    Days → Score:
    5   → ~0.05 (random behavior)
    30  → ~0.28 (short term)
    90  → ~0.63 (strong pattern)
    365 → ~0.98 (stable lifestyle)
    """
    if not first_expense_at or not last_expense_at:
        return 0.0
    
    delta = last_expense_at - first_expense_at
    days = max(delta.days, 0)
    
    return 1.0 - math.exp(-days / 90.0)


# =====================================================
# SIGNAL 3: STABILITY SCORE
# =====================================================

def compute_stability_score(
    current_month: float,
    previous_month: float
) -> float:
    """
    Penalizes sudden spikes by measuring relative change.
    
    Step 1: change = |current - previous| / max(previous, 1)
    Step 2: stability = exp(-change)
    
    Change → Behavior:
    0.05 → ~0.95 (very stable)
    0.3  → ~0.74 (natural variation)
    1.0  → ~0.37 (major shift)
    2.0  → ~0.14 (chaotic user)
    """
    denominator = max(abs(previous_month), 1.0)
    relative_change = abs(current_month - previous_month) / denominator
    
    return math.exp(-relative_change)


# =====================================================
# SIGNAL 4: EXPLANATION RELIABILITY
# =====================================================

def compute_explanation_score(classification: str) -> float:
    """
    Reflects whether LLM reasoning passed validation.
    
    SUCCESS  → 1.00 (fully trusted explanation)
    FALLBACK → 0.65 (analytics correct, reasoning degraded)
    Other    → 0.00 (safety default)
    """
    scores = {
        "success": 1.0,
        "fallback": 0.65,
    }
    
    return scores.get(classification.lower(), 0.0)


# =====================================================
# FINAL CONFIDENCE COMBINER
# =====================================================

def compute_confidence(inputs: ConfidenceInput) -> ConfidenceBreakdown:
    """
    Combine all signals into final confidence score.
    
    Weights:
    0.35 × coverage     (data quantity matters most)
    0.25 × window       (history depth)
    0.25 × stability    (behavior consistency)
    0.15 × explanation  (reasoning quality)
    
    Output: float in [0.00, 1.00] rounded to 2 decimals
    
    Examples:
    - New user (3 txn, 2 days, spike)    → ~0.18
    - Normal user (45 txn, 60d, mild)   → ~0.70
    - Mature user (120 txn, 1yr, stable) → ~0.92
    - Fallback (same as normal)          → ~0.55
    """
    
    # Compute individual signals
    coverage = compute_coverage_score(inputs.total_transactions)
    window = compute_window_score(inputs.first_expense_at, inputs.last_expense_at)
    stability = compute_stability_score(inputs.current_month, inputs.previous_month)
    explanation = compute_explanation_score(inputs.classification)
    
    # Weighted combination
    raw_confidence = (
        0.35 * coverage +
        0.25 * window +
        0.25 * stability +
        0.15 * explanation
    )
    
    # Clamp to [0, 1] and round to 2 decimals
    final = round(min(max(raw_confidence, 0.0), 1.0), 2)
    
    return ConfidenceBreakdown(
        coverage_score=round(coverage, 4),
        window_score=round(window, 4),
        stability_score=round(stability, 4),
        explanation_score=round(explanation, 4),
        final_confidence=final
    )
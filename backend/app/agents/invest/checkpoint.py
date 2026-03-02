"""
VaultAI V3 — agents/invest/checkpoint.py
==========================================
Reusable checkpoint logic for the invest agent.

Mirrors the pattern of agents/budget/checkpoint.py.
Pure functions — no LangGraph state, no I/O.

PHASE 3 EXIT CRITERION (enforced here):
    allocation percentages must sum to exactly 100% within 0.01%.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

ALLOCATION_SUM_TARGET = 100.0
ALLOCATION_SUM_TOL    = 0.01   # ±0.01% — Phase 3 exit criterion


@dataclass
class InvestCheckpointResult:
    passed:     bool
    errors:     list[str] = field(default_factory=list)
    pct_sum:    float = 0.0


def run_invest_checkpoint(
    stored_outcomes: dict | None,
    constraints: dict | None,
) -> InvestCheckpointResult:
    """
    Validate the invest allocation against Phase 3 exit criteria.

    Checks:
      1. equity_pct + debt_pct + liquid_pct == 100% (within 0.01%)
      2. Stored percentages match constraints exactly
      3. total_allocated == investment_amount (within Rs.1)

    Args:
        stored_outcomes: state["projected_outcomes"]
        constraints:     state["constraints"]

    Returns:
        InvestCheckpointResult — never raises.
    """
    if stored_outcomes is None:
        return InvestCheckpointResult(
            passed=False,
            errors=["projected_outcomes is None — invest_allocate did not run"],
        )
    if constraints is None:
        return InvestCheckpointResult(
            passed=False,
            errors=["constraints is None — invest_allocate did not write constraints"],
        )

    errors: list[str] = []

    # Check 1: sum to 100%
    pct_sum = (
        float(stored_outcomes.get("equity_pct", 0)) +
        float(stored_outcomes.get("debt_pct",   0)) +
        float(stored_outcomes.get("liquid_pct", 0))
    )
    if abs(pct_sum - ALLOCATION_SUM_TARGET) > ALLOCATION_SUM_TOL:
        errors.append(
            f"PHASE3_EXIT_CRITERION: percentages sum to {pct_sum:.6f}%, "
            f"must be {ALLOCATION_SUM_TARGET}% ±{ALLOCATION_SUM_TOL}%"
        )

    # Check 2: match constraints
    for key in ("equity_pct", "debt_pct", "liquid_pct"):
        sv = float(stored_outcomes.get(key, 0))
        cv = float(constraints.get(key, 0))
        if abs(sv - cv) > ALLOCATION_SUM_TOL:
            errors.append(
                f"{key}: stored={sv:.4f}% != constraint={cv:.4f}%"
            )

    # Check 3: amounts sum to investment_amount
    amount = float(constraints.get("investment_amount", 0))
    total  = float(stored_outcomes.get("total_allocated", 0))
    if abs(total - amount) > 1.0:
        errors.append(
            f"total_allocated={total:.2f} != investment_amount={amount:.2f}"
        )

    passed = len(errors) == 0
    if passed:
        logger.info("invest_checkpoint: PASSED — sum=%.6f%%", pct_sum)
    else:
        logger.warning("invest_checkpoint: FAILED — %s", "; ".join(errors))

    return InvestCheckpointResult(passed=passed, errors=errors, pct_sum=pct_sum)
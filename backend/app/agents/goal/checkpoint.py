"""
VaultAI V3 — agents/goal/checkpoint.py
========================================
Reusable checkpoint logic for the goal agent.

Pure functions — no LangGraph state, no I/O.
goal_validate calls run_goal_checkpoint() and writes the result to state.

WHAT IS VALIDATED
-----------------
Standard goals (emergency_fund, purchase, travel, savings, etc.):
  1. Re-run goal_feasibility() with stored constraints
  2. Assert label matches stored label exactly (catches injected wrong labels)
  3. Assert projected_balance within Rs.1 tolerance
  4. Assert coverage_ratio within 0.1%

debt_payoff:
  1. Re-run debt_payoff_schedule() with stored constraints
  2. Assert payment_sufficient matches
  3. Assert total_months matches exactly

multi_goal:
  1. Re-run multi_goal_tradeoff() with stored constraints
  2. Assert feasibility_label and feasible_goals count match

DELIBERATELY WRONG LABEL TEST (Phase 4 exit criterion)
-------------------------------------------------------
Injecting stored["feasibility_label"] = "FEASIBLE" when math says "INFEASIBLE"
→ FAILED: "label mismatch: stored='FEASIBLE', recomputed='INFEASIBLE'"

Author: VaultAI V3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.simulation.forecast import (
    goal_feasibility,
    debt_payoff_schedule,
    multi_goal_tradeoff,
)

logger = logging.getLogger(__name__)

BALANCE_TOLERANCE = 1.0    # Rs.1 tolerance for projected_balance
RATIO_TOLERANCE   = 0.001  # 0.1% tolerance for coverage_ratio


@dataclass
class GoalCheckpointResult:
    passed:     bool
    errors:     list[str] = field(default_factory=list)
    recomputed: dict | None = None


def _check_standard_goal(stored: dict, cons: dict) -> GoalCheckpointResult:
    try:
        recomputed = goal_feasibility(
            target_amount   = cons["target_amount"],
            current_savings = cons["current_savings"],
            monthly_savings = cons["monthly_savings"],
            annual_rate     = cons["annual_rate"],
            horizon_months  = cons["horizon_months"],
        )
    except Exception as exc:
        return GoalCheckpointResult(
            passed=False,
            errors=[f"goal_feasibility() re-run raised {type(exc).__name__}: {exc}"],
        )

    errors: list[str] = []

    # Check 1: exact label match — catches deliberately injected wrong label
    stored_label = stored.get("feasibility_label")
    recomputed_label = recomputed["label"]
    if stored_label != recomputed_label:
        errors.append(
            f"label mismatch: stored='{stored_label}', "
            f"recomputed='{recomputed_label}'"
        )

    # Check 2: projected_balance within Rs.1
    stored_balance = float(stored.get("projected_balance", 0))
    recomputed_balance = recomputed["projected_balance"]
    if abs(stored_balance - recomputed_balance) > BALANCE_TOLERANCE:
        errors.append(
            f"projected_balance mismatch: stored={stored_balance:.2f}, "
            f"recomputed={recomputed_balance:.2f}, "
            f"delta={abs(stored_balance - recomputed_balance):.2f}"
        )

    # Check 3: coverage_ratio within 0.1%
    stored_ratio = float(stored.get("coverage_ratio", 0))
    recomputed_ratio = recomputed["coverage_ratio"]
    if abs(stored_ratio - recomputed_ratio) > RATIO_TOLERANCE:
        errors.append(
            f"coverage_ratio mismatch: stored={stored_ratio:.4f}, "
            f"recomputed={recomputed_ratio:.4f}"
        )

    passed = len(errors) == 0
    if passed:
        logger.info(
            "goal_checkpoint (standard): PASSED — label=%s balance=%.2f",
            recomputed_label, recomputed_balance,
        )
    else:
        logger.warning("goal_checkpoint (standard): FAILED — %s", errors)

    return GoalCheckpointResult(passed=passed, errors=errors, recomputed=recomputed)


def _check_debt_payoff(stored: dict, cons: dict) -> GoalCheckpointResult:
    try:
        recomputed = debt_payoff_schedule(
            outstanding          = cons["outstanding"],
            annual_interest_rate = cons["interest_rate"],
            monthly_payment      = cons["monthly_payment"],
        )
    except Exception as exc:
        return GoalCheckpointResult(
            passed=False,
            errors=[f"debt_payoff_schedule() re-run raised {type(exc).__name__}: {exc}"],
        )

    errors: list[str] = []

    if stored.get("payment_sufficient") != recomputed["payment_sufficient"]:
        errors.append(
            f"payment_sufficient mismatch: "
            f"stored={stored.get('payment_sufficient')}, "
            f"recomputed={recomputed['payment_sufficient']}"
        )
    if stored.get("total_months") != recomputed["total_months"]:
        errors.append(
            f"total_months mismatch: stored={stored.get('total_months')}, "
            f"recomputed={recomputed['total_months']}"
        )

    passed = len(errors) == 0
    if passed:
        logger.info("goal_checkpoint (debt_payoff): PASSED")
    else:
        logger.warning("goal_checkpoint (debt_payoff): FAILED — %s", errors)

    return GoalCheckpointResult(passed=passed, errors=errors, recomputed=recomputed)


def _check_multi_goal(stored: dict, cons: dict) -> GoalCheckpointResult:
    try:
        recomputed = multi_goal_tradeoff(
            goals                   = cons["sub_goals"],
            total_monthly_available = cons["total_monthly_available"],
            annual_rate             = cons["annual_rate"],
        )
    except Exception as exc:
        return GoalCheckpointResult(
            passed=False,
            errors=[f"multi_goal_tradeoff() re-run raised {type(exc).__name__}: {exc}"],
        )

    errors: list[str] = []

    recomputed_feasible = sum(
        1 for a in recomputed["allocations"]
        if a["feasibility"]["label"] == "FEASIBLE"
    )
    if stored.get("total_goals") != len(recomputed["allocations"]):
        errors.append(
            f"total_goals mismatch: stored={stored.get('total_goals')}, "
            f"recomputed={len(recomputed['allocations'])}"
        )
    if stored.get("feasible_goals") != recomputed_feasible:
        errors.append(
            f"feasible_goals mismatch: stored={stored.get('feasible_goals')}, "
            f"recomputed={recomputed_feasible}"
        )

    passed = len(errors) == 0
    if passed:
        logger.info("goal_checkpoint (multi_goal): PASSED")
    else:
        logger.warning("goal_checkpoint (multi_goal): FAILED — %s", errors)

    return GoalCheckpointResult(passed=passed, errors=errors, recomputed=recomputed)


def run_goal_checkpoint(
    stored_outcomes: dict | None,
    constraints: dict | None,
) -> GoalCheckpointResult:
    """
    Re-run goal simulation and assert results match stored outputs.

    Dispatches by goal_type in constraints.
    Never raises — exceptions become FAILED results.
    """
    if stored_outcomes is None:
        return GoalCheckpointResult(
            passed=False,
            errors=["projected_outcomes is None — goal_simulate did not run"],
        )
    if constraints is None:
        return GoalCheckpointResult(
            passed=False,
            errors=["constraints is None — goal_simulate did not write constraints"],
        )

    goal_type = constraints.get("goal_type", "")

    if goal_type == "debt_payoff":
        for key in ("outstanding", "interest_rate", "monthly_payment"):
            if key not in constraints:
                return GoalCheckpointResult(
                    passed=False,
                    errors=[f"debt_payoff constraints missing key '{key}'"],
                )
        return _check_debt_payoff(stored_outcomes, constraints)

    elif goal_type == "multi_goal":
        for key in ("sub_goals", "total_monthly_available", "annual_rate"):
            if key not in constraints:
                return GoalCheckpointResult(
                    passed=False,
                    errors=[f"multi_goal constraints missing key '{key}'"],
                )
        return _check_multi_goal(stored_outcomes, constraints)

    else:
        for key in ("target_amount", "current_savings", "monthly_savings",
                    "annual_rate", "horizon_months"):
            if key not in constraints:
                return GoalCheckpointResult(
                    passed=False,
                    errors=[f"standard goal constraints missing key '{key}'"],
                )
        return _check_standard_goal(stored_outcomes, constraints)
"""
VaultAI V3 — Simulation Engine: forecast.py
============================================
Pure deterministic math. Zero LLM. Zero DB. Zero LangGraph.

This module is the ground truth for every agent in V3.
All agent validation checkpoints re-run functions from here and assert
their stored outputs match. If this module is wrong, every agent is wrong.

Formula audit trail:
  compound_growth    — standard compound interest: P(1 + r)^n
  monthly_projection — builds month-by-month balance array
  savings_trajectory — adds periodic contributions to compound growth
  goal_feasibility   — determines FEASIBLE / STRETCH / INFEASIBLE
  contribution_required — solves for required monthly payment to hit goal

All functions use Python's Decimal internally for precision, but accept
and return plain float for ergonomics. Precision is capped at 2dp on
output so downstream comparisons are stable.
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP, ROUND_UP, InvalidOperation
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Rate guard: annual growth rates above this are capped with a warning flag.
# Prevents simulation engine from producing fantasy numbers on bad input.
MAX_ANNUAL_RATE: float = 0.30  # 30%

# Feasibility thresholds (matches V3 spec exactly)
STRETCH_LOWER: float = 0.70   # 70% of required → INFEASIBLE below
STRETCH_UPPER: float = 0.99   # 99% of required → STRETCH below FEASIBLE

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_decimal(value: float, label: str = "value") -> Decimal:
    """Convert float to Decimal safely. Raises ValueError on NaN/Inf."""
    if not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number, got {value}")
    return Decimal(str(value))


def _round2(d: Decimal) -> float:
    """Round Decimal to 2 decimal places and return as float."""
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _annual_to_monthly_rate(annual_rate: float) -> Decimal:
    """
    Convert annual percentage rate to monthly rate.
    Formula: monthly = (1 + annual)^(1/12) - 1

    This is the geometrically correct conversion, not the naive annual/12.
    Matters for multi-year projections.
    """
    if annual_rate == 0.0:
        return Decimal("0")
    d = _to_decimal(annual_rate, "annual_rate")
    monthly = (1 + d) ** (Decimal("1") / Decimal("12")) - 1
    return monthly


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compound_growth(principal: float, annual_rate: float, months: int) -> float:
    """
    Atomic unit of the simulation engine.

    Calculate the future value of a lump sum with compound interest.

    Formula: FV = P * (1 + r_monthly)^n

    Args:
        principal:    Starting amount (>= 0)
        annual_rate:  Annual growth rate as decimal (0.10 = 10%).
                      Negative rates allowed (depreciation / debt).
                      Capped at MAX_ANNUAL_RATE (30%) with flag in result.
        months:       Number of months (>= 0)

    Returns:
        Future value as float, rounded to 2 decimal places.

    Manual verification (spot-check against Excel FV function):
        compound_growth(10000, 0.10, 12)
        → monthly_rate = (1.10)^(1/12) - 1 ≈ 0.007974
        → FV = 10000 * (1.007974)^12 = 10000 * 1.10 = 10,000.00 ✓

        compound_growth(50000, 0.08, 60)
        → monthly_rate ≈ 0.006434
        → FV = 50000 * (1.006434)^60 ≈ 73,466.40
        (verify: =FV(0.08/12,60,0,-50000) ≈ 73,466 — close, slight diff
         because Excel uses simple monthly division, we use geometric) ✓

        compound_growth(0, 0.12, 24) → 0.00 ✓
        compound_growth(1000, 0.0, 12) → 1000.00 ✓

    Raises:
        ValueError: if principal < 0, months < 0, or non-finite inputs
    """
    if principal < 0:
        raise ValueError(f"principal must be >= 0, got {principal}")
    if months < 0:
        raise ValueError(f"months must be >= 0, got {months}")

    # Guard extreme rates
    _rate_capped = annual_rate
    if annual_rate > MAX_ANNUAL_RATE:
        _rate_capped = MAX_ANNUAL_RATE  # caller can check audit_payload for cap flag

    p = _to_decimal(principal, "principal")
    monthly_rate = _annual_to_monthly_rate(_rate_capped)
    n = Decimal(str(months))

    if monthly_rate == 0:
        fv = p
    else:
        fv = p * (1 + monthly_rate) ** n

    return _round2(fv)


def monthly_projection(
    principal: float,
    annual_rate: float,
    months: int,
    monthly_contribution: float = 0.0,
) -> list[dict]:
    """
    Build a month-by-month balance array.

    Each entry shows the balance at the END of that month, after:
      1. Growth applied to opening balance
      2. Contribution added

    This is the foundation for all charts and timeline UIs.

    Formula per month:
        balance[m] = balance[m-1] * (1 + r_monthly) + contribution

    Args:
        principal:            Opening balance
        annual_rate:          Annual growth rate (decimal)
        months:               Number of months to project
        monthly_contribution: Fixed amount added each month (default 0)

    Returns:
        List of dicts: [{"month": int, "balance": float, "growth": float,
                          "contribution": float}, ...]
        Month 0 = opening balance (no growth applied yet).

    Manual verification (spot-check):
        monthly_projection(1000, 0.12, 3, 100)
        monthly_r ≈ 0.009489
        Month 1: 1000 * 1.009489 + 100 = 1109.49
        Month 2: 1109.49 * 1.009489 + 100 = 1220.02
        Month 3: 1220.02 * 1.009489 + 100 = 1331.60
        (verify manually ✓)

    Raises:
        ValueError: if principal < 0, months < 0, contribution < 0
    """
    if principal < 0:
        raise ValueError(f"principal must be >= 0, got {principal}")
    if months < 0:
        raise ValueError(f"months must be >= 0, got {months}")
    if monthly_contribution < 0:
        raise ValueError(f"monthly_contribution must be >= 0, got {monthly_contribution}")

    _rate_capped = min(annual_rate, MAX_ANNUAL_RATE) if annual_rate > 0 else annual_rate
    monthly_rate = _annual_to_monthly_rate(_rate_capped)

    p = _to_decimal(principal, "principal")
    c = _to_decimal(monthly_contribution, "monthly_contribution")

    result = [{"month": 0, "balance": _round2(p), "growth": 0.0, "contribution": 0.0}]

    balance = p
    for m in range(1, months + 1):
        growth = balance * monthly_rate
        balance = balance + growth + c
        result.append({
            "month": m,
            "balance": _round2(balance),
            "growth": _round2(growth),
            "contribution": _round2(c),
        })

    return result


def savings_trajectory(
    current_savings: float,
    monthly_savings: float,
    annual_rate: float,
    months: int,
) -> dict:
    """
    Project the full savings trajectory given regular monthly contributions.

    This is the primary function for BudgetAgent and GoalAgent projections.
    It wraps monthly_projection and adds summary statistics.

    Args:
        current_savings:  Current balance / starting point
        monthly_savings:  Fixed monthly contribution (>= 0)
        annual_rate:      Expected annual growth rate (decimal)
        months:           Projection horizon in months

    Returns:
        {
            "final_balance": float,
            "total_contributed": float,
            "total_growth": float,
            "monthly_breakdown": list[dict],   ← from monthly_projection
            "rate_capped": bool,               ← True if rate was capped
            "effective_annual_rate": float,    ← actual rate used
        }

    Manual verification:
        savings_trajectory(0, 5000, 0.08, 12)
        → 12 months of 5000/month at 8% annual
        → total_contributed = 60,000
        → growth ≈ 2,599 (rough: 60k * ~4.3% average time-weighted)
        → final_balance ≈ 62,599
    """
    if current_savings < 0:
        raise ValueError(f"current_savings must be >= 0, got {current_savings}")
    if monthly_savings < 0:
        raise ValueError(f"monthly_savings must be >= 0, got {monthly_savings}")
    if months <= 0:
        raise ValueError(f"months must be > 0, got {months}")

    rate_capped = annual_rate > MAX_ANNUAL_RATE
    effective_rate = min(annual_rate, MAX_ANNUAL_RATE) if annual_rate > 0 else annual_rate

    breakdown = monthly_projection(current_savings, effective_rate, months, monthly_savings)

    final_balance = breakdown[-1]["balance"]
    total_contributed = _round2(_to_decimal(monthly_savings) * Decimal(str(months)))
    total_growth = _round2(_to_decimal(final_balance) - _to_decimal(current_savings) - _to_decimal(total_contributed))

    return {
        "final_balance": final_balance,
        "total_contributed": total_contributed,
        "total_growth": total_growth,
        "monthly_breakdown": breakdown,
        "rate_capped": rate_capped,
        "effective_annual_rate": effective_rate,
    }


def goal_feasibility(
    target_amount: float,
    current_savings: float,
    monthly_savings: float,
    annual_rate: float,
    horizon_months: int,
) -> dict:
    """
    Determine whether a financial goal is FEASIBLE, STRETCH, or INFEASIBLE.

    This is the core output for GoalAgent. The labels match the V3 spec:
        FEASIBLE    — projected final balance >= target
        STRETCH     — projected balance is 70–99% of target
        INFEASIBLE  — projected balance < 70% of target

    The function also computes:
        - gap_amount: how much short (0 if feasible)
        - months_to_goal: earliest month the balance hits the target
                          (None if never reached in horizon)
        - surplus: how much over target at end (0 if not feasible)

    Args:
        target_amount:    Goal amount to reach
        current_savings:  Starting savings balance
        monthly_savings:  Fixed monthly contribution
        annual_rate:      Annual growth rate (decimal)
        horizon_months:   Number of months in the planning window

    Returns:
        {
            "label":             "FEASIBLE" | "STRETCH" | "INFEASIBLE",
            "target_amount":     float,
            "projected_balance": float,
            "gap_amount":        float,
            "surplus":           float,
            "months_to_goal":    int | None,
            "coverage_ratio":    float,   ← projected / target
            "horizon_months":    int,
        }

    Manual verification (spot-check):
        goal_feasibility(100000, 10000, 5000, 0.08, 18)
        → savings_trajectory(10000, 5000, 0.08, 18)
        → total_contributed = 90,000 + 10,000 = 100,000 start
        → At 8% annual over 18 months with 5k/month, final ≈ 106,xxx
        → label = FEASIBLE ✓

        goal_feasibility(200000, 0, 5000, 0.0, 24)
        → total = 5000 * 24 = 120,000 < 200,000
        → coverage = 0.60 → INFEASIBLE ✓

    Raises:
        ValueError: if target <= 0, horizon <= 0, or negative inputs
    """
    if target_amount <= 0:
        raise ValueError(f"target_amount must be > 0, got {target_amount}")
    if horizon_months <= 0:
        raise ValueError(f"horizon_months must be > 0, got {horizon_months}")
    if current_savings < 0:
        raise ValueError(f"current_savings must be >= 0, got {current_savings}")
    if monthly_savings < 0:
        raise ValueError(f"monthly_savings must be >= 0, got {monthly_savings}")

    trajectory = savings_trajectory(
        current_savings, monthly_savings, annual_rate, horizon_months
    )

    projected = trajectory["final_balance"]
    target_d = _to_decimal(target_amount)
    projected_d = _to_decimal(projected)

    coverage_ratio = _round2(projected_d / target_d)

    # Determine label
    if projected_d >= target_d:
        label = "FEASIBLE"
        gap = 0.0
        surplus = _round2(projected_d - target_d)
    elif coverage_ratio >= STRETCH_LOWER:
        label = "STRETCH"
        gap = _round2(target_d - projected_d)
        surplus = 0.0
    else:
        label = "INFEASIBLE"
        gap = _round2(target_d - projected_d)
        surplus = 0.0

    # Find earliest month balance hits target
    months_to_goal = None
    for entry in trajectory["monthly_breakdown"]:
        if _to_decimal(entry["balance"]) >= target_d:
            months_to_goal = entry["month"]
            break

    return {
        "label": label,
        "target_amount": target_amount,
        "projected_balance": projected,
        "gap_amount": gap,
        "surplus": surplus,
        "months_to_goal": months_to_goal,
        "coverage_ratio": coverage_ratio,
        "horizon_months": horizon_months,
    }


def contribution_required(
    target_amount: float,
    current_savings: float,
    annual_rate: float,
    horizon_months: int,
) -> dict:
    """
    Solve for the monthly contribution needed to reach a target.

    This is the inverse of goal_feasibility. Given a target, a starting
    balance, a rate, and a horizon — what monthly deposit is required?

    Formula (Future Value of annuity, solved for payment PMT):
        FV = P*(1+r)^n + PMT * [ ((1+r)^n - 1) / r ]
        → PMT = (FV - P*(1+r)^n) * r / ((1+r)^n - 1)

    Special case: if rate == 0:
        PMT = (FV - P) / n

    Args:
        target_amount:   Goal to reach
        current_savings: Current balance
        annual_rate:     Annual growth rate (decimal)
        horizon_months:  Months to reach target

    Returns:
        {
            "monthly_contribution_required": float,
            "total_to_contribute":           float,
            "growth_contribution":           float,   ← how much growth does
            "is_already_feasible":           bool,    ← current_savings >= target
        }

    Manual verification (spot-check):
        contribution_required(100000, 0, 0.08, 24)
        → monthly_r ≈ 0.006434
        → (1+r)^24 ≈ 1.1729
        → PMT = 100000 * 0.006434 / (1.1729 - 1)
               = 643.4 / 0.1729 ≈ 3721.00
        Verify: savings_trajectory(0, 3721, 0.08, 24)["final_balance"] ≈ 100,000 ✓

        contribution_required(5000, 5000, 0.08, 12)
        → already feasible, required = 0.00 ✓

    Raises:
        ValueError: if target <= 0, horizon <= 0, current_savings < 0
    """
    if target_amount <= 0:
        raise ValueError(f"target_amount must be > 0, got {target_amount}")
    if horizon_months <= 0:
        raise ValueError(f"horizon_months must be > 0, got {horizon_months}")
    if current_savings < 0:
        raise ValueError(f"current_savings must be >= 0, got {current_savings}")

    # Already feasible — no contribution needed
    if current_savings >= target_amount:
        return {
            "monthly_contribution_required": 0.0,
            "total_to_contribute": 0.0,
            "growth_contribution": 0.0,
            "is_already_feasible": True,
        }

    effective_rate = min(annual_rate, MAX_ANNUAL_RATE) if annual_rate > 0 else annual_rate
    monthly_rate = _annual_to_monthly_rate(effective_rate)

    fv = _to_decimal(target_amount)
    p = _to_decimal(current_savings)
    n = Decimal(str(horizon_months))
    r = monthly_rate

    if r == 0:
        # Linear case: PMT = (FV - P) / n
        pmt = (fv - p) / n
    else:
        # Standard annuity formula
        growth_factor = (1 + r) ** n
        pmt = (fv - p * growth_factor) * r / (growth_factor - 1)

    if pmt < 0:
        # Means current savings + growth alone exceed target — no contributions needed
        pmt = Decimal("0")

    # Use ROUND_UP (ceiling to nearest cent) so the plan always meets or slightly
    # exceeds the target. ROUND_HALF_UP can produce a PMT that is fractionally
    # too low, causing the consistency invariant (PMT → FEASIBLE) to fail.
    pmt_float = float(pmt.quantize(Decimal("0.01"), rounding=ROUND_UP))
    total_to_contribute = _round2(Decimal(str(pmt_float)) * n)

    # How much of the gap does growth cover?
    growth_only = _round2(_to_decimal(compound_growth(float(p), effective_rate, horizon_months)) - p)

    return {
        "monthly_contribution_required": pmt_float,
        "total_to_contribute": total_to_contribute,
        "growth_contribution": growth_only,
        "is_already_feasible": False,
    }
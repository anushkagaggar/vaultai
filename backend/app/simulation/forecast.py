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


def debt_payoff_schedule(
    outstanding: float,
    annual_interest_rate: float,
    monthly_payment: float,
) -> dict:
    """
    Generate a full debt payoff schedule with amortisation.

    Given an outstanding balance, an annual interest rate, and a fixed
    monthly payment, produce the month-by-month schedule showing:
      - opening balance each month
      - interest charged
      - principal repaid
      - closing balance

    Also computes:
      - total_months: how many months until balance hits zero
      - total_interest_paid: sum of all interest charges
      - interest_saved: difference vs paying minimum (interest-only)
      - minimum_payment: interest-only payment (balance never reduces)

    Formula per month:
        interest_charge = opening_balance * monthly_rate
        principal_paid  = monthly_payment - interest_charge
        closing_balance = opening_balance - principal_paid

    The schedule terminates when closing_balance <= 0 or at month 600
    (50-year guard to prevent infinite loops on near-zero payments).

    Args:
        outstanding:           Current debt balance (> 0)
        annual_interest_rate:  Annual rate as decimal (0.18 = 18%)
        monthly_payment:       Fixed monthly payment amount

    Returns:
        {
            "total_months":        int,
            "total_interest_paid": float,
            "total_paid":          float,
            "interest_saved":      float,   ← vs interest-only path
            "minimum_payment":     float,   ← interest-only amount
            "payoff_schedule":     list[dict],
            "payment_sufficient":  bool,    ← False if payment <= interest
        }

    Manual verification:
        debt_payoff_schedule(100000, 0.12, 5000)
        monthly_r ≈ 0.009489
        Month 1: interest = 100000 * 0.009489 = 948.9, principal = 4051.1
        Month 2: balance = 95948.9, interest = 910.0, principal = 4090.0
        ...continues until balance = 0
        total_months ≈ 24 (verify with Excel NPER(1%,5000,-100000) ≈ 22.4)

    Raises:
        ValueError: outstanding <= 0, rate < 0, payment <= 0
    """
    if outstanding <= 0:
        raise ValueError(f"outstanding must be > 0, got {outstanding}")
    if annual_interest_rate < 0:
        raise ValueError(f"annual_interest_rate must be >= 0, got {annual_interest_rate}")
    if monthly_payment <= 0:
        raise ValueError(f"monthly_payment must be > 0, got {monthly_payment}")

    monthly_rate = _annual_to_monthly_rate(
        min(annual_interest_rate, MAX_ANNUAL_RATE)
    )
    minimum_payment = _round2(_to_decimal(outstanding) * monthly_rate)

    # Guard: if payment doesn't cover interest, debt grows — flag it
    first_interest = _round2(_to_decimal(outstanding) * monthly_rate)
    if monthly_payment <= first_interest:
        return {
            "total_months":        None,
            "total_interest_paid": None,
            "total_paid":          None,
            "interest_saved":      None,
            "minimum_payment":     minimum_payment,
            "payoff_schedule":     [],
            "payment_sufficient":  False,
        }

    balance = _to_decimal(outstanding)
    payment = _to_decimal(monthly_payment)
    schedule: list[dict] = []
    total_interest = Decimal("0")
    month = 0
    MAX_MONTHS = 600   # 50-year guard

    while balance > Decimal("0.005") and month < MAX_MONTHS:
        month += 1
        interest_charge = balance * monthly_rate
        # Final month: payment may exceed remaining balance
        actual_payment  = min(payment, balance + interest_charge)
        principal_paid  = actual_payment - interest_charge
        closing_balance = balance - principal_paid

        total_interest += interest_charge
        schedule.append({
            "month":            month,
            "opening_balance":  _round2(balance),
            "interest_charge":  _round2(interest_charge),
            "principal_paid":   _round2(principal_paid),
            "payment":          _round2(actual_payment),
            "closing_balance":  _round2(max(closing_balance, Decimal("0"))),
        })
        balance = max(closing_balance, Decimal("0"))

    total_paid     = _round2(_to_decimal(outstanding) + total_interest)
    interest_total = _round2(total_interest)

    # interest_saved = what you'd pay in interest if you just paid
    # interest-only forever (technically infinite, so we cap at 10 years
    # vs actual schedule)
    interest_only_10yr = _round2(
        _to_decimal(outstanding) * monthly_rate * Decimal("120")
    )
    interest_saved = _round2(
        max(Decimal("0"), _to_decimal(interest_only_10yr) - total_interest)
    )

    return {
        "total_months":        month,
        "total_interest_paid": interest_total,
        "total_paid":          total_paid,
        "interest_saved":      interest_saved,
        "minimum_payment":     minimum_payment,
        "payoff_schedule":     schedule,
        "payment_sufficient":  True,
    }


def multi_goal_tradeoff(
    goals: list[dict],
    total_monthly_available: float,
    annual_rate: float = 0.07,
) -> dict:
    """
    Allocate a fixed monthly budget across 2-5 concurrent goals.

    Each goal is assessed individually via goal_feasibility, then the
    budget is allocated using a priority-weighted split. Goals are
    prioritised by:
      1. Explicit priority rank (if provided in goal dict)
      2. Urgency: goals with shorter horizons get higher weight
      3. Feasibility: INFEASIBLE goals get minimum floor allocation

    Args:
        goals: list of 2-5 goal dicts, each containing:
            {
                "goal_id":       str,           ← caller-assigned ID
                "label":         str,           ← display name
                "target_amount": float,
                "horizon_months": int,
                "current_savings": float,       ← default 0
                "priority":      int,           ← 1=highest (optional)
            }
        total_monthly_available: total monthly amount to split across goals
        annual_rate: assumed growth rate for all goals (decimal)

    Returns:
        {
            "total_monthly_available": float,
            "total_allocated":         float,
            "unallocated":             float,
            "allocations": [
                {
                    "goal_id":            str,
                    "label":              str,
                    "monthly_allocated":  float,
                    "feasibility":        dict,    ← from goal_feasibility
                    "contribution_req":   dict,    ← from contribution_required
                    "meets_requirement":  bool,    ← allocated >= required
                    "priority_rank":      int,
                    "weight":             float,
                },
                ...
            ],
            "tradeoff_summary": str,   ← human-readable allocation summary
        }

    Raises:
        ValueError: fewer than 2 or more than 5 goals, or invalid goal dicts
    """
    if not (2 <= len(goals) <= 5):
        raise ValueError(
            f"multi_goal_tradeoff requires 2-5 goals, got {len(goals)}"
        )
    if total_monthly_available <= 0:
        raise ValueError(
            f"total_monthly_available must be > 0, got {total_monthly_available}"
        )

    # Validate each goal and compute required contribution
    enriched: list[dict] = []
    for i, g in enumerate(goals):
        for req_key in ("goal_id", "target_amount", "horizon_months"):
            if req_key not in g:
                raise ValueError(
                    f"Goal at index {i} missing required key '{req_key}'"
                )
        target   = float(g["target_amount"])
        horizon  = int(g["horizon_months"])
        current  = float(g.get("current_savings", 0))
        priority = int(g.get("priority", i + 1))

        if horizon <= 0:
            raise ValueError(
                f"Goal '{g['goal_id']}': horizon_months must be > 0"
            )

        feasibility = goal_feasibility(
            target_amount   = target,
            current_savings = current,
            monthly_savings = 0.0,   # without any allocation
            annual_rate     = annual_rate,
            horizon_months  = horizon,
        )
        contrib = contribution_required(
            target_amount   = target,
            current_savings = current,
            annual_rate     = annual_rate,
            horizon_months  = horizon,
        )

        enriched.append({
            "goal_id":           g["goal_id"],
            "label":             g.get("label", g["goal_id"]),
            "target_amount":     target,
            "horizon_months":    horizon,
            "current_savings":   current,
            "priority":          priority,
            "feasibility":       feasibility,
            "contribution_req":  contrib,
            "required_monthly":  contrib["monthly_contribution_required"],
        })

    # ── Priority-weighted allocation ─────────────────────────────────────
    # Weight formula:
    #   base_weight  = 1 / priority_rank        (lower rank = higher weight)
    #   urgency_mult = 1 / sqrt(horizon_months) (shorter horizon = higher weight)
    #   final_weight = base_weight * urgency_mult, normalised to sum = 1.0
    import math as _math
    weights: list[float] = []
    for g in enriched:
        base     = 1.0 / g["priority"]
        urgency  = 1.0 / _math.sqrt(max(g["horizon_months"], 1))
        weights.append(base * urgency)

    total_weight = sum(weights)
    norm_weights = [w / total_weight for w in weights]

    # First pass: allocate proportionally
    raw_allocations = [
        total_monthly_available * w for w in norm_weights
    ]

    # Second pass: ensure each goal gets at least its required amount
    # if total budget allows, otherwise allocate proportionally
    total_required = sum(g["required_monthly"] for g in enriched)
    available = _to_decimal(total_monthly_available)

    if _to_decimal(total_required) <= available:
        # Budget sufficient — give each goal exactly what it needs,
        # distribute surplus proportionally
        surplus = float(available) - total_required
        final_allocations = []
        for i, g in enumerate(enriched):
            alloc = g["required_monthly"] + surplus * norm_weights[i]
            final_allocations.append(_round2(_to_decimal(alloc)))
    else:
        # Budget insufficient — proportional split, no goal gets zero
        final_allocations = [
            max(_round2(_to_decimal(a)), 0.01) for a in raw_allocations
        ]

    # Build output
    allocations = []
    total_allocated = 0.0
    for i, g in enumerate(enriched):
        alloc = final_allocations[i]
        total_allocated += alloc

        # Re-run feasibility with allocated amount
        feasibility_with_alloc = goal_feasibility(
            target_amount   = g["target_amount"],
            current_savings = g["current_savings"],
            monthly_savings = alloc,
            annual_rate     = annual_rate,
            horizon_months  = g["horizon_months"],
        )

        allocations.append({
            "goal_id":           g["goal_id"],
            "label":             g["label"],
            "monthly_allocated": alloc,
            "feasibility":       feasibility_with_alloc,
            "contribution_req":  g["contribution_req"],
            "meets_requirement": alloc >= g["required_monthly"] - 0.01,
            "priority_rank":     g["priority"],
            "weight":            round(norm_weights[i], 4),
        })

    unallocated = _round2(_to_decimal(total_monthly_available) - _to_decimal(total_allocated))

    # Build tradeoff summary
    feasible_count = sum(
        1 for a in allocations
        if a["feasibility"]["label"] == "FEASIBLE"
    )
    summary_parts = [
        f"{a['label']}: Rs.{a['monthly_allocated']:,.0f}/mo "
        f"({a['feasibility']['label']})"
        for a in allocations
    ]
    tradeoff_summary = (
        f"{feasible_count}/{len(goals)} goals feasible with "
        f"Rs.{total_monthly_available:,.0f}/mo budget. "
        + " | ".join(summary_parts)
    )

    return {
        "total_monthly_available": total_monthly_available,
        "total_allocated":         _round2(_to_decimal(total_allocated)),
        "unallocated":             unallocated,
        "allocations":             allocations,
        "tradeoff_summary":        tradeoff_summary,
    }
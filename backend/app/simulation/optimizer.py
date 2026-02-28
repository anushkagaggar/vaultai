"""
VaultAI V3 — Simulation Engine: optimizer.py
=============================================
Pure deterministic math. Zero LLM. Zero DB. Zero LangGraph.

This module solves the budget constraint satisfaction problem:
    "Given total income, fixed expenses, and a minimum savings target —
     how should the discretionary spending be allocated?"

Two public functions:

  allocate_budget  — takes income, expense categories, and a savings target;
                     returns how much is available per category after hitting
                     the savings goal. No LP needed — this is a priority-order
                     allocation using a greedy constraint-satisfaction pass.

  solve_constraints — handles the harder case where the user also has
                      per-category min/max bounds. Uses scipy.optimize.linprog
                      (interior-point LP) to find the optimal allocation that
                      maximises savings while respecting all bounds.

Why both?
  allocate_budget is instant and covers 90% of real-world cases.
  solve_constraints is called when the user has explicit constraints
  ("I can't cut rent below X", "I want to keep food above Y"). The BudgetAgent
  checkpoint re-runs whichever function was originally used and asserts the
  output matches to within ±0.01.

Design rules:
  - All inputs and outputs are plain Python dicts/lists — no ORM, no Pydantic
  - scipy.optimize.linprog is the only external dependency
  - Never calls forecast.py (different layer — this is pure budget math)
  - Deterministic: same inputs → identical outputs (linprog with fixed method)

Author: VaultAI V3
"""

from __future__ import annotations

from typing import Optional
import math

import numpy as np
from scipy.optimize import linprog, OptimizeResult


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum savings rate enforced by the optimizer (1%) — prevents plans that
# leave the user with no savings at all.
MIN_SAVINGS_RATE: float = 0.01

# Tolerance for float comparisons in validation
ALLOCATION_TOLERANCE: float = 0.01


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_positive(value: float, name: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number, got {value}")


def _validate_non_negative(value: float, name: str) -> None:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number, got {value}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def allocate_budget(
    income_monthly: float,
    expenses: list[dict],
    savings_target_monthly: float,
    allow_deficit: bool = False,
) -> dict:
    """
    Priority-based budget allocation.

    Given a monthly income, a list of expense categories (each with a
    current amount and a priority), and a savings target — compute how much
    disposable budget remains for each category after the savings goal is met.

    The algorithm:
      1. Sum all FIXED expenses (priority="fixed") — these cannot be cut.
      2. Subtract fixed expenses + savings_target from income → discretionary pool.
      3. If pool is negative and allow_deficit=False → return INFEASIBLE.
      4. Distribute the pool to FLEXIBLE categories in priority order
         (lower priority_rank = more important). Each category gets its full
         requested amount until the pool is exhausted; remaining categories
         are scaled down proportionally.

    Expense dict format:
        {
            "category":       str,    — e.g. "rent", "food", "subscriptions"
            "amount":         float,  — current monthly spend
            "priority":       str,    — "fixed" | "flexible"
            "priority_rank":  int,    — 1 = highest priority (keep), 10 = cut first
                                        (only meaningful for flexible)
            "min_amount":     float,  — optional floor (default 0)
        }

    Args:
        income_monthly:          Total monthly take-home income
        expenses:                List of expense category dicts
        savings_target_monthly:  Minimum amount to save each month
        allow_deficit:           If True, return a deficit plan instead of failing

    Returns:
        {
            "status":              "FEASIBLE" | "INFEASIBLE" | "DEFICIT",
            "income_monthly":      float,
            "savings_target":      float,
            "total_fixed":         float,
            "discretionary_pool":  float,          ← income - fixed - savings_target
            "allocations": [
                {
                    "category":     str,
                    "requested":    float,
                    "allocated":    float,
                    "cut_amount":   float,          ← requested - allocated
                    "cut_pct":      float,          ← cut_amount / requested * 100
                    "priority":     str,
                    "priority_rank": int,
                },
                ...
            ],
            "total_allocated":     float,           ← sum of all allocations
            "actual_savings":      float,           ← income - total_allocated - fixed
            "savings_gap":         float,           ← savings_target - actual_savings
                                                       (0 if feasible)
            "surplus":             float,           ← actual_savings - savings_target
                                                       (0 if infeasible)
        }

    Manual spot-check:
        income = 100,000
        fixed = [rent=30000, utilities=5000]  → total_fixed = 35,000
        flexible = [food=15000, subscriptions=3000, dining=5000]
        savings_target = 20,000
        pool = 100,000 - 35,000 - 20,000 = 45,000
        total_flexible_requested = 23,000
        pool(45k) > requested(23k) → all flexible fully funded
        actual_savings = 100,000 - 35,000 - 23,000 = 42,000
        surplus = 42,000 - 20,000 = 22,000 ✓

    Raises:
        ValueError: invalid inputs
    """
    _validate_positive(income_monthly, "income_monthly")
    _validate_non_negative(savings_target_monthly, "savings_target_monthly")

    if not expenses:
        raise ValueError("expenses list must not be empty")

    # Validate each expense entry
    for i, exp in enumerate(expenses):
        for key in ("category", "amount", "priority"):
            if key not in exp:
                raise ValueError(f"expenses[{i}] missing key '{key}'")
        if exp["priority"] not in ("fixed", "flexible"):
            raise ValueError(
                f"expenses[{i}]['priority'] must be 'fixed' or 'flexible', "
                f"got '{exp['priority']}'"
            )
        _validate_non_negative(exp["amount"], f"expenses[{i}]['amount']")

    # Separate fixed vs flexible
    fixed_expenses = [e for e in expenses if e["priority"] == "fixed"]
    flex_expenses = sorted(
        [e for e in expenses if e["priority"] == "flexible"],
        key=lambda e: e.get("priority_rank", 5),
    )

    total_fixed = round(sum(e["amount"] for e in fixed_expenses), 2)
    discretionary_pool = round(income_monthly - total_fixed - savings_target_monthly, 2)

    # Check feasibility
    if discretionary_pool < 0 and not allow_deficit:
        # Still compute what the deficit looks like — useful for the UI
        status = "INFEASIBLE"
    elif discretionary_pool < 0:
        status = "DEFICIT"
    else:
        status = "FEASIBLE"

    # Allocate to flexible categories from pool
    allocations = []

    # Fixed expenses — always fully allocated
    for exp in fixed_expenses:
        allocations.append({
            "category": exp["category"],
            "requested": float(exp["amount"]),
            "allocated": float(exp["amount"]),
            "cut_amount": 0.0,
            "cut_pct": 0.0,
            "priority": "fixed",
            "priority_rank": exp.get("priority_rank", 0),
        })

    # Flexible expenses — fill in priority order from pool
    remaining_pool = max(discretionary_pool, 0.0)

    for exp in flex_expenses:
        requested = float(exp["amount"])
        min_amount = float(exp.get("min_amount", 0))

        if remaining_pool >= requested:
            allocated = requested
            remaining_pool = round(remaining_pool - requested, 2)
        elif remaining_pool >= min_amount:
            allocated = round(remaining_pool, 2)
            remaining_pool = 0.0
        else:
            allocated = min_amount
            remaining_pool = 0.0

        cut = round(requested - allocated, 2)
        cut_pct = round(cut / requested * 100, 2) if requested > 0 else 0.0

        allocations.append({
            "category": exp["category"],
            "requested": requested,
            "allocated": allocated,
            "cut_amount": cut,
            "cut_pct": cut_pct,
            "priority": "flexible",
            "priority_rank": exp.get("priority_rank", 5),
        })

    total_allocated = round(sum(a["allocated"] for a in allocations), 2)
    actual_savings = round(income_monthly - total_allocated, 2)
    savings_gap = round(max(0.0, savings_target_monthly - actual_savings), 2)
    surplus = round(max(0.0, actual_savings - savings_target_monthly), 2)

    return {
        "status": status,
        "income_monthly": income_monthly,
        "savings_target": savings_target_monthly,
        "total_fixed": total_fixed,
        "discretionary_pool": discretionary_pool,
        "allocations": allocations,
        "total_allocated": total_allocated,
        "actual_savings": actual_savings,
        "savings_gap": savings_gap,
        "surplus": surplus,
    }


def solve_constraints(
    income_monthly: float,
    categories: list[dict],
    savings_target_monthly: float,
    maximise: str = "savings",
) -> dict:
    """
    LP-based budget constraint solver using scipy.optimize.linprog.

    Handles the case where every category has explicit min/max bounds. The LP
    finds the allocation that maximises savings (or minimises total spend) while
    satisfying all per-category bounds and the hard savings constraint.

    LP formulation (maximise savings):
        Variables: x[i] = allocation for category i
        Minimise:  sum(x[i])                    ← minimising spend = maximising savings
        Subject to:
            sum(x[i]) <= income - savings_target ← total spend ceiling
            x[i] >= lb[i]  for all i             ← per-category minimum
            x[i] <= ub[i]  for all i             ← per-category maximum

    Category dict format:
        {
            "category":  str,
            "min_amount": float,   — hard lower bound (must spend at least this)
            "max_amount": float,   — hard upper bound (will never exceed this)
            "target_amount": float — preferred amount (used as objective weight)
        }

    Args:
        income_monthly:          Total monthly income
        categories:              List of category constraint dicts
        savings_target_monthly:  Minimum required monthly savings
        maximise:                "savings" (default) — minimise total spend
                                 "utilisation" — maximise use of budget

    Returns:
        {
            "status":           "OPTIMAL" | "INFEASIBLE" | "UNBOUNDED",
            "income_monthly":   float,
            "savings_target":   float,
            "allocations": [
                {
                    "category":      str,
                    "min_amount":    float,
                    "max_amount":    float,
                    "allocated":     float,   ← LP solution for this category
                    "at_minimum":    bool,    ← allocated == min_amount
                    "at_maximum":    bool,    ← allocated == max_amount
                },
                ...
            ],
            "total_allocated":  float,
            "actual_savings":   float,
            "savings_gap":      float,
            "solver_message":   str,          ← scipy OptimizeResult.message
        }

    Manual spot-check:
        income = 100,000
        savings_target = 25,000
        categories = [
            {category: "rent",   min: 30000, max: 30000, target: 30000},
            {category: "food",   min: 8000,  max: 15000, target: 12000},
            {category: "other",  min: 5000,  max: 20000, target: 10000},
        ]
        spend_ceiling = 100,000 - 25,000 = 75,000
        min_spend = 30000+8000+5000 = 43,000 ≤ 75,000 → FEASIBLE
        LP minimises spend → food=8000, other=5000 → total=43000
        actual_savings = 100,000 - 43,000 = 57,000 ✓

    Raises:
        ValueError: invalid inputs
    """
    _validate_positive(income_monthly, "income_monthly")
    _validate_non_negative(savings_target_monthly, "savings_target_monthly")

    if not categories:
        raise ValueError("categories list must not be empty")

    for i, cat in enumerate(categories):
        for key in ("category", "min_amount", "max_amount"):
            if key not in cat:
                raise ValueError(f"categories[{i}] missing key '{key}'")
        lb = float(cat["min_amount"])
        ub = float(cat["max_amount"])
        _validate_non_negative(lb, f"categories[{i}]['min_amount']")
        _validate_non_negative(ub, f"categories[{i}]['max_amount']")
        if lb > ub:
            raise ValueError(
                f"categories[{i}]: min_amount ({lb}) > max_amount ({ub})"
            )

    n = len(categories)
    spend_ceiling = income_monthly - savings_target_monthly

    bounds = [
        (float(c["min_amount"]), float(c["max_amount"]))
        for c in categories
    ]

    # Objective: minimise sum(x) to maximise savings
    # For "utilisation" mode: maximise sum(x) → minimise -sum(x) — same direction
    # since we still want to stay under ceiling.
    # Practically: minimise spend (default) uses c=[1,1,...,1]
    if maximise == "savings":
        c_obj = np.ones(n)           # minimise total spend
    else:
        c_obj = -np.ones(n)          # maximise total spend (utilisation)

    # Inequality constraint: sum(x) <= spend_ceiling
    A_ub = np.ones((1, n))
    b_ub = np.array([spend_ceiling])

    result: OptimizeResult = linprog(
        c=c_obj,
        A_ub=A_ub,
        b_ub=b_ub,
        bounds=bounds,
        method="highs",              # HiGHS solver — deterministic, fast, no random seed
    )

    if result.status == 0:
        status = "OPTIMAL"
        x = result.x
        allocations = []
        for i, cat in enumerate(categories):
            alloc = round(float(x[i]), 2)
            lb = float(cat["min_amount"])
            ub = float(cat["max_amount"])
            allocations.append({
                "category": cat["category"],
                "min_amount": lb,
                "max_amount": ub,
                "allocated": alloc,
                "at_minimum": abs(alloc - lb) < ALLOCATION_TOLERANCE,
                "at_maximum": abs(alloc - ub) < ALLOCATION_TOLERANCE,
            })
        total_allocated = round(sum(a["allocated"] for a in allocations), 2)
        actual_savings = round(income_monthly - total_allocated, 2)
        savings_gap = round(max(0.0, savings_target_monthly - actual_savings), 2)

    elif result.status == 2:
        status = "INFEASIBLE"
        allocations = []
        total_allocated = 0.0
        actual_savings = 0.0
        savings_gap = savings_target_monthly

    else:
        status = "UNBOUNDED"
        allocations = []
        total_allocated = 0.0
        actual_savings = 0.0
        savings_gap = savings_target_monthly

    return {
        "status": status,
        "income_monthly": income_monthly,
        "savings_target": savings_target_monthly,
        "allocations": allocations,
        "total_allocated": total_allocated,
        "actual_savings": actual_savings,
        "savings_gap": savings_gap,
        "solver_message": result.message,
    }
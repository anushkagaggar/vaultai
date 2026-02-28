"""
VaultAI V3 — Simulation Engine: scenarios.py
=============================================
Pure deterministic math. Zero LLM. Zero DB. Zero LangGraph.

This module answers the "what if" question:
    "What if I save more? What if the rate is higher? What if I extend my
     horizon by 6 months?"

The SimulateAgent calls build_scenario for a single projection, and
compare_scenarios to put 2–5 scenarios side-by-side. delta_analysis
extracts the numeric difference between any two scenarios so the agent
checkpoint can validate the deltas match re-computed values.

Design rules:
  - All numeric computation delegates to forecast.py — never re-implements math
  - Scenario inputs are plain dicts (no ORM, no Pydantic) for portability
  - Comparison output is structured so ScenarioComparison.tsx can render
    it directly without transformation
  - Every function is deterministic: same inputs → bit-identical output

Author: VaultAI V3
"""

from __future__ import annotations

from typing import Any
from app.simulation.forecast import (
    savings_trajectory,
    goal_feasibility,
    contribution_required,
    MAX_ANNUAL_RATE,
)


# ---------------------------------------------------------------------------
# Types (plain TypedDict-style dicts, no runtime import needed)
# ---------------------------------------------------------------------------

# ScenarioInput keys:
#   current_savings:  float  — opening balance
#   monthly_savings:  float  — fixed monthly contribution (>= 0)
#   annual_rate:      float  — annual growth rate as decimal (e.g. 0.08)
#   horizon_months:   int    — projection window
#   target_amount:    float | None — if provided, feasibility is also computed
#   label:            str    — human-readable name ("conservative", "base", etc.)

REQUIRED_KEYS = {"current_savings", "monthly_savings", "annual_rate",
                 "horizon_months", "label"}


# ---------------------------------------------------------------------------
# Internal validation
# ---------------------------------------------------------------------------

def _validate_scenario_input(scenario: dict, name: str = "scenario") -> None:
    """Raise ValueError if a scenario dict is missing required fields or has
    invalid values. Called at the top of every public function."""
    missing = REQUIRED_KEYS - set(scenario.keys())
    if missing:
        raise ValueError(f"{name} missing required keys: {missing}")

    if scenario["current_savings"] < 0:
        raise ValueError(f"{name}: current_savings must be >= 0")
    if scenario["monthly_savings"] < 0:
        raise ValueError(f"{name}: monthly_savings must be >= 0")
    if scenario["horizon_months"] <= 0:
        raise ValueError(f"{name}: horizon_months must be > 0")
    if "target_amount" in scenario and scenario["target_amount"] is not None:
        if scenario["target_amount"] <= 0:
            raise ValueError(f"{name}: target_amount must be > 0")
    if not isinstance(scenario.get("label", ""), str) or not scenario["label"].strip():
        raise ValueError(f"{name}: label must be a non-empty string")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_scenario(scenario: dict) -> dict:
    """
    Run a single projection scenario and return a fully annotated result.

    This is the single-scenario workhorse. compare_scenarios calls it
    once per scenario and collects the results.

    Input dict keys:
        current_savings:  float   — opening balance
        monthly_savings:  float   — monthly contribution
        annual_rate:      float   — annual growth rate (decimal, capped at 30%)
        horizon_months:   int     — projection window in months
        target_amount:    float   — optional; triggers feasibility computation
        label:            str     — scenario name ("base", "optimistic", etc.)

    Returns:
        {
            "label":              str,
            "inputs": {
                "current_savings":  float,
                "monthly_savings":  float,
                "annual_rate":      float,      ← effective (post-cap)
                "horizon_months":   int,
                "target_amount":    float | None,
            },
            "trajectory": {
                "final_balance":      float,
                "total_contributed":  float,
                "total_growth":       float,
                "monthly_breakdown":  list[dict],
                "rate_capped":        bool,
                "effective_annual_rate": float,
            },
            "feasibility": dict | None,          ← None if no target_amount
            "contribution_plan": dict | None,    ← None if no target_amount
            "summary": {
                "final_balance":             float,
                "total_contributed":         float,
                "total_growth":              float,
                "growth_pct_of_final":       float,   ← growth / final * 100
                "contribution_pct_of_final": float,
                "monthly_savings_rate_pct":  float | None,  ← if income_monthly provided
                "feasibility_label":         str | None,
                "months_to_goal":            int | None,
            }
        }

    Manual spot-check:
        build_scenario({current_savings=0, monthly_savings=5000,
                        annual_rate=0.08, horizon_months=12,
                        target_amount=60000, label="base"})
        → trajectory.final_balance ≈ 62169.43 (matches forecast.py spot-check #4)
        → feasibility.label = FEASIBLE (62169 > 60000) ✓

    Raises:
        ValueError: on missing/invalid inputs
    """
    _validate_scenario_input(scenario, name=f"scenario '{scenario.get('label','?')}'")

    current_savings = float(scenario["current_savings"])
    monthly_savings = float(scenario["monthly_savings"])
    annual_rate = float(scenario["annual_rate"])
    horizon_months = int(scenario["horizon_months"])
    target_amount = scenario.get("target_amount")
    if target_amount is not None:
        target_amount = float(target_amount)
    label = scenario["label"].strip()
    income_monthly = scenario.get("income_monthly")  # optional, for savings rate %

    # --- Core trajectory ---
    trajectory = savings_trajectory(
        current_savings=current_savings,
        monthly_savings=monthly_savings,
        annual_rate=annual_rate,
        months=horizon_months,
    )

    effective_rate = trajectory["effective_annual_rate"]

    # --- Feasibility + contribution plan (only if target given) ---
    feasibility = None
    contribution_plan = None
    if target_amount is not None:
        feasibility = goal_feasibility(
            target_amount=target_amount,
            current_savings=current_savings,
            monthly_savings=monthly_savings,
            annual_rate=effective_rate,
            horizon_months=horizon_months,
        )
        contribution_plan = contribution_required(
            target_amount=target_amount,
            current_savings=current_savings,
            annual_rate=effective_rate,
            horizon_months=horizon_months,
        )

    # --- Summary block ---
    final_balance = trajectory["final_balance"]
    total_contributed = trajectory["total_contributed"]
    total_growth = trajectory["total_growth"]

    growth_pct = round(
        (total_growth / final_balance * 100) if final_balance > 0 else 0.0, 2
    )
    contribution_pct = round(
        (total_contributed / final_balance * 100) if final_balance > 0 else 0.0, 2
    )

    savings_rate_pct = None
    if income_monthly and float(income_monthly) > 0:
        savings_rate_pct = round(monthly_savings / float(income_monthly) * 100, 2)

    summary = {
        "final_balance": final_balance,
        "total_contributed": total_contributed,
        "total_growth": total_growth,
        "growth_pct_of_final": growth_pct,
        "contribution_pct_of_final": contribution_pct,
        "monthly_savings_rate_pct": savings_rate_pct,
        "feasibility_label": feasibility["label"] if feasibility else None,
        "months_to_goal": feasibility["months_to_goal"] if feasibility else None,
    }

    return {
        "label": label,
        "inputs": {
            "current_savings": current_savings,
            "monthly_savings": monthly_savings,
            "annual_rate": effective_rate,
            "horizon_months": horizon_months,
            "target_amount": target_amount,
        },
        "trajectory": trajectory,
        "feasibility": feasibility,
        "contribution_plan": contribution_plan,
        "summary": summary,
    }


def compare_scenarios(scenarios: list[dict]) -> dict:
    """
    Run 2–5 scenarios side-by-side and return a comparison structure.

    This is what the SimulateAgent and the ScenarioComparison.tsx frontend
    component consume. Each scenario is independently computed (no shared
    state between them). The comparison layer then extracts rankings and
    the best-performing scenario.

    Args:
        scenarios: list of 2–5 scenario input dicts (same format as
                   build_scenario input). Labels must be unique.

    Returns:
        {
            "scenario_count":  int,
            "results":         list[dict],     ← one build_scenario output per scenario
            "comparison": {
                "final_balances":   {label: float, ...},
                "total_growths":    {label: float, ...},
                "feasibility_labels": {label: str | None, ...},
                "months_to_goal":   {label: int | None, ...},
                "best_final_balance": str,      ← label of highest final_balance
                "fastest_to_goal":   str | None ← label of smallest months_to_goal
                                                   (None if no scenario has a target)
            },
            "delta":  dict   ← delta_analysis of first two scenarios (for UI diff view)
        }

    Raises:
        ValueError: fewer than 2 or more than 5 scenarios, or duplicate labels
    """
    if len(scenarios) < 2:
        raise ValueError(
            f"compare_scenarios requires at least 2 scenarios, got {len(scenarios)}"
        )
    if len(scenarios) > 5:
        raise ValueError(
            f"compare_scenarios supports at most 5 scenarios, got {len(scenarios)}"
        )

    # Validate all labels are unique
    labels = [s.get("label", "") for s in scenarios]
    if len(set(labels)) != len(labels):
        raise ValueError(
            f"Scenario labels must be unique, got: {labels}"
        )

    # Run each scenario independently
    results = [build_scenario(s) for s in scenarios]

    # Build comparison summary
    final_balances = {r["label"]: r["summary"]["final_balance"] for r in results}
    total_growths = {r["label"]: r["summary"]["total_growth"] for r in results}
    feasibility_labels = {r["label"]: r["summary"]["feasibility_label"] for r in results}
    months_to_goal = {r["label"]: r["summary"]["months_to_goal"] for r in results}

    best_final = max(final_balances, key=lambda k: final_balances[k])

    # Fastest to goal: smallest non-None months_to_goal
    goal_times = {k: v for k, v in months_to_goal.items() if v is not None}
    fastest_to_goal = min(goal_times, key=lambda k: goal_times[k]) if goal_times else None

    comparison = {
        "final_balances": final_balances,
        "total_growths": total_growths,
        "feasibility_labels": feasibility_labels,
        "months_to_goal": months_to_goal,
        "best_final_balance": best_final,
        "fastest_to_goal": fastest_to_goal,
    }

    # Delta between first two scenarios (most common UI need)
    delta = delta_analysis(results[0], results[1])

    return {
        "scenario_count": len(scenarios),
        "results": results,
        "comparison": comparison,
        "delta": delta,
    }


def delta_analysis(scenario_a: dict, scenario_b: dict) -> dict:
    """
    Compute the numeric difference between two build_scenario outputs.

    This is the function the agent validation checkpoint calls to verify
    that a claimed delta matches the re-computed delta. If an LLM says
    "scenario B saves ₹5,000 more than scenario A" and the actual delta
    is ₹4,800, the checkpoint catches it.

    Args:
        scenario_a: first build_scenario result dict  (the "base")
        scenario_b: second build_scenario result dict (the "comparison")

    Returns:
        {
            "label_a":                str,
            "label_b":                str,
            "delta_final_balance":    float,   ← b.final - a.final (positive = b better)
            "delta_total_growth":     float,
            "delta_total_contributed": float,
            "delta_months_to_goal":   int | None,   ← b.months - a.months (negative = b faster)
            "pct_change_final_balance": float,      ← delta / a.final * 100
            "b_is_better_balance":    bool,
            "b_reaches_goal_faster":  bool | None,  ← None if either has no goal
        }

    Manual spot-check:
        scenario_a final_balance = 60000
        scenario_b final_balance = 72000
        delta_final_balance = 12000
        pct_change = 12000/60000*100 = 20.00 ✓

    Raises:
        ValueError: if inputs are not build_scenario output dicts
    """
    # Validate structure
    for name, sc in [("scenario_a", scenario_a), ("scenario_b", scenario_b)]:
        if "summary" not in sc or "label" not in sc:
            raise ValueError(
                f"{name} must be a build_scenario output dict "
                f"(missing 'summary' or 'label' key)"
            )

    sum_a = scenario_a["summary"]
    sum_b = scenario_b["summary"]

    final_a = sum_a["final_balance"]
    final_b = sum_b["final_balance"]

    delta_final = round(final_b - final_a, 2)
    delta_growth = round(sum_b["total_growth"] - sum_a["total_growth"], 2)
    delta_contributed = round(
        sum_b["total_contributed"] - sum_a["total_contributed"], 2
    )

    pct_change = round((delta_final / final_a * 100) if final_a != 0 else 0.0, 2)

    # Months-to-goal delta
    m_a = sum_a.get("months_to_goal")
    m_b = sum_b.get("months_to_goal")

    if m_a is not None and m_b is not None:
        delta_months = m_b - m_a   # negative = b reaches goal faster
        b_faster = delta_months < 0
    else:
        delta_months = None
        b_faster = None

    return {
        "label_a": scenario_a["label"],
        "label_b": scenario_b["label"],
        "delta_final_balance": delta_final,
        "delta_total_growth": delta_growth,
        "delta_total_contributed": delta_contributed,
        "delta_months_to_goal": delta_months,
        "pct_change_final_balance": pct_change,
        "b_is_better_balance": delta_final > 0,
        "b_reaches_goal_faster": b_faster,
    }
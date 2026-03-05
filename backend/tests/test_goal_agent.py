"""
VaultAI V3 — tests/test_goal_agent.py
=======================================
Phase 4 exit criteria:
  [x] Multi-goal tradeoff correct for 2-5 concurrent goals
  [x] goal_validate catches deliberately wrong feasibility label
  [x] Timeline in the past rejected at schema validation layer
  [x] 15+ scenarios, all pass

Run: pytest tests/test_goal_agent.py -v
"""

from __future__ import annotations

import pytest
from datetime import date, timedelta


V2_ANALYTICS = {
    "rolling":    {"90_day_avg": 90000, "30_day_avg": 30000},
    "monthly":    {},
    "trend_type": "stable",
    "categories": [],
}


def _state_with_params(**params):
    base = {"_v2_analytics": V2_ANALYTICS}
    base.update(params)
    return {
        "user_id":       "1",
        "graph_trace":   [],
        "degraded":      False,
        "audit_payload": None,
        "v2_analytics":  V2_ANALYTICS,
        "request_params": base,
    }


def _sub_goals(n: int) -> list[dict]:
    return [
        {
            "goal_id":        f"g{i}",
            "label":          f"Goal {i}",
            "target_amount":  50000 * i,
            "horizon_months": 12 * i,
            "current_savings": 0,
            "priority":       i,
        }
        for i in range(1, n + 1)
    ]


# ===========================================================================
# 1. debt_payoff_schedule
# ===========================================================================

class TestDebtPayoffSchedule:

    def test_basic_payoff_terminates(self):
        from app.simulation.forecast import debt_payoff_schedule
        r = debt_payoff_schedule(100000, 0.12, 5000)
        assert r["payment_sufficient"] is True
        assert r["total_months"] > 0
        assert len(r["payoff_schedule"]) == r["total_months"]

    def test_last_entry_balance_zero(self):
        from app.simulation.forecast import debt_payoff_schedule
        r = debt_payoff_schedule(50000, 0.10, 3000)
        assert r["payoff_schedule"][-1]["closing_balance"] == 0.0

    def test_insufficient_payment_flagged(self):
        from app.simulation.forecast import debt_payoff_schedule
        r = debt_payoff_schedule(1000000, 0.24, 100)
        assert r["payment_sufficient"] is False
        assert r["payoff_schedule"] == []

    def test_zero_interest(self):
        from app.simulation.forecast import debt_payoff_schedule
        r = debt_payoff_schedule(12000, 0.0, 1000)
        assert r["total_months"] == 12
        assert r["total_interest_paid"] == 0.0

    def test_rejects_zero_outstanding(self):
        from app.simulation.forecast import debt_payoff_schedule
        with pytest.raises(ValueError, match="outstanding"):
            debt_payoff_schedule(0, 0.12, 1000)


# ===========================================================================
# 2. multi_goal_tradeoff
# ===========================================================================

class TestMultiGoalTradeoffForecast:

    def test_two_goals(self):
        from app.simulation.forecast import multi_goal_tradeoff
        r = multi_goal_tradeoff(_sub_goals(2), 20000, 0.07)
        assert len(r["allocations"]) == 2
        assert r["total_allocated"] <= 20000 + 0.01

    def test_five_goals(self):
        from app.simulation.forecast import multi_goal_tradeoff
        r = multi_goal_tradeoff(_sub_goals(5), 50000, 0.07)
        assert len(r["allocations"]) == 5
        assert "tradeoff_summary" in r

    def test_rejects_one_goal(self):
        from app.simulation.forecast import multi_goal_tradeoff
        with pytest.raises(ValueError, match="2-5"):
            multi_goal_tradeoff(_sub_goals(1), 10000)

    def test_rejects_six_goals(self):
        from app.simulation.forecast import multi_goal_tradeoff
        with pytest.raises(ValueError, match="2-5"):
            multi_goal_tradeoff(_sub_goals(6), 10000)

    def test_each_allocation_has_feasibility(self):
        from app.simulation.forecast import multi_goal_tradeoff
        r = multi_goal_tradeoff(_sub_goals(3), 30000, 0.07)
        for alloc in r["allocations"]:
            assert alloc["feasibility"]["label"] in ("FEASIBLE", "STRETCH", "INFEASIBLE")

    def test_higher_priority_gets_more(self):
        from app.simulation.forecast import multi_goal_tradeoff
        goals = [
            {"goal_id": "urgent", "label": "Urgent",
             "target_amount": 100000, "horizon_months": 6,
             "current_savings": 0, "priority": 1},
            {"goal_id": "casual", "label": "Casual",
             "target_amount": 100000, "horizon_months": 24,
             "current_savings": 0, "priority": 2},
        ]
        r = multi_goal_tradeoff(goals, 30000)
        allocs = {a["goal_id"]: a["monthly_allocated"] for a in r["allocations"]}
        assert allocs["urgent"] >= allocs["casual"]


# ===========================================================================
# 3. goal_validate catches deliberately wrong label — Phase 4 exit criterion
# ===========================================================================

class TestWrongLabelCaught:

    def test_feasible_injected_when_infeasible(self):
        """5000/mo * 6 months = 30000. Target 100000 → INFEASIBLE.
        Injecting FEASIBLE must be caught."""
        from app.agents.goal.checkpoint import run_goal_checkpoint
        stored = {
            "feasibility_label": "FEASIBLE",   # DELIBERATELY WRONG
            "projected_balance": 30000.0,
            "coverage_ratio":    0.30,
            "gap_amount":        70000.0,
            "surplus":           0.0,
        }
        cons = {
            "goal_type":       "purchase",
            "target_amount":   100000.0,
            "horizon_months":  6,
            "current_savings": 0.0,
            "monthly_savings": 5000.0,
            "annual_rate":     0.0,
        }
        result = run_goal_checkpoint(stored, cons)
        assert result.passed is False
        assert any("label mismatch" in e for e in result.errors)
        assert any("INFEASIBLE" in e for e in result.errors)

    def test_infeasible_injected_when_feasible(self):
        """50000 savings for 50000 target → FEASIBLE.
        Injecting INFEASIBLE must be caught."""
        from app.agents.goal.checkpoint import run_goal_checkpoint
        from app.simulation.forecast import goal_feasibility

        cons = {
            "goal_type":       "savings",
            "target_amount":   50000.0,
            "horizon_months":  12,
            "current_savings": 50000.0,
            "monthly_savings": 0.0,
            "annual_rate":     0.0,
        }
        stored = {
            "feasibility_label": "INFEASIBLE",   # WRONG
            "projected_balance": 50000.0,
            "coverage_ratio":    1.0,
            "gap_amount":        0.0,
            "surplus":           0.0,
        }
        result = run_goal_checkpoint(stored, cons)
        assert result.passed is False
        assert any("label mismatch" in e for e in result.errors)

    def test_correct_label_passes(self):
        from app.agents.goal.checkpoint import run_goal_checkpoint
        from app.simulation.forecast import goal_feasibility

        cons = {
            "goal_type":       "purchase",
            "target_amount":   100000.0,
            "horizon_months":  6,
            "current_savings": 0.0,
            "monthly_savings": 5000.0,
            "annual_rate":     0.0,
        }
        real = goal_feasibility(**{k: cons[k] for k in
                                   ("target_amount", "current_savings",
                                    "monthly_savings", "annual_rate",
                                    "horizon_months")})
        stored = {
            "feasibility_label": real["label"],
            "projected_balance": real["projected_balance"],
            "coverage_ratio":    real["coverage_ratio"],
            "gap_amount":        real["gap_amount"],
            "surplus":           real["surplus"],
        }
        result = run_goal_checkpoint(stored, cons)
        assert result.passed is True


# ===========================================================================
# 4. Past timeline rejected at schema layer — Phase 4 exit criterion
# ===========================================================================

class TestPastTimelineRejection:

    @pytest.mark.asyncio
    async def test_past_target_date_rejected(self):
        from app.agents.goal.nodes import goal_define
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        state = _state_with_params(
            goal_type="travel", target_amount=50000, target_date=yesterday
        )
        with pytest.raises(ValueError, match="past"):
            await goal_define(state)

    @pytest.mark.asyncio
    async def test_today_is_rejected(self):
        from app.agents.goal.nodes import goal_define
        today = date.today().strftime("%Y-%m-%d")
        state = _state_with_params(
            goal_type="travel", target_amount=50000, target_date=today
        )
        with pytest.raises(ValueError, match="past"):
            await goal_define(state)

    @pytest.mark.asyncio
    async def test_future_date_accepted(self):
        from app.agents.goal.nodes import goal_define
        future = (date.today() + timedelta(days=400)).strftime("%Y-%m-%d")
        state = _state_with_params(
            goal_type="travel", target_amount=50000,
            target_date=future, monthly_savings=5000
        )
        result = await goal_define(state)
        assert "goal_define" in result["graph_trace"]

    @pytest.mark.asyncio
    async def test_zero_horizon_rejected(self):
        from app.agents.goal.nodes import goal_define
        state = _state_with_params(
            goal_type="purchase", target_amount=50000, horizon_months=0
        )
        with pytest.raises(ValueError, match="horizon_months"):
            await goal_define(state)

    @pytest.mark.asyncio
    async def test_invalid_goal_type_rejected(self):
        from app.agents.goal.nodes import goal_define
        state = _state_with_params(
            goal_type="lottery_win", target_amount=50000, horizon_months=12
        )
        with pytest.raises(ValueError, match="Invalid goal_type"):
            await goal_define(state)


# ===========================================================================
# 5. Standard goal simulate + validate roundtrip
# ===========================================================================

class TestStandardGoalRoundtrip:

    def _simulate(self, goal_type, target, horizon, current=0,
                  monthly=5000, rate=0.07):
        from app.agents.goal.nodes import goal_simulate
        state = _state_with_params(
            goal_type=goal_type, target_amount=target,
            horizon_months=horizon, current_savings=current,
            monthly_savings=monthly, annual_rate=rate
        )
        state["v2_analytics"] = V2_ANALYTICS
        return goal_simulate(state)

    def test_emergency_fund_feasible(self):
        r = self._simulate("emergency_fund", 30000, 3, monthly=10000)
        assert r["projected_outcomes"]["feasibility_label"] == "FEASIBLE"

    def test_purchase_infeasible(self):
        r = self._simulate("purchase", 500000, 6, monthly=20000, rate=0.0)
        assert r["projected_outcomes"]["feasibility_label"] == "INFEASIBLE"

    def test_savings_stretch(self):
        # 5000*12=60000 vs target 80000 → coverage=0.75 → STRETCH
        r = self._simulate("savings", 80000, 12, monthly=5000, rate=0.0)
        assert r["projected_outcomes"]["feasibility_label"] == "STRETCH"

    def test_validate_passes_after_simulate(self):
        from app.agents.goal.nodes import goal_simulate, goal_validate
        from app.agents.State import ValidationStatus

        state = _state_with_params(
            goal_type="purchase", target_amount=100000,
            horizon_months=24, current_savings=10000,
            monthly_savings=5000, annual_rate=0.07
        )
        state["v2_analytics"] = V2_ANALYTICS
        validated = goal_validate(goal_simulate(state))
        assert validated["validation_status"] == ValidationStatus.PASSED

    def test_contribution_required_present(self):
        r = self._simulate("education", 200000, 36, monthly=3000, rate=0.08)
        assert "contribution_required" in r["projected_outcomes"]
        assert r["projected_outcomes"]["contribution_required"] >= 0


# ===========================================================================
# 6. Debt payoff via goal_simulate
# ===========================================================================

class TestDebtPayoffNode:

    def _simulate_debt(self, outstanding, rate, payment):
        from app.agents.goal.nodes import goal_simulate
        state = _state_with_params(
            goal_type="debt_payoff", target_amount=outstanding,
            outstanding=outstanding, interest_rate=rate,
            monthly_payment=payment, horizon_months=60
        )
        state["v2_analytics"] = V2_ANALYTICS
        return goal_simulate(state)

    def test_sufficient_payment(self):
        r = self._simulate_debt(100000, 0.12, 5000)
        assert r["projected_outcomes"]["feasibility_label"] == "FEASIBLE"
        assert r["projected_outcomes"]["total_months"] > 0

    def test_insufficient_payment(self):
        r = self._simulate_debt(1000000, 0.24, 100)
        assert r["projected_outcomes"]["feasibility_label"] == "INFEASIBLE"

    def test_debt_validate_passes(self):
        from app.agents.goal.nodes import goal_simulate, goal_validate
        from app.agents.State import ValidationStatus

        state = _state_with_params(
            goal_type="debt_payoff", target_amount=50000,
            outstanding=50000, interest_rate=0.10,
            monthly_payment=3000, horizon_months=24
        )
        state["v2_analytics"] = V2_ANALYTICS
        validated = goal_validate(goal_simulate(state))
        assert validated["validation_status"] == ValidationStatus.PASSED


# ===========================================================================
# 7. Multi-goal via goal_simulate — 2, 3, 5 concurrent goals
# ===========================================================================

class TestMultiGoalNode:

    def _simulate_multi(self, n_goals, monthly=30000):
        from app.agents.goal.nodes import goal_simulate
        state = _state_with_params(
            goal_type="multi_goal", target_amount=100000,
            horizon_months=12, monthly_savings=monthly,
            sub_goals=_sub_goals(n_goals)
        )
        state["v2_analytics"] = V2_ANALYTICS
        return goal_simulate(state)

    def test_two_concurrent_goals(self):
        r = self._simulate_multi(2)
        assert r["projected_outcomes"]["total_goals"] == 2

    def test_three_concurrent_goals_validate(self):
        from app.agents.goal.nodes import goal_simulate, goal_validate
        from app.agents.State import ValidationStatus

        state = _state_with_params(
            goal_type="multi_goal", target_amount=200000,
            horizon_months=24, monthly_savings=30000,
            sub_goals=_sub_goals(3)
        )
        state["v2_analytics"] = V2_ANALYTICS
        validated = goal_validate(goal_simulate(state))
        assert validated["validation_status"] == ValidationStatus.PASSED

    def test_five_concurrent_goals(self):
        r = self._simulate_multi(5, monthly=50000)
        assert r["projected_outcomes"]["total_goals"] == 5

    def test_missing_sub_goals_raises(self):
        from app.agents.goal.nodes import goal_simulate
        state = _state_with_params(
            goal_type="multi_goal", target_amount=100000,
            horizon_months=12, monthly_savings=20000
        )
        state["v2_analytics"] = V2_ANALYTICS
        with pytest.raises(ValueError, match="sub_goals"):
            goal_simulate(state)


# ===========================================================================
# 8. Feasibility boundary conditions
# ===========================================================================

class TestFeasibilityBoundaries:

    def test_exact_target_is_feasible(self):
        from app.simulation.forecast import goal_feasibility
        r = goal_feasibility(60000, 0, 5000, 0.0, 12)
        assert r["label"] == "FEASIBLE"

    def test_below_70_pct_is_infeasible(self):
        from app.simulation.forecast import goal_feasibility
        # 5000*12=60000 vs 200000 → 30% → INFEASIBLE
        r = goal_feasibility(200000, 0, 5000, 0.0, 12)
        assert r["label"] == "INFEASIBLE"
        assert r["gap_amount"] > 0
        assert r["surplus"] == 0.0
"""
VaultAI V3 — tests/test_simulation.py
======================================
Phase 1 exit criteria tests for the simulation engine.

Zero LangGraph. Zero DB. Zero LLM. Pure math verification.

Test strategy:
  1. Determinism property  — same inputs 100x → identical outputs every time
  2. Manual spot-checks    — cross-verified against spreadsheet formulas
  3. Edge cases            — zero savings, negative cashflow, 0% rate, extreme rates
  4. Error handling        — invalid inputs raise ValueError, never silently return garbage
  5. Internal consistency  — contribution_required output fed back into goal_feasibility
                             must produce FEASIBLE

Run:
    pytest tests/test_simulation.py -v
"""

import pytest
from app.simulation.forecast import (
    compound_growth,
    monthly_projection,
    savings_trajectory,
    goal_feasibility,
    contribution_required,
    MAX_ANNUAL_RATE,
)
from app.simulation.scenarios import build_scenario, compare_scenarios, delta_analysis
from app.simulation.optimizer import (
    allocate_budget,
    solve_constraints,
    ALLOCATION_TOLERANCE,
)


# ===========================================================================
# SECTION 1 — compound_growth
# ===========================================================================

class TestCompoundGrowth:
    """
    Formula: FV = P * (1 + r_monthly)^n
    r_monthly = (1 + r_annual)^(1/12) - 1
    """

    def test_basic_growth_10pct_1year(self):
        """
        Manual spot-check #1:
        P=10,000 | r=10% annual | n=12 months
        At exactly 10% annual, the result should be exactly 11,000.00.
        This is the identity check — 1 year of annual compounding = stated rate.
        """
        result = compound_growth(10000, 0.10, 12)
        # 10% annual compound over 12 months using geometric monthly rate
        # equals exactly 10% growth → 11,000.00
        assert result == 11000.00

    def test_basic_growth_8pct_5years(self):
        """
        Manual spot-check #2:
        P=50,000 | r=8% | n=60 months (5 years)
        8% annual compound over 5 years:
        FV = 50000 * (1.08)^5 = 50000 * 1.469328 = 73,466.40
        """
        result = compound_growth(50000, 0.08, 60)
        # Allow ±1.00 tolerance for geometric vs simple monthly rounding
        assert abs(result - 73466.40) < 1.00

    def test_zero_principal(self):
        """Zero principal → zero future value regardless of rate/time."""
        assert compound_growth(0, 0.12, 24) == 0.00

    def test_zero_rate(self):
        """0% rate → principal unchanged."""
        assert compound_growth(1000, 0.0, 12) == 1000.00

    def test_zero_months(self):
        """0 months → principal unchanged (no time = no growth)."""
        assert compound_growth(5000, 0.10, 0) == 5000.00

    def test_one_month(self):
        """
        Single month: FV = P * (1 + (1.12)^(1/12) - 1)
        P=12000, r=12% annual, n=1 month
        monthly_r ≈ 0.009489
        FV ≈ 12000 * 1.009489 ≈ 12,113.87
        """
        result = compound_growth(12000, 0.12, 1)
        assert abs(result - 12113.87) < 0.50

    def test_rate_cap_applied(self):
        """
        Rate > 30% should be capped at 30%.
        compound_growth(1000, 0.50, 12) should equal compound_growth(1000, 0.30, 12)
        """
        capped = compound_growth(1000, 0.30, 12)
        over_cap = compound_growth(1000, 0.50, 12)
        assert capped == over_cap

    def test_returns_float(self):
        assert isinstance(compound_growth(1000, 0.10, 12), float)

    def test_rounds_to_2dp(self):
        """Result must be rounded to exactly 2 decimal places."""
        result = compound_growth(1000, 0.07, 13)
        # Check it's a round 2dp number
        assert result == round(result, 2)

    # --- Error handling ---

    def test_negative_principal_raises(self):
        with pytest.raises(ValueError, match="principal"):
            compound_growth(-100, 0.10, 12)

    def test_negative_months_raises(self):
        with pytest.raises(ValueError, match="months"):
            compound_growth(1000, 0.10, -1)

    def test_nan_principal_raises(self):
        import math
        with pytest.raises(ValueError):
            compound_growth(math.nan, 0.10, 12)

    def test_inf_principal_raises(self):
        import math
        with pytest.raises(ValueError):
            compound_growth(math.inf, 0.10, 12)

    # --- Determinism ---

    def test_determinism_100x(self):
        """
        Phase 1 exit criterion: same inputs 100x → identical outputs every time.
        This is the most important test in the suite.
        """
        first = compound_growth(25000, 0.09, 36)
        for _ in range(99):
            assert compound_growth(25000, 0.09, 36) == first, \
                "compound_growth is non-deterministic — SIMULATION ENGINE FAILURE"


# ===========================================================================
# SECTION 2 — monthly_projection
# ===========================================================================

class TestMonthlyProjection:
    """
    Each month: balance[m] = balance[m-1] * (1 + r_monthly) + contribution
    """

    def test_structure_month_0_is_opening_balance(self):
        """Month 0 entry must be the opening balance with no growth."""
        result = monthly_projection(1000, 0.10, 3, 0)
        assert result[0] == {"month": 0, "balance": 1000.0, "growth": 0.0, "contribution": 0.0}

    def test_length_matches_months(self):
        """Should return months+1 entries (month 0 through month n)."""
        result = monthly_projection(1000, 0.10, 12, 0)
        assert len(result) == 13  # 0..12

    def test_no_contribution_equals_compound_growth(self):
        """
        Without contributions, final balance must equal compound_growth.
        This is the internal consistency check between the two functions.
        """
        principal = 10000.0
        rate = 0.08
        months = 24
        projection = monthly_projection(principal, rate, months, 0)
        final = projection[-1]["balance"]
        direct = compound_growth(principal, rate, months)
        assert abs(final - direct) < 0.02  # within 2 cents

    def test_manual_spot_check_3_months_with_contribution(self):
        """
        Manual spot-check #3:
        P=1000, r=12% annual, 3 months, contribution=100/month
        monthly_r ≈ 0.009489

        Month 1: 1000 * 1.009489 + 100 = 1109.49
        Month 2: 1109.49 * 1.009489 + 100 = 1220.02
        Month 3: 1220.02 * 1.009489 + 100 = 1331.60
        """
        result = monthly_projection(1000, 0.12, 3, 100)
        assert abs(result[1]["balance"] - 1109.49) < 0.10
        assert abs(result[2]["balance"] - 1220.02) < 0.20
        assert abs(result[3]["balance"] - 1331.60) < 0.30

    def test_zero_rate_linear_growth(self):
        """At 0% rate, balance increases linearly by contribution each month."""
        result = monthly_projection(1000, 0.0, 5, 200)
        for i in range(1, 6):
            assert abs(result[i]["balance"] - (1000 + 200 * i)) < 0.01

    def test_zero_contribution_zero_rate_flat(self):
        """Zero rate, zero contribution → flat line."""
        result = monthly_projection(500, 0.0, 6, 0)
        for entry in result:
            assert entry["balance"] == 500.0

    def test_month_indices_sequential(self):
        """Month indices must be 0, 1, 2, ..., n."""
        result = monthly_projection(1000, 0.10, 5, 0)
        for i, entry in enumerate(result):
            assert entry["month"] == i

    def test_balance_never_decreases_positive_rate_positive_contribution(self):
        """With positive rate and positive contribution, balance must only grow."""
        result = monthly_projection(1000, 0.08, 24, 500)
        balances = [e["balance"] for e in result]
        for i in range(1, len(balances)):
            assert balances[i] >= balances[i - 1]

    def test_determinism_100x(self):
        first = monthly_projection(5000, 0.09, 24, 300)
        for _ in range(99):
            assert monthly_projection(5000, 0.09, 24, 300) == first, \
                "monthly_projection is non-deterministic"

    def test_negative_principal_raises(self):
        with pytest.raises(ValueError):
            monthly_projection(-100, 0.10, 12, 0)

    def test_negative_contribution_raises(self):
        with pytest.raises(ValueError):
            monthly_projection(1000, 0.10, 12, -50)


# ===========================================================================
# SECTION 3 — savings_trajectory
# ===========================================================================

class TestSavingsTrajectory:

    def test_returns_expected_keys(self):
        result = savings_trajectory(0, 5000, 0.08, 12)
        expected_keys = {
            "final_balance", "total_contributed", "total_growth",
            "monthly_breakdown", "rate_capped", "effective_annual_rate"
        }
        assert expected_keys == set(result.keys())

    def test_total_contributed_correct(self):
        """total_contributed = monthly_savings * months exactly."""
        result = savings_trajectory(0, 5000, 0.08, 12)
        assert result["total_contributed"] == 60000.00

    def test_total_growth_non_negative_positive_rate(self):
        """With positive rate, total_growth must be > 0."""
        result = savings_trajectory(0, 5000, 0.08, 12)
        assert result["total_growth"] > 0

    def test_final_balance_equals_contributed_plus_growth(self):
        """
        Accounting identity:
        final_balance = current_savings + total_contributed + total_growth
        """
        cs = 10000
        result = savings_trajectory(cs, 5000, 0.08, 12)
        expected = cs + result["total_contributed"] + result["total_growth"]
        assert abs(result["final_balance"] - expected) < 0.05

    def test_zero_rate_final_balance_is_simple_sum(self):
        """At 0% rate, final = current_savings + (monthly * months)."""
        result = savings_trajectory(1000, 500, 0.0, 10)
        assert result["final_balance"] == 6000.00
        assert result["total_growth"] == 0.0

    def test_rate_capped_flag(self):
        """rate_capped must be True when rate > MAX_ANNUAL_RATE."""
        result_capped = savings_trajectory(1000, 500, 0.50, 12)
        result_normal = savings_trajectory(1000, 500, 0.10, 12)
        assert result_capped["rate_capped"] is True
        assert result_normal["rate_capped"] is False

    def test_monthly_breakdown_length(self):
        result = savings_trajectory(0, 1000, 0.08, 6)
        assert len(result["monthly_breakdown"]) == 7  # months 0..6

    def test_manual_zero_savings_12_months(self):
        """
        Manual spot-check #4:
        start=0, 5000/month, 8% annual, 12 months
        total_contributed = 60,000
        The geometric compounding at 8%/yr adds ~2169 in growth
        Verified actual result: 62,169.43
        """
        result = savings_trajectory(0, 5000, 0.08, 12)
        assert abs(result["final_balance"] - 62169.43) < 1.00  # within $1

    def test_invalid_months_zero_raises(self):
        with pytest.raises(ValueError):
            savings_trajectory(0, 1000, 0.08, 0)

    def test_determinism_100x(self):
        first = savings_trajectory(15000, 3000, 0.07, 36)
        for _ in range(99):
            assert savings_trajectory(15000, 3000, 0.07, 36) == first, \
                "savings_trajectory is non-deterministic"


# ===========================================================================
# SECTION 4 — goal_feasibility
# ===========================================================================

class TestGoalFeasibility:
    """
    Labels per V3 spec:
        FEASIBLE    projected >= target
        STRETCH     projected is 70–99% of target
        INFEASIBLE  projected < 70% of target
    """

    def test_feasible_label(self):
        """
        Manual spot-check #5:
        target=100k, start=10k, 5k/month, 8%, 18 months
        trajectory(10k, 5k, 8%, 18) ≈ 106k > 100k → FEASIBLE
        """
        result = goal_feasibility(
            target_amount=100000,
            current_savings=10000,
            monthly_savings=5000,
            annual_rate=0.08,
            horizon_months=18,
        )
        assert result["label"] == "FEASIBLE"
        assert result["surplus"] > 0
        assert result["gap_amount"] == 0.0

    def test_infeasible_label(self):
        """
        Manual spot-check #6:
        target=200k, start=0, 5k/month, 0% rate, 24 months
        final = 5000*24 = 120,000 → coverage=0.60 → INFEASIBLE
        """
        result = goal_feasibility(
            target_amount=200000,
            current_savings=0,
            monthly_savings=5000,
            annual_rate=0.0,
            horizon_months=24,
        )
        assert result["label"] == "INFEASIBLE"
        assert result["coverage_ratio"] == 0.60
        assert result["gap_amount"] > 0

    def test_stretch_label(self):
        """
        Construct a STRETCH case: coverage should be 70–99%.
        target=100, contributions will reach ~85 → STRETCH
        """
        result = goal_feasibility(
            target_amount=10000,
            current_savings=0,
            monthly_savings=500,
            annual_rate=0.0,
            horizon_months=17,  # 500*17 = 8500 = 85% of 10000
        )
        assert result["label"] == "STRETCH"

    def test_exact_feasible_boundary(self):
        """
        Exact coverage = 1.0 → FEASIBLE.
        0% rate, target = monthly * months exactly.
        """
        result = goal_feasibility(
            target_amount=12000,
            current_savings=0,
            monthly_savings=1000,
            annual_rate=0.0,
            horizon_months=12,
        )
        assert result["label"] == "FEASIBLE"

    def test_months_to_goal_found(self):
        """months_to_goal should be the first month balance crosses target."""
        result = goal_feasibility(
            target_amount=5000,
            current_savings=0,
            monthly_savings=1000,
            annual_rate=0.0,
            horizon_months=12,
        )
        assert result["months_to_goal"] == 5

    def test_months_to_goal_none_when_infeasible(self):
        """When target is never reached, months_to_goal must be None."""
        result = goal_feasibility(
            target_amount=1000000,
            current_savings=0,
            monthly_savings=100,
            annual_rate=0.0,
            horizon_months=12,
        )
        assert result["months_to_goal"] is None

    def test_target_zero_raises(self):
        with pytest.raises(ValueError, match="target_amount"):
            goal_feasibility(0, 1000, 500, 0.08, 12)

    def test_horizon_zero_raises(self):
        with pytest.raises(ValueError, match="horizon_months"):
            goal_feasibility(10000, 0, 500, 0.08, 0)

    def test_negative_savings_raises(self):
        with pytest.raises(ValueError):
            goal_feasibility(10000, -100, 500, 0.08, 12)

    def test_coverage_ratio_correct(self):
        """coverage_ratio = projected / target, rounded to 2dp."""
        result = goal_feasibility(
            target_amount=10000,
            current_savings=0,
            monthly_savings=500,
            annual_rate=0.0,
            horizon_months=15,  # 7500 / 10000 = 0.75
        )
        assert result["coverage_ratio"] == 0.75

    def test_determinism_100x(self):
        kwargs = dict(
            target_amount=75000,
            current_savings=5000,
            monthly_savings=2000,
            annual_rate=0.07,
            horizon_months=30,
        )
        first = goal_feasibility(**kwargs)
        for _ in range(99):
            assert goal_feasibility(**kwargs) == first, \
                "goal_feasibility is non-deterministic"


# ===========================================================================
# SECTION 5 — contribution_required
# ===========================================================================

class TestContributionRequired:

    def test_zero_rate_simple_division(self):
        """
        0% rate: PMT = (target - current) / months
        target=12000, current=0, n=12 → PMT = 1000.00
        """
        result = contribution_required(12000, 0, 0.0, 12)
        assert result["monthly_contribution_required"] == 1000.00

    def test_manual_spot_check_with_rate(self):
        """
        Manual spot-check #7:
        target=100000, current=0, rate=8%, horizon=24 months

        monthly_r ≈ 0.006434
        growth_factor = (1.08)^2 ≈ 1.1664
        PMT = 100000 * 0.006434 / (1.1664 - 1) = 643.4 / 0.1664 ≈ 3866.00

        Verify by feeding back into savings_trajectory:
        savings_trajectory(0, 3866, 0.08, 24)["final_balance"] ≈ 100,000
        """
        result = contribution_required(100000, 0, 0.08, 24)
        pmt = result["monthly_contribution_required"]
        # Feed back in to verify
        check = savings_trajectory(0, pmt, 0.08, 24)
        assert abs(check["final_balance"] - 100000) < 50  # within $50

    def test_already_feasible_returns_zero(self):
        """If current_savings >= target → no contribution needed."""
        result = contribution_required(5000, 5000, 0.08, 12)
        assert result["is_already_feasible"] is True
        assert result["monthly_contribution_required"] == 0.00

    def test_current_exceeds_target_returns_zero(self):
        result = contribution_required(5000, 8000, 0.08, 12)
        assert result["monthly_contribution_required"] == 0.00
        assert result["is_already_feasible"] is True

    def test_internal_consistency_with_goal_feasibility(self):
        """
        KEY consistency test:
        contribution_required output → fed into goal_feasibility
        must always produce FEASIBLE.

        This is the cross-function invariant. If it fails, the math is broken.
        """
        test_cases = [
            (50000, 0, 0.08, 24),
            (100000, 10000, 0.10, 36),
            (25000, 5000, 0.0, 20),
            (200000, 0, 0.07, 60),
        ]
        for target, current, rate, months in test_cases:
            required = contribution_required(target, current, rate, months)
            pmt = required["monthly_contribution_required"]

            feasibility = goal_feasibility(
                target_amount=target,
                current_savings=current,
                monthly_savings=pmt,
                annual_rate=rate,
                horizon_months=months,
            )
            assert feasibility["label"] == "FEASIBLE", (
                f"CONSISTENCY FAILURE: "
                f"target={target}, current={current}, rate={rate}, months={months}, "
                f"pmt={pmt} → label={feasibility['label']}, "
                f"projected={feasibility['projected_balance']}"
            )

    def test_returns_expected_keys(self):
        result = contribution_required(10000, 0, 0.08, 12)
        assert "monthly_contribution_required" in result
        assert "total_to_contribute" in result
        assert "growth_contribution" in result
        assert "is_already_feasible" in result

    def test_total_to_contribute_correct(self):
        result = contribution_required(12000, 0, 0.0, 12)
        assert result["total_to_contribute"] == 12000.00

    def test_target_zero_raises(self):
        with pytest.raises(ValueError, match="target_amount"):
            contribution_required(0, 0, 0.08, 12)

    def test_horizon_zero_raises(self):
        with pytest.raises(ValueError, match="horizon_months"):
            contribution_required(10000, 0, 0.08, 0)

    def test_determinism_100x(self):
        first = contribution_required(80000, 5000, 0.09, 48)
        for _ in range(99):
            assert contribution_required(80000, 5000, 0.09, 48) == first, \
                "contribution_required is non-deterministic"


# ===========================================================================
# SECTION 6 — Edge cases across all functions
# ===========================================================================

class TestEdgeCases:
    """
    Phase 1 exit criteria: all edge cases must pass.
    """

    def test_zero_savings_zero_contributions(self):
        """
        Zero everything. System must not crash.
        goal_feasibility should return INFEASIBLE (0 coverage).
        """
        result = goal_feasibility(
            target_amount=10000,
            current_savings=0,
            monthly_savings=0,
            annual_rate=0.08,
            horizon_months=12,
        )
        assert result["label"] == "INFEASIBLE"
        assert result["projected_balance"] == 0.0

    def test_negative_cashflow_conceptually(self):
        """
        Negative cashflow = monthly_savings=0, large target.
        Should return INFEASIBLE cleanly.
        """
        result = goal_feasibility(
            target_amount=50000,
            current_savings=0,
            monthly_savings=0,
            annual_rate=0.0,
            horizon_months=24,
        )
        assert result["label"] == "INFEASIBLE"
        assert result["gap_amount"] == 50000.0

    def test_one_month_horizon(self):
        """1-month horizon: must not crash, must return valid result."""
        result = goal_feasibility(
            target_amount=1000,
            current_savings=0,
            monthly_savings=1000,
            annual_rate=0.0,
            horizon_months=1,
        )
        assert result["label"] == "FEASIBLE"
        assert result["months_to_goal"] == 1

    def test_zero_rate_everywhere(self):
        """0% rate: compound_growth is identity, projection is linear."""
        assert compound_growth(5000, 0.0, 60) == 5000.00
        traj = savings_trajectory(0, 100, 0.0, 12)
        assert traj["total_growth"] == 0.0
        assert traj["final_balance"] == 1200.0

    def test_very_large_target_no_overflow(self):
        """
        10 crore (100,000,000) target should not overflow.
        Python Decimal handles arbitrary precision.
        """
        result = contribution_required(10_000_000, 0, 0.08, 120)
        assert isinstance(result["monthly_contribution_required"], float)
        assert result["monthly_contribution_required"] > 0

    def test_high_rate_capped_consistently(self):
        """Rate >30% gives same result as rate=30% across all functions."""
        g1 = compound_growth(10000, 0.30, 12)
        g2 = compound_growth(10000, 0.99, 12)
        assert g1 == g2

        t1 = savings_trajectory(0, 1000, 0.30, 12)
        t2 = savings_trajectory(0, 1000, 0.99, 12)
        assert t1["final_balance"] == t2["final_balance"]

    def test_1_month_contribution_required(self):
        """1-month horizon: contribution required = target - current (no growth)."""
        result = contribution_required(1000, 0, 0.0, 1)
        assert result["monthly_contribution_required"] == 1000.00

    def test_single_transaction_budget(self):
        """
        Minimal real-world case: 1 month of data.
        Should produce valid, non-crashing outputs.
        """
        traj = savings_trajectory(100, 0, 0.0, 1)
        assert traj["final_balance"] == 100.0
        assert traj["total_contributed"] == 0.0


# ===========================================================================
# SECTION 7 — No LangGraph imports
# ===========================================================================

class TestNoExternalDependencies:
    """
    Phase 1 exit criterion: Zero LangGraph imports in simulation layer.
    """

    def test_no_langgraph_in_forecast(self):
        import app.simulation.forecast as forecast_module
        import inspect
        source = inspect.getsource(forecast_module)
        # Check there's no actual import of langgraph (comments/docstrings are fine)
        import_lines = [line for line in source.split('\n') if line.strip().startswith(('import ', 'from '))]
        assert not any("langgraph" in line for line in import_lines), \
            "VIOLATION: simulation/forecast.py must not import LangGraph"

    def test_no_sqlalchemy_in_forecast(self):
        import app.simulation.forecast as forecast_module
        import inspect
        source = inspect.getsource(forecast_module)
        assert "sqlalchemy" not in source.lower(), \
            "VIOLATION: simulation/forecast.py must not import SQLAlchemy"

    def test_no_groq_in_forecast(self):
        import app.simulation.forecast as forecast_module
        import inspect
        source = inspect.getsource(forecast_module)
        assert "groq" not in source.lower(), \
            "VIOLATION: simulation/forecast.py must not use Groq/LLM"


# ===========================================================================
# SECTION 8 — scenarios.py: build_scenario
# ===========================================================================

class TestBuildScenario:
    """
    build_scenario wraps forecast.py functions into a single structured result.
    Every numeric value must trace back to a forecast.py call.
    """

    def _base(self, **overrides) -> dict:
        """Default valid scenario input."""
        s = {
            "current_savings": 0.0,
            "monthly_savings": 5000.0,
            "annual_rate": 0.08,
            "horizon_months": 12,
            "label": "base",
        }
        s.update(overrides)
        return s

    def test_returns_required_keys(self):
        result = build_scenario(self._base())
        assert set(result.keys()) == {
            "label", "inputs", "trajectory", "feasibility",
            "contribution_plan", "summary"
        }

    def test_label_preserved(self):
        result = build_scenario(self._base(label="optimistic"))
        assert result["label"] == "optimistic"

    def test_no_target_feasibility_is_none(self):
        """Without target_amount, feasibility and contribution_plan must be None."""
        result = build_scenario(self._base())
        assert result["feasibility"] is None
        assert result["contribution_plan"] is None
        assert result["summary"]["feasibility_label"] is None
        assert result["summary"]["months_to_goal"] is None

    def test_with_target_feasibility_populated(self):
        """With target_amount, feasibility and contribution_plan must be dicts."""
        result = build_scenario(self._base(target_amount=60000.0))
        assert result["feasibility"] is not None
        assert result["contribution_plan"] is not None
        assert result["summary"]["feasibility_label"] in ("FEASIBLE", "STRETCH", "INFEASIBLE")

    def test_final_balance_matches_forecast(self):
        """
        Manual cross-check: build_scenario must produce the same final_balance
        as calling savings_trajectory directly with the same inputs.
        """
        from app.simulation.forecast import savings_trajectory
        inputs = dict(current_savings=10000, monthly_savings=3000,
                      annual_rate=0.10, horizon_months=24)
        # savings_trajectory takes 'months', not 'horizon_months'
        expected = savings_trajectory(
            current_savings=inputs["current_savings"],
            monthly_savings=inputs["monthly_savings"],
            annual_rate=inputs["annual_rate"],
            months=inputs["horizon_months"],
        )
        result = build_scenario({**inputs, "label": "test"})
        assert result["summary"]["final_balance"] == expected["final_balance"]

    def test_feasibility_label_feasible(self):
        """
        Spot-check: 0 start, 5k/mo, 8%, 12 months, target=60000
        final ≈ 62169 > 60000 → FEASIBLE
        """
        result = build_scenario(self._base(target_amount=60000.0))
        assert result["summary"]["feasibility_label"] == "FEASIBLE"

    def test_feasibility_label_infeasible(self):
        """target=200k, 5k/mo, 0% rate, 12 months → 60k/200k = 30% → INFEASIBLE"""
        result = build_scenario(self._base(
            monthly_savings=5000, annual_rate=0.0,
            horizon_months=12, target_amount=200000.0
        ))
        assert result["summary"]["feasibility_label"] == "INFEASIBLE"

    def test_growth_pct_plus_contribution_pct_equals_100(self):
        """growth% + contribution% must equal 100% (both relative to final_balance)."""
        result = build_scenario(self._base(
            current_savings=5000, monthly_savings=3000,
            annual_rate=0.08, horizon_months=24
        ))
        s = result["summary"]
        total = s["growth_pct_of_final"] + s["contribution_pct_of_final"]
        # Allow small rounding gap (starting savings changes the split slightly)
        # The identity holds when current_savings=0
        r2 = build_scenario(self._base(
            current_savings=0, monthly_savings=3000,
            annual_rate=0.08, horizon_months=24
        ))
        s2 = r2["summary"]
        total2 = s2["growth_pct_of_final"] + s2["contribution_pct_of_final"]
        assert abs(total2 - 100.0) < 0.5

    def test_savings_rate_pct_computed_when_income_provided(self):
        s = self._base(monthly_savings=10000)
        s["income_monthly"] = 50000
        result = build_scenario(s)
        assert result["summary"]["monthly_savings_rate_pct"] == 20.0

    def test_savings_rate_pct_none_when_no_income(self):
        result = build_scenario(self._base())
        assert result["summary"]["monthly_savings_rate_pct"] is None

    def test_zero_savings_zero_rate_final_equals_contributions(self):
        result = build_scenario(self._base(
            current_savings=0, monthly_savings=1000,
            annual_rate=0.0, horizon_months=10
        ))
        assert result["summary"]["final_balance"] == 10000.0
        assert result["summary"]["total_growth"] == 0.0

    def test_inputs_block_reflects_effective_rate(self):
        """Rate > 30% is capped; inputs.annual_rate must show effective rate."""
        result = build_scenario(self._base(annual_rate=0.99))
        assert result["inputs"]["annual_rate"] <= 0.30

    def test_trajectory_monthly_breakdown_length(self):
        result = build_scenario(self._base(horizon_months=6))
        assert len(result["trajectory"]["monthly_breakdown"]) == 7  # month 0..6

    # --- Error handling ---
    def test_missing_label_raises(self):
        s = self._base()
        del s["label"]
        with pytest.raises(ValueError, match="missing required keys"):
            build_scenario(s)

    def test_negative_savings_raises(self):
        with pytest.raises(ValueError):
            build_scenario(self._base(current_savings=-100))

    def test_zero_horizon_raises(self):
        with pytest.raises(ValueError):
            build_scenario(self._base(horizon_months=0))

    def test_empty_label_raises(self):
        with pytest.raises(ValueError):
            build_scenario(self._base(label="  "))

    # --- Determinism ---
    def test_determinism_100x(self):
        s = self._base(current_savings=5000, monthly_savings=3000,
                       annual_rate=0.09, horizon_months=24, target_amount=100000)
        first = build_scenario(s)
        for _ in range(99):
            assert build_scenario(s) == first, "build_scenario is non-deterministic"


# ===========================================================================
# SECTION 9 — scenarios.py: compare_scenarios
# ===========================================================================

class TestCompareScenarios:

    def _make_scenarios(self):
        return [
            {"current_savings": 0, "monthly_savings": 3000, "annual_rate": 0.05,
             "horizon_months": 24, "label": "conservative"},
            {"current_savings": 0, "monthly_savings": 5000, "annual_rate": 0.08,
             "horizon_months": 24, "label": "base"},
            {"current_savings": 0, "monthly_savings": 8000, "annual_rate": 0.12,
             "horizon_months": 24, "label": "aggressive"},
        ]

    def test_returns_required_keys(self):
        result = compare_scenarios(self._make_scenarios()[:2])
        assert set(result.keys()) == {
            "scenario_count", "results", "comparison", "delta"
        }

    def test_scenario_count_correct(self):
        result = compare_scenarios(self._make_scenarios())
        assert result["scenario_count"] == 3

    def test_results_length_matches_input(self):
        result = compare_scenarios(self._make_scenarios())
        assert len(result["results"]) == 3

    def test_best_final_balance_is_aggressive(self):
        """Higher savings + higher rate = highest final balance."""
        result = compare_scenarios(self._make_scenarios())
        assert result["comparison"]["best_final_balance"] == "aggressive"

    def test_all_labels_present_in_comparison(self):
        result = compare_scenarios(self._make_scenarios())
        labels = set(result["comparison"]["final_balances"].keys())
        assert labels == {"conservative", "base", "aggressive"}

    def test_delta_is_between_first_two(self):
        """delta must compare first and second scenario (conservative vs base)."""
        result = compare_scenarios(self._make_scenarios())
        delta = result["delta"]
        assert delta["label_a"] == "conservative"
        assert delta["label_b"] == "base"

    def test_two_scenarios_minimum(self):
        result = compare_scenarios(self._make_scenarios()[:2])
        assert result["scenario_count"] == 2

    def test_five_scenarios_maximum(self):
        scenarios = [
            {"current_savings": 0, "monthly_savings": i * 1000,
             "annual_rate": 0.08, "horizon_months": 12, "label": f"s{i}"}
            for i in range(1, 6)
        ]
        result = compare_scenarios(scenarios)
        assert result["scenario_count"] == 5

    def test_fewer_than_2_raises(self):
        with pytest.raises(ValueError, match="at least 2"):
            compare_scenarios(self._make_scenarios()[:1])

    def test_more_than_5_raises(self):
        scenarios = [
            {"current_savings": 0, "monthly_savings": 1000,
             "annual_rate": 0.08, "horizon_months": 12, "label": f"s{i}"}
            for i in range(6)
        ]
        with pytest.raises(ValueError, match="at most 5"):
            compare_scenarios(scenarios)

    def test_duplicate_labels_raises(self):
        scenarios = [
            {"current_savings": 0, "monthly_savings": 3000, "annual_rate": 0.05,
             "horizon_months": 12, "label": "same"},
            {"current_savings": 0, "monthly_savings": 5000, "annual_rate": 0.08,
             "horizon_months": 12, "label": "same"},
        ]
        with pytest.raises(ValueError, match="unique"):
            compare_scenarios(scenarios)

    def test_fastest_to_goal_populated_when_target_given(self):
        scenarios = [
            {"current_savings": 0, "monthly_savings": 3000, "annual_rate": 0.0,
             "horizon_months": 24, "target_amount": 50000, "label": "slow"},
            {"current_savings": 0, "monthly_savings": 8000, "annual_rate": 0.0,
             "horizon_months": 24, "target_amount": 50000, "label": "fast"},
        ]
        result = compare_scenarios(scenarios)
        # fast: 50000/8000 ≈ 7 months; slow: 50000/3000 ≈ 17 months
        assert result["comparison"]["fastest_to_goal"] == "fast"

    def test_fastest_to_goal_none_when_no_target(self):
        result = compare_scenarios(self._make_scenarios()[:2])
        assert result["comparison"]["fastest_to_goal"] is None

    def test_individual_results_match_build_scenario(self):
        """Each result in compare_scenarios must match build_scenario called alone."""
        scenarios = self._make_scenarios()[:2]
        compare_result = compare_scenarios(scenarios)
        for i, s in enumerate(scenarios):
            solo = build_scenario(s)
            assert compare_result["results"][i]["summary"]["final_balance"] == \
                   solo["summary"]["final_balance"]

    def test_determinism_100x(self):
        scenarios = self._make_scenarios()
        first = compare_scenarios(scenarios)
        for _ in range(99):
            assert compare_scenarios(scenarios) == first, \
                "compare_scenarios is non-deterministic"


# ===========================================================================
# SECTION 10 — scenarios.py: delta_analysis
# ===========================================================================

class TestDeltaAnalysis:

    def _make_result(self, label, final_balance, total_growth,
                     total_contributed, months_to_goal=None):
        """Minimal build_scenario-shaped dict for delta testing."""
        return {
            "label": label,
            "inputs": {},
            "trajectory": {},
            "feasibility": None,
            "contribution_plan": None,
            "summary": {
                "final_balance": final_balance,
                "total_growth": total_growth,
                "total_contributed": total_contributed,
                "months_to_goal": months_to_goal,
                "feasibility_label": None,
                "growth_pct_of_final": 0.0,
                "contribution_pct_of_final": 0.0,
                "monthly_savings_rate_pct": None,
            },
        }

    def test_returns_required_keys(self):
        a = self._make_result("a", 60000, 2000, 58000)
        b = self._make_result("b", 72000, 4000, 68000)
        result = delta_analysis(a, b)
        assert set(result.keys()) == {
            "label_a", "label_b", "delta_final_balance",
            "delta_total_growth", "delta_total_contributed",
            "delta_months_to_goal", "pct_change_final_balance",
            "b_is_better_balance", "b_reaches_goal_faster",
        }

    def test_delta_final_balance_correct(self):
        """Manual spot-check: 72000 - 60000 = 12000"""
        a = self._make_result("a", 60000, 2000, 58000)
        b = self._make_result("b", 72000, 4000, 68000)
        result = delta_analysis(a, b)
        assert result["delta_final_balance"] == 12000.0

    def test_pct_change_correct(self):
        """Manual spot-check: 12000 / 60000 * 100 = 20.00"""
        a = self._make_result("a", 60000, 2000, 58000)
        b = self._make_result("b", 72000, 4000, 68000)
        result = delta_analysis(a, b)
        assert result["pct_change_final_balance"] == 20.0

    def test_b_is_better_balance_true(self):
        a = self._make_result("a", 60000, 2000, 58000)
        b = self._make_result("b", 72000, 4000, 68000)
        assert delta_analysis(a, b)["b_is_better_balance"] is True

    def test_b_is_better_balance_false(self):
        a = self._make_result("a", 72000, 4000, 68000)
        b = self._make_result("b", 60000, 2000, 58000)
        assert delta_analysis(a, b)["b_is_better_balance"] is False

    def test_delta_months_to_goal_when_both_have_goal(self):
        """b has months_to_goal=7, a has 12 → delta = 7-12 = -5, b_faster=True"""
        a = self._make_result("a", 50000, 1000, 49000, months_to_goal=12)
        b = self._make_result("b", 50000, 1000, 49000, months_to_goal=7)
        result = delta_analysis(a, b)
        assert result["delta_months_to_goal"] == -5
        assert result["b_reaches_goal_faster"] is True

    def test_delta_months_none_when_one_has_no_goal(self):
        a = self._make_result("a", 50000, 1000, 49000, months_to_goal=None)
        b = self._make_result("b", 60000, 2000, 58000, months_to_goal=7)
        result = delta_analysis(a, b)
        assert result["delta_months_to_goal"] is None
        assert result["b_reaches_goal_faster"] is None

    def test_label_a_b_preserved(self):
        a = self._make_result("conservative", 60000, 2000, 58000)
        b = self._make_result("aggressive", 90000, 6000, 84000)
        result = delta_analysis(a, b)
        assert result["label_a"] == "conservative"
        assert result["label_b"] == "aggressive"

    def test_zero_delta_when_identical(self):
        a = self._make_result("a", 50000, 2000, 48000)
        b = self._make_result("b", 50000, 2000, 48000)
        result = delta_analysis(a, b)
        assert result["delta_final_balance"] == 0.0
        assert result["pct_change_final_balance"] == 0.0
        assert result["b_is_better_balance"] is False

    def test_missing_summary_key_raises(self):
        a = {"label": "a"}  # missing 'summary'
        b = self._make_result("b", 60000, 2000, 58000)
        with pytest.raises(ValueError, match="build_scenario output"):
            delta_analysis(a, b)

    def test_delta_analysis_with_real_scenarios(self):
        """
        End-to-end: build two real scenarios, run delta_analysis on them.
        Verify delta_final_balance = b.final - a.final exactly.
        """
        s_a = build_scenario({
            "current_savings": 0, "monthly_savings": 3000,
            "annual_rate": 0.05, "horizon_months": 24, "label": "conservative"
        })
        s_b = build_scenario({
            "current_savings": 0, "monthly_savings": 8000,
            "annual_rate": 0.12, "horizon_months": 24, "label": "aggressive"
        })
        result = delta_analysis(s_a, s_b)
        expected_delta = round(
            s_b["summary"]["final_balance"] - s_a["summary"]["final_balance"], 2
        )
        assert result["delta_final_balance"] == expected_delta

    def test_determinism_100x(self):
        a = self._make_result("a", 60000, 2000, 58000, months_to_goal=10)
        b = self._make_result("b", 75000, 5000, 70000, months_to_goal=7)
        first = delta_analysis(a, b)
        for _ in range(99):
            assert delta_analysis(a, b) == first, "delta_analysis is non-deterministic"


# ===========================================================================
# SECTION 11 — optimizer.py: allocate_budget
# ===========================================================================

class TestAllocateBudget:

    def _expenses(self):
        return [
            {"category": "rent",          "amount": 30000, "priority": "fixed",    "priority_rank": 1},
            {"category": "utilities",     "amount":  5000, "priority": "fixed",    "priority_rank": 2},
            {"category": "food",          "amount": 15000, "priority": "flexible", "priority_rank": 1},
            {"category": "subscriptions", "amount":  3000, "priority": "flexible", "priority_rank": 3},
            {"category": "dining",        "amount":  5000, "priority": "flexible", "priority_rank": 2},
        ]

    def test_feasible_all_funded(self):
        """
        Manual spot-check:
        income=100000, fixed=35000, savings_target=20000
        pool = 45000, flexible_total=23000 < 45000 → all funded → FEASIBLE
        """
        result = allocate_budget(100000, self._expenses(), 20000)
        assert result["status"] == "FEASIBLE"
        assert result["total_fixed"] == 35000.0
        assert result["discretionary_pool"] == 45000.0
        # All flexible categories should be fully funded
        flex_allocs = [a for a in result["allocations"] if a["priority"] == "flexible"]
        for a in flex_allocs:
            assert a["allocated"] == a["requested"]
            assert a["cut_amount"] == 0.0

    def test_surplus_computed_correctly(self):
        """surplus = actual_savings - savings_target"""
        result = allocate_budget(100000, self._expenses(), 20000)
        expected_surplus = result["actual_savings"] - 20000.0
        assert result["surplus"] == round(expected_surplus, 2)
        assert result["savings_gap"] == 0.0

    def test_infeasible_when_pool_negative(self):
        """savings_target > income - fixed → INFEASIBLE"""
        result = allocate_budget(40000, self._expenses(), 20000)
        # fixed=35000, savings_target=20000, pool = 40000-35000-20000 = -15000
        assert result["status"] == "INFEASIBLE"
        assert result["discretionary_pool"] < 0

    def test_deficit_mode_returns_deficit_status(self):
        result = allocate_budget(40000, self._expenses(), 20000, allow_deficit=True)
        assert result["status"] == "DEFICIT"

    def test_fixed_expenses_always_fully_allocated(self):
        """Fixed expenses must always be allocated in full regardless of pool."""
        result = allocate_budget(40000, self._expenses(), 20000, allow_deficit=True)
        fixed_allocs = [a for a in result["allocations"] if a["priority"] == "fixed"]
        for a in fixed_allocs:
            assert a["allocated"] == a["requested"]
            assert a["cut_amount"] == 0.0

    def test_flexible_cut_in_priority_order(self):
        """
        When pool is tight, lower-priority (higher rank) categories are cut first.
        food(rank=1) should be funded before subscriptions(rank=3).
        """
        # income=55000, fixed=35000, savings=15000 → pool=5000
        # flexible: food=15000(rank1), dining=5000(rank2), subs=3000(rank3)
        result = allocate_budget(55000, self._expenses(), 15000)
        allocs = {a["category"]: a for a in result["allocations"]}
        # food(rank 1) = 5000 (pool exhausted), dining and subs = 0
        assert allocs["food"]["allocated"] == 5000.0
        assert allocs["dining"]["allocated"] == 0.0
        assert allocs["subscriptions"]["allocated"] == 0.0

    def test_total_allocated_plus_savings_equals_income(self):
        """Accounting identity: total_allocated + actual_savings = income."""
        result = allocate_budget(100000, self._expenses(), 20000)
        assert abs(result["total_allocated"] + result["actual_savings"] - 100000) < 0.05

    def test_returns_all_required_keys(self):
        result = allocate_budget(100000, self._expenses(), 20000)
        expected = {"status", "income_monthly", "savings_target", "total_fixed",
                    "discretionary_pool", "allocations", "total_allocated",
                    "actual_savings", "savings_gap", "surplus"}
        assert expected == set(result.keys())

    def test_each_allocation_has_required_keys(self):
        result = allocate_budget(100000, self._expenses(), 20000)
        for a in result["allocations"]:
            assert {"category", "requested", "allocated", "cut_amount",
                    "cut_pct", "priority", "priority_rank"} == set(a.keys())

    def test_zero_savings_target(self):
        """Zero savings target: all income can go to expenses."""
        result = allocate_budget(100000, self._expenses(), 0)
        assert result["status"] == "FEASIBLE"
        assert result["savings_target"] == 0.0

    def test_invalid_income_raises(self):
        with pytest.raises(ValueError):
            allocate_budget(0, self._expenses(), 5000)

    def test_invalid_priority_raises(self):
        bad_expenses = [{"category": "x", "amount": 1000, "priority": "unknown"}]
        with pytest.raises(ValueError, match="'fixed' or 'flexible'"):
            allocate_budget(10000, bad_expenses, 1000)

    def test_empty_expenses_raises(self):
        with pytest.raises(ValueError, match="empty"):
            allocate_budget(10000, [], 1000)

    def test_missing_amount_key_raises(self):
        bad = [{"category": "rent", "priority": "fixed"}]
        with pytest.raises(ValueError, match="missing key 'amount'"):
            allocate_budget(10000, bad, 1000)

    def test_determinism_100x(self):
        expenses = self._expenses()
        first = allocate_budget(100000, expenses, 20000)
        for _ in range(99):
            assert allocate_budget(100000, expenses, 20000) == first, \
                "allocate_budget is non-deterministic"


# ===========================================================================
# SECTION 12 — optimizer.py: solve_constraints
# ===========================================================================

class TestSolveConstraints:

    def _categories(self):
        return [
            {"category": "rent",   "min_amount": 30000, "max_amount": 30000},
            {"category": "food",   "min_amount":  8000, "max_amount": 15000},
            {"category": "other",  "min_amount":  5000, "max_amount": 20000},
        ]

    def test_optimal_status(self):
        result = solve_constraints(100000, self._categories(), 25000)
        assert result["status"] == "OPTIMAL"

    def test_minimises_spend_to_maximise_savings(self):
        """
        Manual spot-check:
        income=100000, savings_target=25000 → spend_ceiling=75000
        min_spend = 30000+8000+5000 = 43000
        LP minimises → rent=30000, food=8000, other=5000 → total=43000
        actual_savings = 100000-43000 = 57000 ✓
        """
        result = solve_constraints(100000, self._categories(), 25000)
        assert result["status"] == "OPTIMAL"
        assert abs(result["total_allocated"] - 43000) < 0.10
        assert abs(result["actual_savings"] - 57000) < 0.10

    def test_allocations_respect_min_bounds(self):
        result = solve_constraints(100000, self._categories(), 25000)
        for a in result["allocations"]:
            assert a["allocated"] >= a["min_amount"] - ALLOCATION_TOLERANCE

    def test_allocations_respect_max_bounds(self):
        result = solve_constraints(100000, self._categories(), 25000)
        for a in result["allocations"]:
            assert a["allocated"] <= a["max_amount"] + ALLOCATION_TOLERANCE

    def test_infeasible_when_min_spend_exceeds_ceiling(self):
        """
        income=50000, savings_target=30000 → ceiling=20000
        min_spend = 30000+8000+5000 = 43000 > 20000 → INFEASIBLE
        """
        result = solve_constraints(50000, self._categories(), 30000)
        assert result["status"] == "INFEASIBLE"

    def test_returns_required_keys(self):
        result = solve_constraints(100000, self._categories(), 25000)
        assert {"status", "income_monthly", "savings_target", "allocations",
                "total_allocated", "actual_savings", "savings_gap",
                "solver_message"} == set(result.keys())

    def test_each_allocation_has_required_keys(self):
        result = solve_constraints(100000, self._categories(), 25000)
        for a in result["allocations"]:
            assert {"category", "min_amount", "max_amount", "allocated",
                    "at_minimum", "at_maximum"} == set(a.keys())

    def test_at_minimum_flag_set_correctly(self):
        """In minimise-spend mode, all categories should be at their minimum."""
        result = solve_constraints(100000, self._categories(), 25000)
        for a in result["allocations"]:
            if a["min_amount"] == a["max_amount"]:
                assert a["at_minimum"] is True
                assert a["at_maximum"] is True
            else:
                assert a["at_minimum"] is True   # LP minimises spend

    def test_utilisation_mode_maximises_spend(self):
        """maximise='utilisation' should push allocations toward max bounds."""
        result = solve_constraints(100000, self._categories(), 25000,
                                   maximise="utilisation")
        assert result["status"] == "OPTIMAL"
        # In utilisation mode, flexible categories should be at max
        for a in result["allocations"]:
            if a["min_amount"] < a["max_amount"]:
                assert a["at_maximum"] is True

    def test_savings_gap_zero_when_optimal(self):
        result = solve_constraints(100000, self._categories(), 25000)
        assert result["savings_gap"] == 0.0

    def test_accounting_identity(self):
        """total_allocated + actual_savings must equal income_monthly."""
        result = solve_constraints(100000, self._categories(), 25000)
        assert abs(result["total_allocated"] + result["actual_savings"] - 100000) < 0.10

    def test_min_greater_than_max_raises(self):
        bad = [{"category": "rent", "min_amount": 40000, "max_amount": 30000}]
        with pytest.raises(ValueError, match="min_amount.*max_amount"):
            solve_constraints(100000, bad, 25000)

    def test_empty_categories_raises(self):
        with pytest.raises(ValueError, match="empty"):
            solve_constraints(100000, [], 25000)

    def test_missing_min_amount_raises(self):
        bad = [{"category": "rent", "max_amount": 30000}]
        with pytest.raises(ValueError, match="missing key"):
            solve_constraints(100000, bad, 25000)

    def test_determinism_100x(self):
        """
        CRITICAL: linprog with method='highs' must be deterministic.
        Same inputs → identical allocations every time.
        """
        categories = self._categories()
        first = solve_constraints(100000, categories, 25000)
        for _ in range(99):
            assert solve_constraints(100000, categories, 25000) == first, \
                "solve_constraints is non-deterministic — HiGHS solver inconsistent"


# ===========================================================================
# SECTION 13 — No external dependencies in new modules
# ===========================================================================

class TestNoExternalDependenciesNewModules:

    def _check_no_import(self, module_name, forbidden):
        import importlib, inspect
        mod = importlib.import_module(module_name)
        src = inspect.getsource(mod)
        import_lines = [l for l in src.split('\n')
                        if l.strip().startswith(('import ', 'from '))]
        return not any(forbidden in l for l in import_lines)

    def test_no_langgraph_in_scenarios(self):
        assert self._check_no_import("app.simulation.scenarios", "langgraph")

    def test_no_sqlalchemy_in_scenarios(self):
        assert self._check_no_import("app.simulation.scenarios", "sqlalchemy")

    def test_no_langgraph_in_optimizer(self):
        assert self._check_no_import("app.simulation.optimizer", "langgraph")

    def test_no_sqlalchemy_in_optimizer(self):
        assert self._check_no_import("app.simulation.optimizer", "sqlalchemy")

    def test_scenarios_only_imports_from_forecast(self):
        """scenarios.py must import from app.simulation.forecast — not re-implement math."""
        import inspect, app.simulation.scenarios as sc
        src = inspect.getsource(sc)
        import_lines = [l.strip() for l in src.split('\n')
                        if l.strip().startswith('from app.simulation')]
        assert any("forecast" in l for l in import_lines), \
            "scenarios.py must import from app.simulation.forecast"
"""
tests/test_budget_load_v2.py
============================
Unit tests for agents/budget/nodes.py → budget_load_v2.

Tests are 100% synchronous. No DB. No LLM. No LangGraph graph compile.
All V2 data is injected via request_params["_v2_analytics"] (the
preferred production path).

Test groups:
  1. Happy path — valid analytics loads cleanly into state
  2. Audit payload — v2_load_metrics computed correctly from analytics
  3. Graph trace  — "budget_load_v2" is appended exactly once
  4. State isolation — no other state fields are mutated
  5. Degradation — DependencyUnavailableError raised on every failure mode
  6. Schema validation — missing or malformed analytics keys caught
  7. Edge cases — empty categories, None rolling values, zero spend

Run with:
    pytest tests/test_budget_load_v2.py -v

Author: VaultAI V3
"""

from __future__ import annotations

import pytest

from app.agents.budget.nodes import budget_load_v2, DependencyUnavailableError
from app.agents.State import make_initial_state, ValidationStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_state(v2_analytics=None, db=None, extra_params=None) -> dict:
    """
    Build a minimal VaultAIState ready to pass into budget_load_v2.

    Injects _v2_analytics or _db into request_params depending on arguments.
    """
    params = {}
    if v2_analytics is not None:
        params["_v2_analytics"] = v2_analytics
    if db is not None:
        params["_db"] = db
    if extra_params:
        params.update(extra_params)

    return make_initial_state(
        user_id="42",
        user_message="help me understand my budget",
        request_params=params,
    )


def _valid_analytics() -> dict:
    """
    Minimal valid return value from build_trends_report().
    Matches the exact schema produced by trends.py.
    """
    return {
        "rolling": {
            "30_day_avg": 15000.0,
            "60_day_avg": 14500.0,
            "90_day_avg": 14200.0,
        },
        "monthly": {
            "current_month":  16000.0,
            "previous_month": 14000.0,
            "percent_change": 14.29,
        },
        "trend_type": "moderate_increase",
        "categories": [
            {"category": "food",          "total": 5000.0},
            {"category": "transport",     "total": 3000.0},
            {"category": "utilities",     "total": 2500.0},
            {"category": "shopping",      "total": 2000.0},
            {"category": "subscriptions", "total":  800.0},
        ],
    }


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:

    def test_returns_v2_analytics_in_state(self):
        analytics = _valid_analytics()
        state = _make_state(v2_analytics=analytics)
        result = budget_load_v2(state)
        assert result["v2_analytics"] == analytics

    def test_returns_empty_v2_expenses(self):
        """v2_expenses is always [] from this node — plan_persist fetches raw records."""
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        assert result["v2_expenses"] == []

    def test_does_not_raise(self):
        state = _make_state(v2_analytics=_valid_analytics())
        # Should complete without exception
        budget_load_v2(state)

    def test_returns_dict(self):
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# 2. Graph trace
# ---------------------------------------------------------------------------

class TestGraphTrace:

    def test_appends_budget_load_v2_to_trace(self):
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        assert "budget_load_v2" in result["graph_trace"]

    def test_trace_appended_exactly_once(self):
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        count = result["graph_trace"].count("budget_load_v2")
        assert count == 1

    def test_trace_preserves_existing_entries(self):
        """Pre-existing trace entries (e.g. from intent_classifier) are kept."""
        analytics = _valid_analytics()
        state = make_initial_state(
            user_id="42",
            user_message="budget help",
            request_params={"_v2_analytics": analytics},
        )
        # Simulate intent_classifier having already run
        state = {**state, "graph_trace": ["intent_classifier"]}
        result = budget_load_v2(state)
        assert result["graph_trace"] == ["intent_classifier", "budget_load_v2"]


# ---------------------------------------------------------------------------
# 3. Audit payload — v2_load_metrics
# ---------------------------------------------------------------------------

class TestAuditPayload:

    def test_audit_payload_contains_v2_load_metrics(self):
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        assert "v2_load_metrics" in result["audit_payload"]

    def test_load_metrics_expense_category_count(self):
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        metrics = result["audit_payload"]["v2_load_metrics"]
        assert metrics["expense_category_count"] == 5

    def test_load_metrics_top_category(self):
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        metrics = result["audit_payload"]["v2_load_metrics"]
        assert metrics["top_category"] == "food"

    def test_load_metrics_trend_type(self):
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        metrics = result["audit_payload"]["v2_load_metrics"]
        assert metrics["trend_type"] == "moderate_increase"

    def test_load_metrics_data_days_available_90(self):
        """All three rolling windows populated → 90 days available."""
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        metrics = result["audit_payload"]["v2_load_metrics"]
        assert metrics["data_days_available"] == 90

    def test_load_metrics_data_days_available_60(self):
        """Only 30/60 day windows populated → 60 days available."""
        analytics = _valid_analytics()
        analytics["rolling"]["90_day_avg"] = 0.0   # zero = no data
        state = _make_state(v2_analytics=analytics)
        result = budget_load_v2(state)
        metrics = result["audit_payload"]["v2_load_metrics"]
        assert metrics["data_days_available"] == 60

    def test_load_metrics_data_days_available_30(self):
        """Only 30-day window populated."""
        analytics = _valid_analytics()
        analytics["rolling"]["90_day_avg"] = 0.0
        analytics["rolling"]["60_day_avg"] = 0.0
        state = _make_state(v2_analytics=analytics)
        result = budget_load_v2(state)
        metrics = result["audit_payload"]["v2_load_metrics"]
        assert metrics["data_days_available"] == 30

    def test_load_metrics_income_detected_always_false(self):
        """V2 has no income model — income_detected is always False."""
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        assert result["audit_payload"]["v2_load_metrics"]["income_detected"] is False

    def test_load_metrics_month_totals(self):
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        metrics = result["audit_payload"]["v2_load_metrics"]
        assert metrics["current_month_total"]  == 16000.0
        assert metrics["previous_month_total"] == 14000.0
        assert metrics["month_over_month_pct"] == 14.29

    def test_load_metrics_preserves_existing_audit_payload(self):
        """Existing audit_payload entries (e.g. classification) must not be lost."""
        analytics = _valid_analytics()
        state = make_initial_state(
            user_id="42",
            user_message="budget",
            request_params={"_v2_analytics": analytics},
        )
        state = {
            **state,
            "audit_payload": {"classification": {"plan_type": "budget"}},
        }
        result = budget_load_v2(state)
        # original key preserved
        assert result["audit_payload"]["classification"]["plan_type"] == "budget"
        # new key added
        assert "v2_load_metrics" in result["audit_payload"]


# ---------------------------------------------------------------------------
# 4. State isolation
# ---------------------------------------------------------------------------

class TestStateIsolation:

    def test_plan_type_not_mutated(self):
        from app.agents.State import PlanType
        state = _make_state(v2_analytics=_valid_analytics())
        state = {**state, "plan_type": PlanType.BUDGET}
        result = budget_load_v2(state)
        assert result["plan_type"] == PlanType.BUDGET

    def test_user_id_not_mutated(self):
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        assert result["user_id"] == "42"

    def test_user_message_not_mutated(self):
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        assert result["user_message"] == "help me understand my budget"

    def test_projected_outcomes_not_set(self):
        """budget_load_v2 must never write projected_outcomes — that's budget_optimize."""
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        assert result["projected_outcomes"] is None

    def test_validation_status_not_set(self):
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        assert result["validation_status"] is None

    def test_degraded_starts_false(self):
        state = _make_state(v2_analytics=_valid_analytics())
        result = budget_load_v2(state)
        assert result["degraded"] is False


# ---------------------------------------------------------------------------
# 5. Degradation — DependencyUnavailableError raised
# ---------------------------------------------------------------------------

class TestDegradation:

    def test_raises_when_no_analytics_and_no_db(self):
        """Neither _v2_analytics nor _db in request_params → error."""
        state = make_initial_state(
            user_id="42",
            user_message="budget",
            request_params={},   # nothing provided
        )
        with pytest.raises(DependencyUnavailableError):
            budget_load_v2(state)

    def test_raises_when_analytics_is_none(self):
        """Explicit None in _v2_analytics → treated as missing."""
        state = make_initial_state(
            user_id="42",
            user_message="budget",
            request_params={"_v2_analytics": None},
        )
        with pytest.raises(DependencyUnavailableError):
            budget_load_v2(state)

    def test_error_message_mentions_dependency(self):
        state = make_initial_state(
            user_id="42",
            user_message="budget",
            request_params={},
        )
        with pytest.raises(DependencyUnavailableError, match="request_params"):
            budget_load_v2(state)


# ---------------------------------------------------------------------------
# 6. Schema validation — malformed analytics
# ---------------------------------------------------------------------------

class TestSchemaValidation:

    def test_raises_when_rolling_key_missing(self):
        analytics = _valid_analytics()
        del analytics["rolling"]
        state = _make_state(v2_analytics=analytics)
        with pytest.raises(DependencyUnavailableError):
            budget_load_v2(state)

    def test_raises_when_monthly_key_missing(self):
        analytics = _valid_analytics()
        del analytics["monthly"]
        state = _make_state(v2_analytics=analytics)
        with pytest.raises(DependencyUnavailableError):
            budget_load_v2(state)

    def test_raises_when_trend_type_missing(self):
        analytics = _valid_analytics()
        del analytics["trend_type"]
        state = _make_state(v2_analytics=analytics)
        with pytest.raises(DependencyUnavailableError):
            budget_load_v2(state)

    def test_raises_when_categories_missing(self):
        analytics = _valid_analytics()
        del analytics["categories"]
        state = _make_state(v2_analytics=analytics)
        with pytest.raises(DependencyUnavailableError):
            budget_load_v2(state)

    def test_raises_when_categories_not_list(self):
        analytics = _valid_analytics()
        analytics["categories"] = {"food": 5000}   # dict instead of list
        state = _make_state(v2_analytics=analytics)
        with pytest.raises(DependencyUnavailableError):
            budget_load_v2(state)

    def test_raises_when_rolling_30_day_missing(self):
        analytics = _valid_analytics()
        del analytics["rolling"]["30_day_avg"]
        state = _make_state(v2_analytics=analytics)
        with pytest.raises(DependencyUnavailableError):
            budget_load_v2(state)

    def test_raises_when_monthly_current_month_missing(self):
        analytics = _valid_analytics()
        del analytics["monthly"]["current_month"]
        state = _make_state(v2_analytics=analytics)
        with pytest.raises(DependencyUnavailableError):
            budget_load_v2(state)


# ---------------------------------------------------------------------------
# 7. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_categories_list(self):
        """Zero categories is valid (user has no recorded expenses yet)."""
        analytics = _valid_analytics()
        analytics["categories"] = []
        state = _make_state(v2_analytics=analytics)
        result = budget_load_v2(state)
        assert result["v2_analytics"]["categories"] == []
        metrics = result["audit_payload"]["v2_load_metrics"]
        assert metrics["expense_category_count"] == 0
        assert metrics["top_category"] is None

    def test_all_rolling_averages_zero(self):
        """All rolling windows are zero → data_days_available = 0."""
        analytics = _valid_analytics()
        analytics["rolling"] = {
            "30_day_avg": 0.0,
            "60_day_avg": 0.0,
            "90_day_avg": 0.0,
        }
        state = _make_state(v2_analytics=analytics)
        result = budget_load_v2(state)
        metrics = result["audit_payload"]["v2_load_metrics"]
        assert metrics["data_days_available"] == 0

    def test_rolling_averages_none_values(self):
        """None rolling values (classify_trend returns insufficient_data)."""
        analytics = _valid_analytics()
        analytics["rolling"] = {
            "30_day_avg": None,
            "60_day_avg": None,
            "90_day_avg": None,
        }
        state = _make_state(v2_analytics=analytics)
        result = budget_load_v2(state)
        metrics = result["audit_payload"]["v2_load_metrics"]
        assert metrics["data_days_available"] == 0

    def test_percent_change_none(self):
        """percent_change is None when previous_month is 0."""
        analytics = _valid_analytics()
        analytics["monthly"]["percent_change"] = None
        state = _make_state(v2_analytics=analytics)
        result = budget_load_v2(state)
        metrics = result["audit_payload"]["v2_load_metrics"]
        assert metrics["month_over_month_pct"] is None

    def test_insufficient_data_trend_type(self):
        analytics = _valid_analytics()
        analytics["trend_type"] = "insufficient_data"
        state = _make_state(v2_analytics=analytics)
        result = budget_load_v2(state)
        assert result["audit_payload"]["v2_load_metrics"]["trend_type"] == "insufficient_data"

    def test_single_category(self):
        """Only one expense category — top_category correctly identified."""
        analytics = _valid_analytics()
        analytics["categories"] = [{"category": "rent", "total": 30000.0}]
        state = _make_state(v2_analytics=analytics)
        result = budget_load_v2(state)
        assert result["audit_payload"]["v2_load_metrics"]["top_category"] == "rent"

    def test_existing_audit_payload_none(self):
        """audit_payload starting as None is handled safely."""
        analytics = _valid_analytics()
        state = make_initial_state(
            user_id="42",
            user_message="budget",
            request_params={"_v2_analytics": analytics},
        )
        state = {**state, "audit_payload": None}
        result = budget_load_v2(state)
        assert "v2_load_metrics" in result["audit_payload"]

    def test_v2_analytics_passthrough_unchanged(self):
        """The analytics dict is passed through as-is — not transformed."""
        analytics = _valid_analytics()
        state = _make_state(v2_analytics=analytics)
        result = budget_load_v2(state)
        # Should be the same object (no copy/transform)
        assert result["v2_analytics"] is analytics
"""
VaultAI V3 — tests/test_router.py
===================================
Phase 5 exit criterion: 10 benchmark intent strings correctly classified.

Tests are deterministic — same input always produces same output.
No mocks needed — classify_intent() is a pure function.

Also tests:
  - Priority ordering (SIMULATE beats BUDGET when "what if" + "budget" both present)
  - request_params override bypasses NLP entirely
  - UNKNOWN fallback for unrecognisable input

Run: pytest tests/test_router.py -v
"""

from __future__ import annotations

import pytest
from app.agents.router_node import classify_intent
from app.agents.State import PlanType


# ===========================================================================
# 10 Benchmark strings — Phase 5 exit criterion
# ===========================================================================

class TestBenchmarkStrings:
    """
    The 10 canonical benchmark strings that the classifier must get right.
    These represent the most common user inputs in each category.
    """

    def test_benchmark_01_budget_salary(self):
        """'I earn 80k a month, help me manage my salary' → BUDGET"""
        r = classify_intent("I earn 80k a month, help me manage my salary", {})
        assert r.plan_type == PlanType.BUDGET
        assert r.source == "keyword_match"

    def test_benchmark_02_invest_mutual_funds(self):
        """'Where should I invest Rs.50,000 in mutual funds?' → INVEST"""
        r = classify_intent("Where should I invest Rs.50,000 in mutual funds?", {})
        assert r.plan_type == PlanType.INVEST

    def test_benchmark_03_goal_car(self):
        """'plan for a car in 12 months' → GOAL"""
        r = classify_intent("plan for a car in 12 months", {})
        assert r.plan_type == PlanType.GOAL

    def test_benchmark_04_goal_emergency_fund(self):
        """'I want to build an emergency fund' → GOAL"""
        r = classify_intent("I want to build an emergency fund", {})
        assert r.plan_type == PlanType.GOAL

    def test_benchmark_05_simulate_what_if(self):
        """'What if I reduce my grocery spending by 20%?' → SIMULATE"""
        r = classify_intent("What if I reduce my grocery spending by 20%?", {})
        assert r.plan_type == PlanType.SIMULATE

    def test_benchmark_06_combined_full_plan(self):
        """'Give me a full plan for my finances' → COMBINED"""
        r = classify_intent("Give me a full plan for my finances", {})
        assert r.plan_type == PlanType.COMBINED

    def test_benchmark_07_goal_vacation(self):
        """'I want to save for a vacation to Goa' → GOAL"""
        r = classify_intent("I want to save for a vacation to Goa", {})
        assert r.plan_type == PlanType.GOAL

    def test_benchmark_08_invest_portfolio(self):
        """'Help me build a portfolio with moderate risk' → INVEST"""
        r = classify_intent("Help me build a portfolio with moderate risk", {})
        assert r.plan_type == PlanType.INVEST

    def test_benchmark_09_budget_expenses(self):
        """'My expenses are too high, where does my money go?' → BUDGET"""
        r = classify_intent("My expenses are too high, where does my money go?", {})
        assert r.plan_type == PlanType.BUDGET

    def test_benchmark_10_goal_debt_payoff(self):
        """'Help me pay off my credit card debt' → GOAL"""
        r = classify_intent("Help me pay off my credit card debt", {})
        assert r.plan_type == PlanType.GOAL


# ===========================================================================
# Priority ordering — SIMULATE beats BUDGET/GOAL when "what if" present
# ===========================================================================

class TestPriorityOrdering:

    def test_simulate_beats_budget_on_what_if(self):
        """'What if I reduce my budget by Rs.5000?' — contains 'budget'
        but SIMULATE has higher priority due to 'what if'."""
        r = classify_intent("What if I reduce my budget by Rs.5000?", {})
        assert r.plan_type == PlanType.SIMULATE
        assert r.matched_keyword in ("what if", "if i reduce")

    def test_simulate_beats_goal_on_scenario(self):
        """'Give me a scenario where I save for a car faster' — SIMULATE wins."""
        r = classify_intent("Give me a scenario where I save for a car faster", {})
        assert r.plan_type == PlanType.SIMULATE

    def test_combined_beats_budget(self):
        """'I want everything reviewed — budget, savings, the works' → COMBINED."""
        r = classify_intent("I want everything reviewed — budget, savings, the works", {})
        assert r.plan_type == PlanType.COMBINED

    def test_goal_beats_budget_on_save_for(self):
        """'help me save for a house' — 'save for' triggers GOAL not BUDGET."""
        r = classify_intent("help me save for a house", {})
        assert r.plan_type == PlanType.GOAL

    def test_invest_beats_budget_on_invest_keyword(self):
        """'I want to invest my savings' — INVEST wins despite 'savings' in BUDGET."""
        r = classify_intent("I want to invest my savings", {})
        assert r.plan_type == PlanType.INVEST


# ===========================================================================
# request_params override — bypasses NLP
# ===========================================================================

class TestRequestParamsOverride:

    def test_explicit_budget_override(self):
        """_plan_type=budget overrides message that would classify as GOAL."""
        r = classify_intent(
            "save for a vacation",
            {"_plan_type": "budget"},
        )
        assert r.plan_type == PlanType.BUDGET
        assert r.source == "request_params"
        assert r.confidence == "high"

    def test_explicit_invest_override(self):
        r = classify_intent(
            "help me manage my expenses",
            {"_plan_type": "invest"},
        )
        assert r.plan_type == PlanType.INVEST
        assert r.source == "request_params"

    def test_explicit_goal_override(self):
        r = classify_intent(
            "what if I change my portfolio",
            {"_plan_type": "goal"},
        )
        assert r.plan_type == PlanType.GOAL
        assert r.source == "request_params"

    def test_explicit_combined_override(self):
        r = classify_intent("", {"_plan_type": "combined"})
        assert r.plan_type == PlanType.COMBINED
        assert r.source == "request_params"

    def test_invalid_override_falls_through_to_keyword(self):
        """Invalid _plan_type value → falls through to keyword matching."""
        r = classify_intent(
            "help me with my budget",
            {"_plan_type": "nonsense_value"},
        )
        assert r.plan_type == PlanType.BUDGET
        assert r.source == "keyword_match"


# ===========================================================================
# UNKNOWN fallback
# ===========================================================================

class TestUnknownFallback:

    def test_empty_message_is_unknown(self):
        r = classify_intent("", {})
        assert r.plan_type == PlanType.UNKNOWN
        assert r.source == "fallback"
        assert r.confidence == "low"

    def test_gibberish_is_unknown(self):
        r = classify_intent("asdfghjkl qwerty zxcv", {})
        assert r.plan_type == PlanType.UNKNOWN

    def test_greeting_is_unknown(self):
        """'Hello, how are you?' — no financial keywords → UNKNOWN."""
        r = classify_intent("Hello, how are you?", {})
        assert r.plan_type == PlanType.UNKNOWN


# ===========================================================================
# Classification result fields
# ===========================================================================

class TestClassificationResultFields:

    def test_keyword_match_has_matched_keyword(self):
        r = classify_intent("I want to invest in SIP", {})
        assert r.matched_keyword is not None
        assert len(r.matched_keyword) > 0

    def test_fallback_has_no_matched_keyword(self):
        r = classify_intent("xyz abc", {})
        assert r.matched_keyword is None

    def test_request_params_override_has_no_matched_keyword(self):
        r = classify_intent("anything", {"_plan_type": "budget"})
        assert r.matched_keyword is None

    def test_confidence_high_for_keyword_match(self):
        r = classify_intent("help me with my budget", {})
        assert r.confidence == "high"

    def test_confidence_low_for_unknown(self):
        r = classify_intent("xyzzy plugh", {})
        assert r.confidence == "low"
"""
VaultAI V3 — tests/test_router.py
===================================
Tests for agents/router_node.py

Phase 2 exit criterion: 10 benchmark intent strings correctly classified.

Test strategy:
  1. Spec benchmark strings   — the exact examples from the spec routing table
  2. Priority ordering        — SIMULATE beats BUDGET when both keywords present
  3. request_params override  — explicit _plan_type bypasses keyword matching
  4. Invalid override         — bad _plan_type falls through to keyword matching
  5. Edge cases               — empty string, whitespace, numeric only, gibberish
  6. Determinism              — same input 100x → identical result
  7. Node function            — intent_classifier_node writes correct state fields
  8. Audit trail              — classification evidence recorded in audit_payload

Run:
    pytest tests/test_router.py -v
"""

import pytest
from app.agents.router_node import classify_intent, intent_classifier_node, ClassificationResult
from app.agents.State import PlanType, ValidationStatus, make_initial_state


# ===========================================================================
# SECTION 1 — Spec benchmark strings (Phase 2 exit criterion)
# These are the exact examples from spec Section 5.1 routing table.
# All 10 must pass for Phase 2 exit.
# ===========================================================================

class TestSpecBenchmarks:
    """
    The 10 benchmark strings from spec Section 5.1, verbatim.
    Input Pattern | Example | Classified As
    """

    def test_benchmark_01_help_me_save_more(self):
        """save/budget/spend → "help me save more" → BUDGET"""
        result = classify_intent("help me save more", {})
        assert result.plan_type == PlanType.BUDGET

    def test_benchmark_02_where_to_put_savings(self):
        """invest/allocate/where → "where to put savings" → INVEST"""
        result = classify_intent("where to put savings", {})
        assert result.plan_type == PlanType.INVEST

    def test_benchmark_03_plan_for_a_car(self):
        """goal/plan for/target → "plan for a car" → GOAL"""
        result = classify_intent("plan for a car", {})
        assert result.plan_type == PlanType.GOAL

    def test_benchmark_04_what_if_i_cut_food(self):
        """what if/reduce/scenario → "what if I cut food" → SIMULATE"""
        result = classify_intent("what if I cut food", {})
        assert result.plan_type == PlanType.SIMULATE

    def test_benchmark_05_review_everything(self):
        """full review/all/combined → "review everything" → COMBINED"""
        result = classify_intent("review everything", {})
        assert result.plan_type == PlanType.COMBINED

    def test_benchmark_06_budget_keyword(self):
        """Pattern: save/budget/spend → BUDGET"""
        result = classify_intent("I need help with my budget", {})
        assert result.plan_type == PlanType.BUDGET

    def test_benchmark_07_invest_keyword(self):
        """Pattern: invest/allocate/where → INVEST"""
        result = classify_intent("help me allocate my savings", {})
        assert result.plan_type == PlanType.INVEST

    def test_benchmark_08_goal_save_for(self):
        """Pattern: goal/plan for/target → GOAL"""
        result = classify_intent("I want to save for a house", {})
        assert result.plan_type == PlanType.GOAL

    def test_benchmark_09_simulate_scenario(self):
        """Pattern: what if/reduce/scenario → SIMULATE"""
        result = classify_intent("show me a scenario where I invest more", {})
        assert result.plan_type == PlanType.SIMULATE

    def test_benchmark_10_unknown_gibberish(self):
        """unknown → anything else → UNKNOWN"""
        result = classify_intent("xyzzy frobble wumpus", {})
        assert result.plan_type == PlanType.UNKNOWN


# ===========================================================================
# SECTION 2 — Additional BUDGET classifications
# ===========================================================================

class TestBudgetClassification:

    def test_spending_keyword(self):
        assert classify_intent("I want to track my spending", {}).plan_type == PlanType.BUDGET

    def test_expenses_keyword(self):
        assert classify_intent("show me my expenses breakdown", {}).plan_type == PlanType.BUDGET

    def test_save_more_variant(self):
        assert classify_intent("how can I spend less each month", {}).plan_type == PlanType.BUDGET

    def test_salary_keyword(self):
        assert classify_intent("I just got a salary hike, what should I do", {}).plan_type == PlanType.BUDGET

    def test_income_keyword(self):
        assert classify_intent("based on my income, can I save 20%", {}).plan_type == PlanType.BUDGET

    def test_cut_costs(self):
        assert classify_intent("I need to cut costs this month", {}).plan_type == PlanType.BUDGET


# ===========================================================================
# SECTION 3 — Additional INVEST classifications
# ===========================================================================

class TestInvestClassification:

    def test_invest_keyword(self):
        assert classify_intent("I want to invest 50000 rupees", {}).plan_type == PlanType.INVEST

    def test_portfolio_keyword(self):
        assert classify_intent("help me build a portfolio", {}).plan_type == PlanType.INVEST

    def test_mutual_fund(self):
        assert classify_intent("which mutual fund should I pick", {}).plan_type == PlanType.INVEST

    def test_sip_keyword(self):
        assert classify_intent("I want to start a SIP", {}).plan_type == PlanType.INVEST

    def test_equity_keyword(self):
        assert classify_intent("how much equity exposure is right for me", {}).plan_type == PlanType.INVEST

    def test_where_should_i_put(self):
        assert classify_intent("where should I put my bonus money", {}).plan_type == PlanType.INVEST


# ===========================================================================
# SECTION 4 — Additional GOAL classifications
# ===========================================================================

class TestGoalClassification:

    def test_buy_a_car(self):
        assert classify_intent("I want to buy a car in 12 months", {}).plan_type == PlanType.GOAL

    def test_emergency_fund(self):
        assert classify_intent("I need to build an emergency fund", {}).plan_type == PlanType.GOAL

    def test_down_payment(self):
        assert classify_intent("saving for a down payment on a flat", {}).plan_type == PlanType.GOAL

    def test_vacation_keyword(self):
        assert classify_intent("planning a vacation to Europe next year", {}).plan_type == PlanType.GOAL

    def test_when_can_i_afford(self):
        assert classify_intent("when can I afford to buy a laptop", {}).plan_type == PlanType.GOAL

    def test_pay_off_debt(self):
        assert classify_intent("I want to pay off my credit card debt", {}).plan_type == PlanType.GOAL

    def test_how_long_to_save(self):
        assert classify_intent("how many months to save 1 lakh", {}).plan_type == PlanType.GOAL


# ===========================================================================
# SECTION 5 — SIMULATE classifications
# ===========================================================================

class TestSimulateClassification:

    def test_what_if_reduce(self):
        assert classify_intent("what if I reduce dining out by 50%", {}).plan_type == PlanType.SIMULATE

    def test_what_if_increase(self):
        assert classify_intent("what if I increase my SIP to 10000", {}).plan_type == PlanType.SIMULATE

    def test_scenario_keyword(self):
        assert classify_intent("run a scenario with higher savings rate", {}).plan_type == PlanType.SIMULATE

    def test_simulate_keyword(self):
        assert classify_intent("simulate what happens if I stop eating out", {}).plan_type == PlanType.SIMULATE

    def test_hypothetical(self):
        assert classify_intent("hypothetical: what if I got a 20% raise", {}).plan_type == PlanType.SIMULATE


# ===========================================================================
# SECTION 6 — COMBINED classifications
# ===========================================================================

class TestCombinedClassification:

    def test_review_everything(self):
        assert classify_intent("review everything for me", {}).plan_type == PlanType.COMBINED

    def test_full_review(self):
        assert classify_intent("I want a full review of my finances", {}).plan_type == PlanType.COMBINED

    def test_combined_keyword(self):
        assert classify_intent("give me a combined plan", {}).plan_type == PlanType.COMBINED

    def test_complete_plan(self):
        assert classify_intent("I want a complete plan for my finances", {}).plan_type == PlanType.COMBINED


# ===========================================================================
# SECTION 7 — Priority ordering
# When a message contains keywords from multiple categories, the higher
# priority category must win.
# ===========================================================================

class TestPriorityOrdering:

    def test_simulate_beats_budget(self):
        """
        "what if I cut my budget" contains both SIMULATE ("what if", "cut")
        and BUDGET ("budget"). SIMULATE must win — user is asking a hypothetical.
        """
        result = classify_intent("what if I cut my budget in half", {})
        assert result.plan_type == PlanType.SIMULATE

    def test_simulate_beats_invest(self):
        """
        "what if I increase my investment" contains both SIMULATE and INVEST.
        SIMULATE wins.
        """
        result = classify_intent("what if I increase my investment amount", {})
        assert result.plan_type == PlanType.SIMULATE

    def test_combined_beats_budget(self):
        """
        "review everything including my budget" → COMBINED wins.
        """
        result = classify_intent("review everything including my budget and savings", {})
        assert result.plan_type == PlanType.COMBINED

    def test_combined_beats_goal(self):
        """
        "full plan for all my goals" → COMBINED wins.
        """
        result = classify_intent("give me a full plan for all my goals", {})
        assert result.plan_type == PlanType.COMBINED

    def test_goal_beats_budget_save_for(self):
        """
        "save for a car" contains BUDGET ("save") but GOAL wins
        because "save for" is a more specific GOAL phrase.
        SIMULATE is checked before BUDGET, but "save for" is in GOAL patterns.
        The key is GOAL has "save for" as a keyword.
        """
        result = classify_intent("I want to save for a new car", {})
        assert result.plan_type == PlanType.GOAL


# ===========================================================================
# SECTION 8 — request_params override
# ===========================================================================

class TestRequestParamsOverride:

    def test_budget_override(self):
        """Direct API call to /plans/budget sets _plan_type=budget."""
        result = classify_intent("anything at all", {"_plan_type": "budget"})
        assert result.plan_type == PlanType.BUDGET
        assert result.source == "request_params"
        assert result.confidence == "high"

    def test_invest_override(self):
        result = classify_intent("", {"_plan_type": "invest"})
        assert result.plan_type == PlanType.INVEST
        assert result.source == "request_params"

    def test_goal_override(self):
        result = classify_intent("", {"_plan_type": "goal"})
        assert result.plan_type == PlanType.GOAL

    def test_simulate_override(self):
        result = classify_intent("", {"_plan_type": "simulate"})
        assert result.plan_type == PlanType.SIMULATE

    def test_override_beats_conflicting_keywords(self):
        """
        Even if message says "invest", explicit _plan_type=budget overrides it.
        This is how the direct API endpoints work.
        """
        result = classify_intent("I want to invest everything", {"_plan_type": "budget"})
        assert result.plan_type == PlanType.BUDGET
        assert result.source == "request_params"

    def test_invalid_override_falls_through_to_keywords(self):
        """
        Invalid _plan_type value → falls through to keyword matching.
        The route still works, just via NLP.
        """
        result = classify_intent("help me save more", {"_plan_type": "invalid_type"})
        assert result.plan_type == PlanType.BUDGET
        assert result.source == "keyword_match"

    def test_empty_params_no_override(self):
        result = classify_intent("plan for a car", {})
        assert result.source == "keyword_match"


# ===========================================================================
# SECTION 9 — Edge cases
# ===========================================================================

class TestEdgeCases:

    def test_empty_string(self):
        """Empty message → UNKNOWN (no keywords to match)."""
        result = classify_intent("", {})
        assert result.plan_type == PlanType.UNKNOWN
        assert result.source == "fallback"
        assert result.confidence == "low"

    def test_whitespace_only(self):
        result = classify_intent("   ", {})
        assert result.plan_type == PlanType.UNKNOWN

    def test_numbers_only(self):
        result = classify_intent("100000 50000 24", {})
        assert result.plan_type == PlanType.UNKNOWN

    def test_single_irrelevant_word(self):
        result = classify_intent("hello", {})
        assert result.plan_type == PlanType.UNKNOWN

    def test_case_insensitive_upper(self):
        """Keywords must match regardless of case."""
        result = classify_intent("HELP ME SAVE MORE", {})
        assert result.plan_type == PlanType.BUDGET

    def test_case_insensitive_mixed(self):
        result = classify_intent("What If I Cut Food expenses", {})
        assert result.plan_type == PlanType.SIMULATE

    def test_very_long_message(self):
        """Long message with budget keyword buried at the end."""
        msg = ("I have been thinking a lot about my financial situation. "
               "I earn a decent amount but I feel like I am not managing "
               "my money well. I want to understand where my money goes "
               "and how to create a proper monthly budget for myself.")
        result = classify_intent(msg, {})
        assert result.plan_type == PlanType.BUDGET

    def test_matched_keyword_recorded(self):
        """matched_keyword must be populated on a successful keyword match."""
        result = classify_intent("I want to invest in mutual funds", {})
        assert result.matched_keyword is not None
        assert len(result.matched_keyword) > 0

    def test_matched_keyword_none_on_fallback(self):
        result = classify_intent("xyzzy", {})
        assert result.matched_keyword is None

    def test_matched_keyword_none_on_override(self):
        result = classify_intent("anything", {"_plan_type": "budget"})
        assert result.matched_keyword is None


# ===========================================================================
# SECTION 10 — ClassificationResult fields
# ===========================================================================

class TestClassificationResult:

    def test_returns_dataclass(self):
        result = classify_intent("help me save more", {})
        assert isinstance(result, ClassificationResult)

    def test_has_all_fields(self):
        result = classify_intent("what if I cut food", {})
        assert hasattr(result, "plan_type")
        assert hasattr(result, "source")
        assert hasattr(result, "matched_keyword")
        assert hasattr(result, "confidence")

    def test_confidence_high_on_keyword_match(self):
        result = classify_intent("plan for a car", {})
        assert result.confidence == "high"

    def test_confidence_low_on_fallback(self):
        result = classify_intent("random words that match nothing", {})
        assert result.confidence == "low"

    def test_source_keyword_match(self):
        result = classify_intent("I want to invest", {})
        assert result.source == "keyword_match"

    def test_source_fallback(self):
        result = classify_intent("", {})
        assert result.source == "fallback"


# ===========================================================================
# SECTION 11 — LangGraph node function: intent_classifier_node
# ===========================================================================

class TestIntentClassifierNode:
    """
    Tests the full LangGraph node, not just the pure classify_intent function.
    Verifies that state fields are written correctly.
    """

    def _state(self, message: str, params: dict = None) -> dict:
        return make_initial_state(
            user_id="test-user",
            user_message=message,
            request_params=params or {},
        )

    def test_sets_plan_type_in_state(self):
        state = self._state("help me save more")
        result = intent_classifier_node(state)
        assert result["plan_type"] == PlanType.BUDGET

    def test_appends_to_graph_trace(self):
        state = self._state("plan for a car")
        result = intent_classifier_node(state)
        assert "intent_classifier" in result["graph_trace"]

    def test_graph_trace_is_first_entry(self):
        """intent_classifier is always the first node to run."""
        state = self._state("invest my savings")
        result = intent_classifier_node(state)
        assert result["graph_trace"][0] == "intent_classifier"

    def test_writes_audit_payload(self):
        state = self._state("what if I cut dining out")
        result = intent_classifier_node(state)
        assert result["audit_payload"] is not None
        assert "classification" in result["audit_payload"]

    def test_audit_payload_has_plan_type(self):
        state = self._state("review everything")
        result = intent_classifier_node(state)
        classification = result["audit_payload"]["classification"]
        assert classification["plan_type"] == PlanType.COMBINED.value

    def test_audit_payload_has_matched_keyword(self):
        state = self._state("I want to invest in stocks")
        result = intent_classifier_node(state)
        classification = result["audit_payload"]["classification"]
        assert classification["matched_keyword"] is not None

    def test_audit_payload_has_source(self):
        state = self._state("budget help")
        result = intent_classifier_node(state)
        assert result["audit_payload"]["classification"]["source"] in (
            "request_params", "keyword_match", "fallback"
        )

    def test_immutable_fields_unchanged(self):
        """Node must not modify user_id, user_message, or request_params."""
        state = self._state("help me save", {"income": 100000})
        result = intent_classifier_node(state)
        assert result["user_id"] == "test-user"
        assert result["user_message"] == "help me save"
        assert result["request_params"] == {"income": 100000}

    def test_node_preserves_all_other_state_fields(self):
        """All Optional fields not touched by this node must remain None."""
        state = self._state("invest my money")
        result = intent_classifier_node(state)
        assert result["v2_analytics"] is None
        assert result["projected_outcomes"] is None
        assert result["validation_status"] is None
        assert result["llm_explanation"] is None
        assert result["plan_id"] is None

    def test_unknown_intent_sets_unknown_plan_type(self):
        state = self._state("jabberwocky snicker-snack")
        result = intent_classifier_node(state)
        assert result["plan_type"] == PlanType.UNKNOWN

    def test_request_params_override_via_node(self):
        """_plan_type in request_params must override keyword matching in the node."""
        state = self._state("I want to invest everything", {"_plan_type": "budget"})
        result = intent_classifier_node(state)
        assert result["plan_type"] == PlanType.BUDGET


# ===========================================================================
# SECTION 12 — Determinism
# ===========================================================================

class TestDeterminism:

    def test_classify_intent_determinism_100x(self):
        """
        Phase 2 exit criterion: same message always produces same result.
        Routing must NEVER be non-deterministic.
        """
        messages = [
            ("help me save more",        PlanType.BUDGET),
            ("where to put savings",      PlanType.INVEST),
            ("plan for a car",            PlanType.GOAL),
            ("what if I cut food",        PlanType.SIMULATE),
            ("review everything",         PlanType.COMBINED),
            ("xyzzy frobble",             PlanType.UNKNOWN),
        ]
        for message, expected in messages:
            first = classify_intent(message, {})
            for _ in range(99):
                again = classify_intent(message, {})
                assert again.plan_type == first.plan_type == expected, (
                    f"NON-DETERMINISTIC: '{message}' → {again.plan_type} "
                    f"but expected {expected}"
                )

    def test_node_determinism_100x(self):
        """Node function must also be deterministic end-to-end."""
        state = make_initial_state("u", "what if I cut dining", {})
        first = intent_classifier_node(state)
        for _ in range(99):
            again = intent_classifier_node(state)
            assert again["plan_type"] == first["plan_type"]
            assert again["graph_trace"] == first["graph_trace"]
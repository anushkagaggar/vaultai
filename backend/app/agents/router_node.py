"""
VaultAI V3 — agents/router_node.py
====================================
Rule-based intent classifier. No LLM. No ML. Zero randomness.

The spec is explicit:
    "RULE: This node is 100% rule-based. No LLM. No ML.
     Routing errors are system failures — they must never be non-deterministic."

This means the classifier must be:
  1. Deterministic  — same input always produces the same PlanType
  2. Exhaustive     — every possible input produces exactly one output
  3. Auditable      — the match reason is recorded in state for the trace
  4. Testable       — 10 benchmark strings from the spec must pass (Phase 2 exit)

CLASSIFICATION STRATEGY
-----------------------
Two-pass approach:

  Pass 1 — request_params first.
    If the FastAPI route sets plan_type explicitly (e.g. POST /plans/budget
    always sets {"_plan_type": "budget"}), skip NLP entirely.
    This is how the direct API endpoints work — no ambiguity.

  Pass 2 — keyword matching on user_message.
    Normalise to lowercase. Check keyword groups in priority order.
    Priority matters: "what if I reduce my budget" contains both
    SIMULATE ("what if", "reduce") and BUDGET ("budget") keywords.
    SIMULATE wins because it's checked first — the user asked a
    what-if question, not for a budget plan.

    Priority order (highest to lowest):
      1. COMBINED  — "review everything", "full plan", "all three"
      2. SIMULATE  — "what if", "scenario", "reduce", "cut"
      3. BUDGET    — "budget", "save", "spend", "expense", "salary"
      4. INVEST    — "invest", "allocate", "portfolio", "where to put"
      5. GOAL      — "goal", "plan for", "target", "buy a", "save for"
      6. UNKNOWN   — fallback if nothing matched

WHY PRIORITY ORDER MATTERS
---------------------------
"what if I reduce my grocery budget" → SIMULATE (not BUDGET)
  because the user is asking a hypothetical, not requesting a budget plan.

"help me save for a car" → GOAL (not BUDGET)
  because "save for" + an object = goal, not general savings advice.

"I want to invest my savings in mutual funds" → INVEST (not BUDGET/GOAL)
  because "invest" + "mutual funds" = allocation request.

The priority ordering encodes these precedence rules explicitly so any
future change to the rules is visible in the keyword lists, not buried
in conditional logic.

MATCH RESULT
------------
classify_intent() returns a ClassificationResult dataclass (not just
a PlanType) so the node can record:
  - which plan_type was chosen
  - which keyword triggered the match (for audit_payload)
  - whether it came from request_params override or message analysis

Author: VaultAI V3
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.agents.State import (
    VaultAIState,
    PlanType,
    append_trace,
)


# ---------------------------------------------------------------------------
# Keyword registry
# ---------------------------------------------------------------------------
# Each entry: (PlanType, [keyword_or_phrase, ...])
# Phrases are matched as substrings after lowercasing.
# Priority = order in this list (first match wins).

_KEYWORD_RULES: list[tuple[PlanType, list[str]]] = [
    (
        PlanType.COMBINED,
        [
            "review everything",
            "full review",
            "full plan",
            "all three",
            "combined",
            "complete plan",
            "everything",
            "overall plan",
        ],
    ),
    (
        PlanType.SIMULATE,
        [
            "what if",
            "scenario",
            "what happens if",
            "if i reduce",
            "if i cut",
            "if i increase",
            "simulate",
            "hypothetical",
            "project what",
        ],
    ),
    (
        PlanType.BUDGET,
        [
            "budget",
            "help me save",
            "how much can i save",
            "spending",
            "expenses",
            "monthly spend",
            "cut costs",
            "reduce expenses",
            "salary",
            "income",
            "where does my money go",
            "track spending",
            "save more",
            "spend less",
        ],
    ),
    (
        PlanType.INVEST,
        [
            "invest",
            "investment",
            "allocate",
            "allocation",
            "portfolio",
            "mutual fund",
            "stocks",
            "equity",
            "where to put",
            "where should i put",
            "risk profile",
            "sip",
            "fixed deposit",
            "fd ",
            "debt fund",
        ],
    ),
    (
        PlanType.GOAL,
        [
            "goal",
            "plan for",
            "save for",
            "saving for",
            "target",
            "buy a",
            "buy my",
            "afford",
            "down payment",
            "emergency fund",
            "how long",
            "how many months",
            "when can i",
            "pay off",
            "debt payoff",
            "trip to",
            "travel to",
            "vacation",
        ],
    ),
]

# Compiled for performance — normalise once, match many times
_COMPILED_RULES: list[tuple[PlanType, list[re.Pattern]]] = [
    (plan_type, [re.compile(re.escape(kw), re.IGNORECASE) for kw in keywords])
    for plan_type, keywords in _KEYWORD_RULES
]


# ---------------------------------------------------------------------------
# Classification result
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    """
    Result of classify_intent(). Carries the match evidence so
    the node can write an informative audit trail entry.
    """
    plan_type: PlanType
    source: str          # "request_params" | "keyword_match" | "fallback"
    matched_keyword: Optional[str]   # the keyword that triggered the match
    confidence: str      # "high" | "medium" | "low"
                         # high   = request_params override or unambiguous keyword
                         # medium = single keyword match
                         # low    = fallback (UNKNOWN)


# ---------------------------------------------------------------------------
# Core classification logic (pure function — no state dependency)
# ---------------------------------------------------------------------------

def classify_intent(
    user_message: str,
    request_params: dict,
) -> ClassificationResult:
    """
    Classify the user's intent into a PlanType.

    Pure function — takes message + params, returns ClassificationResult.
    No side effects. Deterministic. Safe to call in tests without state.

    Pass 1: Check request_params for an explicit "_plan_type" override.
            The FastAPI direct endpoints (/plans/budget, /plans/invest, etc.)
            inject this so the router is bypassed cleanly.

    Pass 2: Keyword matching on user_message, priority order.

    Pass 3: Fallback to UNKNOWN if nothing matched.

    Args:
        user_message:    Raw message text from the user.
        request_params:  Dict from the API request body.

    Returns:
        ClassificationResult with plan_type, source, matched_keyword, confidence.
    """
    # --- Pass 1: explicit override from request_params ---
    explicit = request_params.get("_plan_type")
    if explicit:
        try:
            forced_type = PlanType(explicit)
            return ClassificationResult(
                plan_type=forced_type,
                source="request_params",
                matched_keyword=None,
                confidence="high",
            )
        except ValueError:
            # Invalid value in _plan_type — fall through to keyword matching
            pass

    # --- Pass 2: keyword matching ---
    message_lower = user_message.lower().strip()

    for plan_type, patterns in _COMPILED_RULES:
        for pattern in patterns:
            match = pattern.search(message_lower)
            if match:
                return ClassificationResult(
                    plan_type=plan_type,
                    source="keyword_match",
                    matched_keyword=match.group(0),
                    confidence="high" if plan_type != PlanType.COMBINED else "high",
                )

    # --- Pass 3: fallback ---
    return ClassificationResult(
        plan_type=PlanType.UNKNOWN,
        source="fallback",
        matched_keyword=None,
        confidence="low",
    )


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------

def intent_classifier_node(state: VaultAIState) -> VaultAIState:
    """
    LangGraph node: intent_classifier

    Reads:  state["user_message"], state["request_params"]
    Writes: state["plan_type"], state["graph_trace"], state["audit_payload"]

    This is the function registered in graph.py as:
        builder.add_node("intent_classifier", intent_classifier_node)

    It is deterministic. The same user_message always produces the
    same plan_type. Routing errors are system failures.
    """
    trace = append_trace(state, "intent_classifier")

    result = classify_intent(
        user_message=state.get("user_message", ""),
        request_params=state.get("request_params", {}),
    )

    # Record classification evidence in audit_payload
    existing_payload = state.get("audit_payload") or {}
    updated_payload = {
        **existing_payload,
        "classification": {
            "plan_type":        result.plan_type.value,
            "source":           result.source,
            "matched_keyword":  result.matched_keyword,
            "confidence":       result.confidence,
            "user_message":     state.get("user_message", ""),
        },
    }

    return {
        **state,
        "plan_type":     result.plan_type,
        "graph_trace":   trace,
        "audit_payload": updated_payload,
    }
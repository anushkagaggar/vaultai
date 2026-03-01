"""
VaultAI V3 — agents/graph.py
==============================
The complete LangGraph StateGraph definition.

PHASE 3 STATUS
--------------
Budget subgraph: FULLY WIRED — real implementations from agents/budget/nodes.py.
All other subgraphs remain stubbed with correct topology.

INVOCATION — always use ainvoke from async route handlers:

    result = await app_graph.ainvoke(
        state,
        config={"configurable": {"thread_id": user_id}},
    )

graph.invoke() is only safe in sync unit tests that never reach an async node.

Author: VaultAI V3
"""

from __future__ import annotations

import logging

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.router_node import intent_classifier_node
from app.agents.State import (
    VaultAIState,
    PlanType,
    ValidationStatus,
    append_trace,
    mark_degraded,
)

# Budget subgraph — real implementations from agents/budget/nodes.py
from app.agents.budget.nodes import (
    budget_load_v2,
    budget_optimize,
    budget_validate,
    budget_explain,
    budget_filter,
    budget_fallback,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# ROUTING FUNCTIONS
# ===========================================================================

def _route_by_intent(state: VaultAIState) -> str:
    plan_type = state.get("plan_type")
    if plan_type == PlanType.BUDGET:
        return "budget_load_v2"
    elif plan_type == PlanType.INVEST:
        return "invest_fetch_data"
    elif plan_type == PlanType.GOAL:
        return "goal_define"
    elif plan_type == PlanType.SIMULATE:
        return "sim_run"
    elif plan_type == PlanType.COMBINED:
        return "budget_load_v2"   # Phase 5 will replace
    else:
        return "clarify"


def _route_after_budget_validate(state: VaultAIState) -> str:
    if state.get("validation_status") == ValidationStatus.PASSED:
        return "budget_explain"
    return "budget_fallback"


def _route_after_invest_validate(state: VaultAIState) -> str:
    if state.get("validation_status") == ValidationStatus.PASSED:
        return "invest_explain"
    return "invest_fallback"


def _route_after_goal_validate(state: VaultAIState) -> str:
    if state.get("validation_status") == ValidationStatus.PASSED:
        return "goal_explain"
    return "goal_fallback"


def _route_after_sim_validate(state: VaultAIState) -> str:
    if state.get("validation_status") == ValidationStatus.PASSED:
        return "plan_persist"
    return "sim_fallback"


# ===========================================================================
# STUB NODES — invest / goal / simulate
# ===========================================================================

async def invest_fetch_data(state: VaultAIState) -> VaultAIState:
    """STUB Phase 4 — loads V2 analytics + external market data."""
    trace = append_trace(state, "invest_fetch_data")
    return {**state, "graph_trace": trace}

def invest_allocate(state: VaultAIState) -> VaultAIState:
    """STUB Phase 4 — deterministic risk-tolerance allocation template."""
    trace = append_trace(state, "invest_allocate")
    return {**state, "graph_trace": trace}

def invest_validate(state: VaultAIState) -> VaultAIState:
    """STUB Phase 4 — asserts allocations sum to 100%."""
    trace = append_trace(state, "invest_validate")
    return {**state, "graph_trace": trace,
            "validation_status": ValidationStatus.PASSED}

async def invest_explain(state: VaultAIState) -> VaultAIState:
    """STUB Phase 4 — LLM narrates allocation rationale."""
    trace = append_trace(state, "invest_explain")
    return {**state, "graph_trace": trace}

def invest_filter(state: VaultAIState) -> VaultAIState:
    """STUB Phase 4 — scrubs predicted returns from LLM output."""
    trace = append_trace(state, "invest_filter")
    return {**state, "graph_trace": trace}

def invest_fallback(state: VaultAIState) -> VaultAIState:
    """STUB Phase 4 — deterministic allocation summary."""
    trace = append_trace(state, "invest_fallback")
    return {**state, "graph_trace": trace}


def goal_define(state: VaultAIState) -> VaultAIState:
    """STUB Phase 5 — parses goal type/params, loads V2 data."""
    trace = append_trace(state, "goal_define")
    return {**state, "graph_trace": trace}

def goal_simulate(state: VaultAIState) -> VaultAIState:
    """STUB Phase 5 — calls forecast.goal_feasibility()."""
    trace = append_trace(state, "goal_simulate")
    return {**state, "graph_trace": trace}

def goal_validate(state: VaultAIState) -> VaultAIState:
    """STUB Phase 5 — re-runs goal_feasibility, asserts label matches."""
    trace = append_trace(state, "goal_validate")
    return {**state, "graph_trace": trace,
            "validation_status": ValidationStatus.PASSED}

async def goal_explain(state: VaultAIState) -> VaultAIState:
    """STUB Phase 5 — LLM narrates goal feasibility."""
    trace = append_trace(state, "goal_explain")
    return {**state, "graph_trace": trace}

def goal_filter(state: VaultAIState) -> VaultAIState:
    """STUB Phase 5 — scrubs speculative language."""
    trace = append_trace(state, "goal_filter")
    return {**state, "graph_trace": trace}

def goal_fallback(state: VaultAIState) -> VaultAIState:
    """STUB Phase 5 — deterministic feasibility summary."""
    trace = append_trace(state, "goal_fallback")
    return {**state, "graph_trace": trace}


def sim_run(state: VaultAIState) -> VaultAIState:
    """STUB Phase 5 — calls scenarios.build_scenario()."""
    trace = append_trace(state, "sim_run")
    return {**state, "graph_trace": trace}

def sim_validate(state: VaultAIState) -> VaultAIState:
    """STUB Phase 5 — re-runs build_scenario, asserts final_balance matches."""
    trace = append_trace(state, "sim_validate")
    return {**state, "graph_trace": trace,
            "validation_status": ValidationStatus.PASSED}

def sim_fallback(state: VaultAIState) -> VaultAIState:
    """STUB Phase 5 — marks degraded, passes raw numbers through."""
    trace = append_trace(state, "sim_fallback")
    return {**state, "graph_trace": trace}


# ===========================================================================
# SHARED TERMINAL NODES
# ===========================================================================

async def plan_persist(state: VaultAIState) -> VaultAIState:
    """
    The ONLY node that writes to the database.

    The AsyncSession is NOT created here. It is extracted from
    state["request_params"]["_db"] — injected there by the route handler
    via Depends(get_db). This keeps the session lifecycle owned by FastAPI,
    not by the graph.

    If _db is absent (unit tests without DB), logs a warning and returns
    plan_id=None — the graph still completes cleanly with full plan data.
    """
    trace = append_trace(state, "plan_persist")
    db    = (state.get("request_params") or {}).get("_db")

    if db is None:
        logger.warning(
            "plan_persist: _db not in request_params — skipping DB write. "
            "plan_id will be None. Expected in unit tests only."
        )
        return {**state, "graph_trace": trace, "plan_id": None}

    from app.plans.service import persist_plan
    result = await persist_plan(state, db)

    return {**state, **result, "graph_trace": trace}


def clarify(state: VaultAIState) -> VaultAIState:
    """
    STUB Phase 6 — reached when intent_classifier returns UNKNOWN.
    Returns a clarification prompt. Does NOT write a plan to DB.
    """
    trace = append_trace(state, "clarify")
    return {
        **state,
        "graph_trace": trace,
        "explanation_filtered": (
            "I'm not sure what type of financial plan you need. "
            "Try: 'Help me build a budget', 'Where should I invest ₹50,000?', "
            "or 'Can I afford a car in 2 years?'"
        ),
    }


# ===========================================================================
# GRAPH ASSEMBLY
# ===========================================================================

def _build_graph() -> StateGraph:
    builder = StateGraph(VaultAIState)

    # Router
    builder.add_node("intent_classifier", intent_classifier_node)

    # Budget — real implementations
    builder.add_node("budget_load_v2",   budget_load_v2)
    builder.add_node("budget_optimize",  budget_optimize)
    builder.add_node("budget_validate",  budget_validate)
    builder.add_node("budget_explain",   budget_explain)
    builder.add_node("budget_filter",    budget_filter)
    builder.add_node("budget_fallback",  budget_fallback)

    # Invest — stubs
    builder.add_node("invest_fetch_data", invest_fetch_data)
    builder.add_node("invest_allocate",   invest_allocate)
    builder.add_node("invest_validate",   invest_validate)
    builder.add_node("invest_explain",    invest_explain)
    builder.add_node("invest_filter",     invest_filter)
    builder.add_node("invest_fallback",   invest_fallback)

    # Goal — stubs
    builder.add_node("goal_define",    goal_define)
    builder.add_node("goal_simulate",  goal_simulate)
    builder.add_node("goal_validate",  goal_validate)
    builder.add_node("goal_explain",   goal_explain)
    builder.add_node("goal_filter",    goal_filter)
    builder.add_node("goal_fallback",  goal_fallback)

    # Simulate — stubs
    builder.add_node("sim_run",      sim_run)
    builder.add_node("sim_validate", sim_validate)
    builder.add_node("sim_fallback", sim_fallback)

    # Shared
    builder.add_node("plan_persist", plan_persist)
    builder.add_node("clarify",      clarify)

    # ── Edges ────────────────────────────────────────────────────────────

    builder.set_entry_point("intent_classifier")

    builder.add_conditional_edges(
        "intent_classifier",
        _route_by_intent,
        {
            "budget_load_v2":    "budget_load_v2",
            "invest_fetch_data": "invest_fetch_data",
            "goal_define":       "goal_define",
            "sim_run":           "sim_run",
            "clarify":           "clarify",
        },
    )

    # Budget chain
    builder.add_edge("budget_load_v2",  "budget_optimize")
    builder.add_edge("budget_optimize", "budget_validate")
    builder.add_conditional_edges(
        "budget_validate",
        _route_after_budget_validate,
        {
            "budget_explain":  "budget_explain",
            "budget_fallback": "budget_fallback",
        },
    )
    builder.add_edge("budget_explain",  "budget_filter")
    builder.add_edge("budget_filter",   "plan_persist")
    builder.add_edge("budget_fallback", "plan_persist")

    # Invest chain
    builder.add_edge("invest_fetch_data", "invest_allocate")
    builder.add_edge("invest_allocate",   "invest_validate")
    builder.add_conditional_edges(
        "invest_validate",
        _route_after_invest_validate,
        {"invest_explain": "invest_explain", "invest_fallback": "invest_fallback"},
    )
    builder.add_edge("invest_explain",  "invest_filter")
    builder.add_edge("invest_filter",   "plan_persist")
    builder.add_edge("invest_fallback", "plan_persist")

    # Goal chain
    builder.add_edge("goal_define",   "goal_simulate")
    builder.add_edge("goal_simulate", "goal_validate")
    builder.add_conditional_edges(
        "goal_validate",
        _route_after_goal_validate,
        {"goal_explain": "goal_explain", "goal_fallback": "goal_fallback"},
    )
    builder.add_edge("goal_explain",  "goal_filter")
    builder.add_edge("goal_filter",   "plan_persist")
    builder.add_edge("goal_fallback", "plan_persist")

    # Simulate chain
    builder.add_edge("sim_run", "sim_validate")
    builder.add_conditional_edges(
        "sim_validate",
        _route_after_sim_validate,
        {"plan_persist": "plan_persist", "sim_fallback": "sim_fallback"},
    )
    builder.add_edge("sim_fallback", "plan_persist")

    # Terminal
    builder.add_edge("plan_persist", END)
    builder.add_edge("clarify",      END)

    return builder


def compile_graph():
    """
    Compile the VaultAI StateGraph. Called once at application startup.

    Always use ainvoke() from async route handlers:
        await graph.ainvoke(state, config={"configurable": {"thread_id": user_id}})
    """
    builder = _build_graph()
    memory  = MemorySaver()
    return builder.compile(checkpointer=memory)
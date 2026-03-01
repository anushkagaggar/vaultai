"""
VaultAI V3 — agents/graph.py
==============================

PHASE STATUS
------------
Budget subgraph : LIVE — agents/budget/nodes.py
Invest subgraph : LIVE — agents/invest/nodes.py
Goal   subgraph : LIVE — agents/goal/nodes.py
Simulate        : STUBBED — Phase 5

INVOCATION — always ainvoke from async route handlers:

    result = await app_graph.ainvoke(
        state,
        config={"configurable": {"thread_id": user_id, "db": db}},
    )

Author: VaultAI V3
"""

from __future__ import annotations

import logging

from langchain_core.runnables import RunnableConfig
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

# ── Real node implementations ────────────────────────────────────────────────
from app.agents.budget.nodes import (
    budget_load_v2,
    budget_optimize,
    budget_validate,
    budget_explain,
    budget_filter,
    budget_fallback,
)
from app.agents.invest.nodes import (
    invest_fetch_data,
    invest_allocate,
    invest_validate,
    invest_explain,
    invest_filter,
    invest_fallback,
)
from app.agents.goal.nodes import (
    goal_define,
    goal_simulate,
    goal_validate,
    goal_explain,
    goal_filter,
    goal_fallback,
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
        return "budget_load_v2"   # Phase 5
    else:
        return "clarify"


def _route_after_budget_validate(state: VaultAIState) -> str:
    return "budget_explain" if state.get("validation_status") == ValidationStatus.PASSED \
        else "budget_fallback"


def _route_after_invest_validate(state: VaultAIState) -> str:
    return "invest_explain" if state.get("validation_status") == ValidationStatus.PASSED \
        else "invest_fallback"


def _route_after_goal_validate(state: VaultAIState) -> str:
    return "goal_explain" if state.get("validation_status") == ValidationStatus.PASSED \
        else "goal_fallback"


def _route_after_sim_validate(state: VaultAIState) -> str:
    return "plan_persist" if state.get("validation_status") == ValidationStatus.PASSED \
        else "sim_fallback"


# ===========================================================================
# SIMULATE STUBS — Phase 5
# ===========================================================================

def sim_run(state: VaultAIState) -> VaultAIState:
    """STUB Phase 5."""
    trace = append_trace(state, "sim_run")
    return {**state, "graph_trace": trace}

def sim_validate(state: VaultAIState) -> VaultAIState:
    """STUB Phase 5."""
    trace = append_trace(state, "sim_validate")
    return {**state, "graph_trace": trace,
            "validation_status": ValidationStatus.PASSED}

def sim_fallback(state: VaultAIState) -> VaultAIState:
    """STUB Phase 5."""
    trace = append_trace(state, "sim_fallback")
    return {**state, "graph_trace": trace}


# ===========================================================================
# SHARED TERMINAL NODES
# ===========================================================================

async def plan_persist(state: VaultAIState, config: RunnableConfig) -> VaultAIState:
    """
    The ONLY node that writes to the database.

    AsyncSession comes from config["configurable"]["db"] — injected by the
    route handler. Never stored in state to avoid msgpack serialisation errors.
    """
    trace = append_trace(state, "plan_persist")
    db    = (config.get("configurable") or {}).get("db")

    if db is None:
        logger.warning(
            "plan_persist: no db in config — skipping DB write (plan_id=None). "
            "Expected in unit tests only."
        )
        return {**state, "graph_trace": trace, "plan_id": None}

    from app.plans.service import persist_plan
    result = await persist_plan(state, db)
    return {**state, **result, "graph_trace": trace}


def clarify(state: VaultAIState) -> VaultAIState:
    """STUB Phase 6 — unknown intent."""
    trace = append_trace(state, "clarify")
    return {
        **state,
        "graph_trace": trace,
        "explanation_filtered": (
            "I'm not sure what type of financial plan you need. "
            "Try: 'Help me build a budget', 'Where should I invest Rs.50,000?', "
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

    # Budget
    builder.add_node("budget_load_v2",   budget_load_v2)
    builder.add_node("budget_optimize",  budget_optimize)
    builder.add_node("budget_validate",  budget_validate)
    builder.add_node("budget_explain",   budget_explain)
    builder.add_node("budget_filter",    budget_filter)
    builder.add_node("budget_fallback",  budget_fallback)

    # Invest
    builder.add_node("invest_fetch_data", invest_fetch_data)
    builder.add_node("invest_allocate",   invest_allocate)
    builder.add_node("invest_validate",   invest_validate)
    builder.add_node("invest_explain",    invest_explain)
    builder.add_node("invest_filter",     invest_filter)
    builder.add_node("invest_fallback",   invest_fallback)

    # Goal
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

    # ── Edges ─────────────────────────────────────────────────────────────

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
        {"budget_explain": "budget_explain", "budget_fallback": "budget_fallback"},
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
    Compile the VaultAI StateGraph. Called once at startup.

    Use ainvoke() from async route handlers:
        await graph.ainvoke(
            state,
            config={"configurable": {"thread_id": user_id, "db": db}},
        )
    """
    return _build_graph().compile(checkpointer=MemorySaver())
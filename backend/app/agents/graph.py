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
        return "combined_budget_start"   # Phase 5 — dedicated entry node
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


# COMBINED path — routing after each subgraph's terminal node
# budget_filter/fallback → combined_invest_start (if COMBINED) or plan_persist
# invest_filter/fallback → combined_goal_start  (if COMBINED) or plan_persist

def _route_after_budget_terminal(state: VaultAIState) -> str:
    if state.get("plan_type") == PlanType.COMBINED:
        return "combined_invest_start"
    return "plan_persist"


def _route_after_invest_terminal(state: VaultAIState) -> str:
    if state.get("plan_type") == PlanType.COMBINED:
        return "combined_goal_start"
    return "plan_persist"


# ===========================================================================
# COMBINED TRANSITION NODES
# ===========================================================================

def combined_budget_start(state: VaultAIState) -> VaultAIState:
    """
    Entry point for the COMBINED path.
    Resets validation state so each subgraph starts clean.
    """
    trace = append_trace(state, "combined_budget_start")
    logger.info("combined_budget_start: beginning COMBINED plan for user=%s",
                state.get("user_id"))
    return {
        **state,
        "graph_trace":       trace,
        "_combined_stage":   "budget",
        "validation_status": None,
        "validation_errors": [],
    }


def combined_invest_start(state: VaultAIState) -> VaultAIState:
    """
    Transition budget → invest in COMBINED path.
    Preserves budget projected_outcomes under 'budget_outcomes'.
    Clears per-subgraph keys so invest starts with a clean slate.
    """
    trace = append_trace(state, "combined_invest_start")
    logger.info("combined_invest_start: budget complete, starting invest")
    return {
        **state,
        "graph_trace":          trace,
        "_combined_stage":      "invest",
        "validation_status":    None,
        "validation_errors":    [],
        "budget_outcomes":      state.get("projected_outcomes"),  # preserve
        "projected_outcomes":   None,
        "assumptions":          None,
        "constraints":          None,
        "llm_explanation":      None,
        "explanation_filtered": None,
    }


def combined_goal_start(state: VaultAIState) -> VaultAIState:
    """
    Transition invest → goal in COMBINED path.
    Preserves invest projected_outcomes under 'invest_outcomes'.
    Injects budget monthly_savings into request_params for goal simulation
    if the user did not provide monthly_savings explicitly.
    """
    trace = append_trace(state, "combined_goal_start")
    invest_outcomes = state.get("projected_outcomes") or {}
    budget_outcomes = state.get("budget_outcomes") or {}

    # Propagate monthly_savings from budget to goal (only if not explicit)
    req_params = dict(state.get("request_params") or {})
    if "monthly_savings" not in req_params and budget_outcomes:
        monthly_sv = budget_outcomes.get("monthly_savings")
        if monthly_sv is not None:
            req_params["monthly_savings"] = monthly_sv

    logger.info("combined_goal_start: invest complete, starting goal")
    return {
        **state,
        "graph_trace":          trace,
        "_combined_stage":      "goal",
        "validation_status":    None,
        "validation_errors":    [],
        "invest_outcomes":      invest_outcomes,   # preserve
        "projected_outcomes":   None,
        "assumptions":          None,
        "constraints":          None,
        "llm_explanation":      None,
        "explanation_filtered": None,
        "request_params":       req_params,
    }


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

    INFEASIBLE GOAL GUARD (Phase 5):
    If plan_type is GOAL (or COMBINED in goal stage) and feasibility_label
    is INFEASIBLE, skip the DB write and return adjusted_timeline only.
    Spec: "INFEASIBLE: show adjusted_timeline only, no plan stored."

    AsyncSession comes from config["configurable"]["db"] — injected by the
    route handler. Never stored in state to avoid msgpack serialisation errors.
    """
    trace    = append_trace(state, "plan_persist")
    db       = (config.get("configurable") or {}).get("db")
    outcomes = state.get("projected_outcomes") or {}

    # ── INFEASIBLE goal guard ─────────────────────────────────────────────
    plan_type = state.get("plan_type")
    stage     = state.get("_combined_stage", "")
    is_goal_plan = (
        plan_type == PlanType.GOAL or
        (plan_type == PlanType.COMBINED and stage == "goal")
    )
    if is_goal_plan and outcomes.get("feasibility_label") == "INFEASIBLE":
        logger.info(
            "plan_persist: INFEASIBLE goal — skipping DB write, "
            "returning adjusted_timeline only"
        )
        return {
            **state,
            "graph_trace": trace,
            "plan_id":     None,
            "adjusted_timeline": {
                "stored":                False,
                "reason":                "INFEASIBLE — plan not stored per policy",
                "contribution_required": outcomes.get("contribution_required", 0),
                "gap_amount":            outcomes.get("gap_amount", 0),
                "coverage_ratio":        outcomes.get("coverage_ratio", 0),
                "explanation":           state.get("explanation_filtered", ""),
            },
        }

    # ── No DB (unit tests) ────────────────────────────────────────────────
    if db is None:
        logger.warning(
            "plan_persist: no db in config — skipping DB write (plan_id=None). "
            "Expected in unit tests only."
        )
        return {**state, "graph_trace": trace, "plan_id": None}

    # ── Normal DB write ───────────────────────────────────────────────────
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

    # COMBINED transition nodes
    builder.add_node("combined_budget_start", combined_budget_start)
    builder.add_node("combined_invest_start", combined_invest_start)
    builder.add_node("combined_goal_start",   combined_goal_start)

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
            "budget_load_v2":        "budget_load_v2",
            "invest_fetch_data":     "invest_fetch_data",
            "goal_define":           "goal_define",
            "sim_run":               "sim_run",
            "combined_budget_start": "combined_budget_start",
            "clarify":               "clarify",
        },
    )

    # COMBINED entry
    builder.add_edge("combined_budget_start", "budget_load_v2")

    # Budget chain
    builder.add_edge("budget_load_v2",  "budget_optimize")
    builder.add_edge("budget_optimize", "budget_validate")
    builder.add_conditional_edges(
        "budget_validate",
        _route_after_budget_validate,
        {"budget_explain": "budget_explain", "budget_fallback": "budget_fallback"},
    )
    builder.add_edge("budget_explain", "budget_filter")
    # budget_filter + budget_fallback: standalone → plan_persist, COMBINED → invest
    builder.add_conditional_edges(
        "budget_filter",
        _route_after_budget_terminal,
        {"combined_invest_start": "combined_invest_start", "plan_persist": "plan_persist"},
    )
    builder.add_conditional_edges(
        "budget_fallback",
        _route_after_budget_terminal,
        {"combined_invest_start": "combined_invest_start", "plan_persist": "plan_persist"},
    )

    # COMBINED invest transition
    builder.add_edge("combined_invest_start", "invest_fetch_data")

    # Invest chain
    builder.add_edge("invest_fetch_data", "invest_allocate")
    builder.add_edge("invest_allocate",   "invest_validate")
    builder.add_conditional_edges(
        "invest_validate",
        _route_after_invest_validate,
        {"invest_explain": "invest_explain", "invest_fallback": "invest_fallback"},
    )
    builder.add_edge("invest_explain", "invest_filter")
    # invest_filter + invest_fallback: standalone → plan_persist, COMBINED → goal
    builder.add_conditional_edges(
        "invest_filter",
        _route_after_invest_terminal,
        {"combined_goal_start": "combined_goal_start", "plan_persist": "plan_persist"},
    )
    builder.add_conditional_edges(
        "invest_fallback",
        _route_after_invest_terminal,
        {"combined_goal_start": "combined_goal_start", "plan_persist": "plan_persist"},
    )

    # COMBINED goal transition
    builder.add_edge("combined_goal_start", "goal_define")

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
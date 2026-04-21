"""
VaultAI LLMOps — Phase 1: Structured Logging
app/agents/ops_logger.py   ← NEW FILE

Drop into: backend/app/agents/ops_logger.py

Usage in any node:
    from app.agents.ops_logger import log_node_start, log_node_end

    def budget_optimize(state):
        log_node_start("budget_optimize", "budget", list(state.keys()))
        t0 = time.perf_counter()
        ...
        log_node_end("budget_optimize", "budget",
                     round((time.perf_counter() - t0)*1000, 1),
                     "success", {"savings_rate": 0.22, "monthly_savings": 14400})
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("vaultai.agents")


def log_node_start(node_name: str, plan_type: str, state_keys: list[str]) -> None:
    """Emit structured JSON at the start of a LangGraph node."""
    logger.info(json.dumps({
        "event":               "node_start",
        "node":                node_name,
        "plan_type":           plan_type,
        "state_keys_available": state_keys,
    }))


def log_node_end(
    node_name:   str,
    plan_type:   str,
    duration_ms: float,
    status:      str,        # "success" | "fallback" | "failed"
    metrics:     dict[str, Any],
) -> None:
    """Emit structured JSON at the end of a LangGraph node."""
    logger.info(json.dumps({
        "event":       "node_end",
        "node":        node_name,
        "plan_type":   plan_type,
        "duration_ms": duration_ms,
        "status":      status,
        **metrics,
    }))


def log_llm_call(
    plan_type:         str,
    model:             str,
    prompt_tokens:     int,
    completion_tokens: int,
    latency_ms:        float,
    degraded:          bool = False,
) -> None:
    """Emit structured JSON after every Groq LLM call."""
    logger.info(json.dumps({
        "event":             "llm_call",
        "plan_type":         plan_type,
        "model":             model,
        "prompt_tokens":     prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens":      prompt_tokens + completion_tokens,
        "latency_ms":        latency_ms,
        "degraded":          degraded,
    }))


def log_confidence_scored(
    plan_type:       str,
    overall:         float,
    data_coverage:   float,
    window_score:    float,
    stability_score: float,
    rag_score:       float,
    degraded:        bool = False,
) -> None:
    """Emit structured JSON after confidence scoring."""
    logger.info(json.dumps({
        "event":                      "confidence_scored",
        "plan_type":                  plan_type,
        "confidence_overall":         round(overall, 4),
        "confidence_data_coverage":   round(data_coverage, 4),
        "confidence_window_score":    round(window_score, 4),
        "confidence_stability_score": round(stability_score, 4),
        "confidence_rag_score":       round(rag_score, 4),
        "degraded":                   degraded,
    }))


def log_hitl_trigger(
    plan_type:      str,
    missing_fields: list[str],
    message_length: int,
) -> None:
    """Emit structured JSON when a 422 HITL is triggered."""
    logger.info(json.dumps({
        "event":               "hitl_triggered",
        "plan_type":           plan_type,
        "missing_fields":      missing_fields,
        "missing_field_count": len(missing_fields),
        "message_length":      message_length,
    }))


def log_plan_persisted(
    plan_id:            str,
    plan_type:          str,
    confidence_overall: float,
    degraded:           bool,
    user_id_hash:       str,
) -> None:
    """Emit structured JSON when a plan is persisted to DB."""
    logger.info(json.dumps({
        "event":              "plan_persisted",
        "plan_id":            plan_id,
        "plan_type":          plan_type,
        "confidence_overall": round(confidence_overall, 4),
        "degraded":           degraded,
        "user_id_hash":       user_id_hash,
    }))


# ── One-time setup ────────────────────────────────────────────────────────────

def configure_logging(log_level: str = "INFO") -> None:
    """
    Configure vaultai.ops and vaultai.agents loggers to emit plain JSON lines.
    Call once in app/main.py before startup.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    for name in ("vaultai.ops", "vaultai.agents"):
        lg = logging.getLogger(name)
        lg.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        if not lg.handlers:
            lg.addHandler(handler)
        lg.propagate = False
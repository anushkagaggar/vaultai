"""
VaultAI LLMOps — Phase 2: MLflow Experiment Tracking
app/agents/mlflow_tracker.py   ← NEW FILE

Drop into: backend/app/agents/mlflow_tracker.py

Setup:
  pip install mlflow>=2.13
  mlflow server --host 0.0.0.0 --port 5000
  Add to .env:  MLFLOW_TRACKING_URI=http://localhost:5000

Called automatically by instrumented node files — no manual wiring needed
beyond the startup call in main.py.
"""

from __future__ import annotations

import logging
import os
from typing import Callable, Any

logger = logging.getLogger("vaultai.agents")

_EXPERIMENTS: dict[str, str] = {}

EXPERIMENT_NAMES = {
    "plan_runs":   "vaultai/plan-runs",
    "llm_calls":   "vaultai/llm-calls",
    "agent_nodes": "vaultai/agent-nodes",
    "eval_runs":   "vaultai/eval-runs",
}


def init_mlflow_experiments() -> None:
    """
    Create (or look up) the four VaultAI MLflow experiments.
    Call once inside startup_event() in main.py.
    Degrades silently if MLflow server is not reachable.
    """
    import json
    try:
        import mlflow
        uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        mlflow.set_tracking_uri(uri)
        for key, name in EXPERIMENT_NAMES.items():
            exp = mlflow.get_experiment_by_name(name)
            _EXPERIMENTS[key] = (
                exp.experiment_id if exp else mlflow.create_experiment(name)
            )
        logger.info(json.dumps({
            "event":        "mlflow_initialized",
            "tracking_uri": uri,
        }))
    except Exception as exc:
        logger.warning(json.dumps({
            "event":  "mlflow_init_skipped",
            "reason": str(exc),
        }))


# ── Per-node tracking helpers ─────────────────────────────────────────────────

def track_agent_node(
    node_name:    str,
    plan_type:    str,
    duration_ms:  float,
    status:       str,
    node_metrics: dict,
) -> None:
    """Log a single LangGraph node execution to vaultai/agent-nodes."""
    _run_safely("agent_nodes", lambda mlflow: _log_node(
        mlflow, node_name, plan_type, duration_ms, status, node_metrics
    ))


def track_llm_call(
    plan_type:         str,
    model:             str,
    prompt_tokens:     int,
    completion_tokens: int,
    latency_ms:        float,
    prompt_text:       str = "",
    explanation:       str = "",
) -> None:
    """Log a single Groq LLM call to vaultai/llm-calls."""
    _run_safely("llm_calls", lambda mlflow: _log_llm(
        mlflow, plan_type, model, prompt_tokens,
        completion_tokens, latency_ms, prompt_text, explanation
    ))


# ── Internal helpers ──────────────────────────────────────────────────────────

def _run_safely(exp_key: str, fn: Callable) -> None:
    """Run an MLflow logging call; swallow all errors so request path is unaffected."""
    exp_id = _EXPERIMENTS.get(exp_key)
    if not exp_id:
        return
    try:
        import mlflow
        with mlflow.start_run(experiment_id=exp_id):
            fn(mlflow)
    except Exception as exc:
        import json
        logger.warning(json.dumps({"event": "mlflow_track_error", "error": str(exc)}))


def _log_node(mlflow, node_name, plan_type, duration_ms, status, node_metrics):
    mlflow.log_params({
        "node_name":    node_name,
        "plan_type":    plan_type,
        "status":       status,
        "fallback_path": node_metrics.get("fallback_path", "none"),
    })
    numeric = {
        k: float(v)
        for k, v in node_metrics.items()
        if isinstance(v, (int, float)) and k != "fallback_path"
    }
    numeric["duration_ms"] = float(duration_ms)
    mlflow.log_metrics(numeric)


def _log_llm(mlflow, plan_type, model, prompt_tokens,
             completion_tokens, latency_ms, prompt_text, explanation):
    mlflow.log_params({"plan_type": plan_type, "groq_model": model})
    mlflow.log_metrics({
        "llm_latency_ms":           float(latency_ms),
        "prompt_tokens":            float(prompt_tokens),
        "completion_tokens":        float(completion_tokens),
        "total_tokens":             float(prompt_tokens + completion_tokens),
        "explanation_length_chars": float(len(explanation)),
    })
    if prompt_text:
        mlflow.log_text(prompt_text[:2000], "prompt.txt")
    if explanation:
        mlflow.log_text(explanation, "explanation.txt")
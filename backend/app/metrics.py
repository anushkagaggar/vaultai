"""
VaultAI LLMOps — Phase 3: Prometheus Metrics
app/metrics.py   ← NEW FILE

Drop into: backend/app/metrics.py

Setup:
  pip install prometheus-fastapi-instrumentator>=6.1 prometheus-client>=0.20

All metric objects are module-level singletons.
Import only what you need in each node file.

Quick usage reference:
  # In a node after computing results:
  from app.metrics import node_duration, plan_counter
  node_duration.labels("budget_optimize", "budget").observe(dur_seconds)
  plan_counter.labels("budget", "success").inc()

  # In LLM client after Groq response:
  from app.metrics import llm_latency, token_counter
  llm_latency.labels("budget").observe(latency_seconds)
  token_counter.labels("prompt").inc(prompt_tokens)
"""

from prometheus_client import Counter, Histogram, Gauge

# ── Plan generation counters ──────────────────────────────────────────────────
plan_counter = Counter(
    "vaultai_plans_total",
    "Total plans generated",
    ["plan_type", "status"],   # status: success | degraded | failed
)

# ── LLM latency histogram ─────────────────────────────────────────────────────
llm_latency = Histogram(
    "vaultai_llm_latency_seconds",
    "Groq API call duration in seconds",
    ["plan_type"],
    buckets=[0.5, 1.0, 2.0, 4.0, 8.0, 16.0],
)

# ── Token usage counters ──────────────────────────────────────────────────────
token_counter = Counter(
    "vaultai_llm_tokens_total",
    "Total LLM tokens used",
    ["direction"],   # prompt | completion
)

# ── Confidence score gauges ───────────────────────────────────────────────────
# Label examples: "budget_overall", "budget_coverage", "invest_overall" …
confidence_gauge = Gauge(
    "vaultai_confidence_score_current",
    "Most recent confidence score per plan type / sub-dimension",
    ["plan_type"],
)

# ── HITL trigger counter ──────────────────────────────────────────────────────
hitl_counter = Counter(
    "vaultai_hitl_triggers_total",
    "HITL forms triggered (intent classifier fell back to form)",
    ["plan_type", "missing_field"],
)

# ── Execution state transitions ───────────────────────────────────────────────
execution_state_counter = Counter(
    "vaultai_execution_transitions_total",
    "Execution state machine transitions",
    ["plan_type", "to_state"],   # to_state: running | success | fallback | failed
)

# ── Agent node duration histogram ─────────────────────────────────────────────
node_duration = Histogram(
    "vaultai_node_duration_seconds",
    "LangGraph node execution time in seconds",
    ["node_name", "plan_type"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 3.0, 8.0],
)

# ── RAG retrieval latency ─────────────────────────────────────────────────────
rag_latency = Histogram(
    "vaultai_rag_retrieval_seconds",
    "Qdrant vector search latency in seconds",
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 2.0],
)


# ── Convenience function used by confidence/scorer.py ────────────────────────

def record_confidence_scores(
    plan_type: str,
    coverage:  float,
    window:    float,
    stability: float,
    rag:       float,
) -> float:
    """
    Compute overall confidence and push all four sub-scores to Prometheus.
    Formula matches V3 scorer: 0.35×cov + 0.25×win + 0.25×stab + 0.15×rag

    Returns overall confidence so callers don't have to recompute it.
    """
    overall = 0.35 * coverage + 0.25 * window + 0.25 * stability + 0.15 * rag
    overall = round(min(max(overall, 0.0), 1.0), 4)

    confidence_gauge.labels(f"{plan_type}_overall").set(overall)
    confidence_gauge.labels(f"{plan_type}_coverage").set(coverage)
    confidence_gauge.labels(f"{plan_type}_window").set(window)
    confidence_gauge.labels(f"{plan_type}_stability").set(stability)
    confidence_gauge.labels(f"{plan_type}_rag").set(rag)

    return overall
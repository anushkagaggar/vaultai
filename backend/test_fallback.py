import asyncio
from app.validation.diagnostic import (
    build_validation_report,
    extract_numbers,
    collect_metric_numbers
)
from app.validation.decision import decide, ExecutionDecision

# Simulate LLM output with wrong numbers
llm_output = "The current month total was $9999."

metrics = {
    "rolling": {"30_day_avg": 500, "60_day_avg": 450, "90_day_avg": 985},
    "monthly": {"current_month": 3250, "previous_month": 100, "percent_change": 3150},
    "categories": [
        {"category": "rent", "total": 6000},
        {"category": "food", "total": 3250}
    ]
}

rag_text = ""

# ✅ DEBUG: Show extracted numbers
print("=== DEBUGGING ===")
print(f"LLM output: {llm_output}")
print(f"Numbers found in LLM output: {extract_numbers(llm_output)}")
print(f"Numbers in metrics: {collect_metric_numbers(metrics)}")
print()

# Build report
report = build_validation_report(llm_output, metrics, rag_text)

print("=== REPORT ===")
print(f"  numbers_ok: {report.numbers_ok}")
print(f"  forbidden_language_ok: {report.forbidden_language_ok}")
print(f"  rag_supported: {report.rag_supported}")
print(f"  has_content: {report.has_content}")
print(f"  reasoning_quality: {report.reasoning_quality}")
print(f"  issues: {report.issues}")

# Make decision
decision = decide(report)

print(f"\n=== DECISION ===")
print(f"Result: {decision.value}")
print(f"Expected: fallback")
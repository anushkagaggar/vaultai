from enum import Enum
from app.validation.diagnostic import ValidationReport


class ExecutionDecision(Enum):
    """
    Final classification of execution outcome.
    This is the ONLY authority that determines what happens to an execution.
    """
    SUCCESS = "success"
    FALLBACK = "fallback"
    SUPPRESS = "suppress"


def decide(report: ValidationReport) -> ExecutionDecision:
    """
    Deterministic decision engine that converts diagnostic report into action.
    
    CRITICAL: Rules are evaluated in strict priority order.
    DO NOT reorder - doing so breaks determinism.
    
    Priority:
    1. Suppression (highest) - never show output
    2. Fallback (medium) - show degraded insight
    3. Success (default) - show full insight
    """
    
    # =====================================================
    # PRIORITY 1: SUPPRESSION RULES (Highest Priority)
    # =====================================================
    # Never allow storage or display of dangerous output
    
    # Rule 1.1: Empty or missing content
    if not report.has_content:
        return ExecutionDecision.SUPPRESS
    
    # Rule 1.2: Unsafe reasoning (contradictions, nonsense)
    if report.reasoning_quality == "unsafe":
        return ExecutionDecision.SUPPRESS
    
    # Rule 1.3: Hallucinated numbers without ANY evidence
    # (numbers wrong AND no RAG support = pure hallucination)
    if not report.numbers_ok and not report.rag_supported:
        return ExecutionDecision.SUPPRESS
    
    # =====================================================
    # PRIORITY 2: FALLBACK RULES (Medium Priority)
    # =====================================================
    # Allow analytics-only explanation (degraded but safe)
    
    # Rule 2.1: Numbers unverifiable but documented in RAG
    # (we can't verify, but user uploaded docs support it)
    if not report.numbers_ok and report.rag_supported:
        return ExecutionDecision.FALLBACK
    
    # Rule 2.2: Forbidden speculative language detected
    if not report.forbidden_language_ok:
        return ExecutionDecision.FALLBACK
    
    # Rule 2.3: Weak reasoning quality (minor issues)
    if report.reasoning_quality == "weak":
        return ExecutionDecision.FALLBACK
    
    # =====================================================
    # PRIORITY 3: SUCCESS (Default)
    # =====================================================
    # All checks passed - full insight approved
    
    return ExecutionDecision.SUCCESS


# =====================================================
# HELPER: Human-readable explanation of decision
# =====================================================

def explain_decision(report: ValidationReport, decision: ExecutionDecision) -> str:
    """
    Generate human-readable explanation of why a decision was made.
    Useful for debugging and transparency.
    """
    
    if decision == ExecutionDecision.SUPPRESS:
        if not report.has_content:
            return "Output suppressed: No meaningful content generated"
        elif report.reasoning_quality == "unsafe":
            return "Output suppressed: Unsafe reasoning detected (contradictions/nonsense)"
        elif not report.numbers_ok and not report.rag_supported:
            return "Output suppressed: Hallucinated numbers without evidence"
        else:
            return "Output suppressed: Multiple safety violations"
    
    elif decision == ExecutionDecision.FALLBACK:
        if not report.numbers_ok and report.rag_supported:
            return "Fallback: Numbers unverifiable but supported by user documents"
        elif not report.forbidden_language_ok:
            return "Fallback: Speculative language detected"
        elif report.reasoning_quality == "weak":
            return "Fallback: Weak reasoning quality"
        else:
            return "Fallback: Minor quality issues detected"
    
    else:  # SUCCESS
        return "Success: All validation checks passed"
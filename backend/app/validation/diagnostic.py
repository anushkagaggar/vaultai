from dataclasses import dataclass
from typing import Literal
import re
import math


@dataclass
class ValidationReport:
    """
    Structured diagnostic report for LLM output quality.
    
    This is NOT a pass/fail verdict - it's a detailed analysis
    that later stages use to make decisions.
    """
    numbers_ok: bool
    forbidden_language_ok: bool
    rag_supported: bool
    has_content: bool
    reasoning_quality: Literal["good", "weak", "unsafe"]
    classification_hint: Literal["success", "fallback", "suppress"]
    
    # Debug info
    issues: list[str]  # Human-readable list of problems found


# =====================================================
# FORBIDDEN PHRASES (from your existing validator)
# =====================================================

FORBIDDEN_PHRASES = [
    "you should invest",
    "you should buy", 
    "you should sell",
    "i recommend",
    "my recommendation",
    "my advice",
    "guaranteed",
    "will definitely",
    "predicted to",
    "forecast"
]

GENERIC_PHRASES = [
    "the data shows",
    "according to the information",
    "based on the metrics",
    "the analysis indicates",
]


# =====================================================
# HELPER: Number Extraction (reused from validator)
# =====================================================

def extract_numbers(text: str) -> list[float]:
    """
    Extract numeric values from text while EXCLUDING:
    - Years (2020-2099)
    - Dates (patterns like 2026-02-12)
    - Ordinals (1st, 2nd, 3rd)
    - Time (3:30)
    - Small integers < 100 (likely days/counts)
    """
    # Remove date patterns
    cleaned = re.sub(r'\b(19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b', '', text)
    cleaned = re.sub(r'\b\d{1,2}:\d{2}\b', '', cleaned)
    cleaned = re.sub(r'\b\d+(st|nd|rd|th)\b', '', cleaned, flags=re.IGNORECASE)
    
    # Extract numbers (including comma-separated)
    pattern = r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b'
    raw = re.findall(pattern, cleaned)
    
    nums = []
    for x in raw:
        val = float(x.replace(',', ''))
        
        # Filter out years and small numbers
        if 2020 <= val <= 2099:
            continue
        if val < 100:
            continue
        
        nums.append(val)
    
    return nums


def collect_metric_numbers(metrics: dict) -> set[float]:
    """Collect all numeric values from metrics."""
    nums = set()
    
    # Rolling averages
    for v in metrics.get("rolling", {}).values():
        nums.add(round(float(v), 2))
    
    # Monthly metrics
    for v in metrics.get("monthly", {}).values():
        if v is not None:
            nums.add(round(float(v), 2))
    
    # Category totals
    for c in metrics.get("categories", []):
        nums.add(round(float(c["total"]), 2))
    
    return nums


# =====================================================
# CHECK 1: Content Quality
# =====================================================

def check_content_quality(text: str) -> tuple[bool, list[str]]:
    """
    Detect useless or empty output.
    
    Returns:
        (has_content: bool, issues: list[str])
    """
    issues = []
    
    # Empty or very short
    if not text or len(text.strip()) < 20:
        issues.append("Output too short (< 20 chars)")
        return False, issues
    
    # Only generic phrases (lazy LLM output)
    stripped = text.lower()
    only_generic = all(
        phrase in stripped 
        for phrase in GENERIC_PHRASES
    )
    
    if only_generic:
        issues.append("Output contains only generic phrases")
        return False, issues
    
    return True, issues


# =====================================================
# CHECK 2: Numeric Consistency
# =====================================================

def check_numeric_consistency(
    text: str,
    metrics: dict,
    rag_text: str = ""
) -> tuple[bool, list[str]]:
    """
    Verify numbers in explanation exist in metrics or RAG.
    
    Returns:
        (numbers_ok: bool, issues: list[str])
    """
    issues = []
    
    found_nums = extract_numbers(text)
    if not found_nums:
        return True, issues  # No numbers to validate
    
    metric_nums = collect_metric_numbers(metrics)
    rag_nums = set(extract_numbers(rag_text)) if rag_text else set()
    allowed = metric_nums.union(rag_nums)
    
    invalid = []
    for num in found_nums:
        matched = False
        for approved in allowed:
            if math.isclose(num, approved, rel_tol=0.05, abs_tol=10.0):
                matched = True
                break
        
        if not matched:
            invalid.append(num)
    
    if invalid:
        issues.append(f"Unapproved numbers found: {invalid}")
        return False, issues
    
    return True, issues


# =====================================================
# CHECK 3: Forbidden Language
# =====================================================

def check_forbidden_language(text: str) -> tuple[bool, list[str]]:
    """
    Detect speculative or advisory language.
    
    Returns:
        (no_forbidden: bool, issues: list[str])
    """
    issues = []
    lowered = text.lower()
    
    found = []
    for phrase in FORBIDDEN_PHRASES:
        if phrase in lowered:
            found.append(phrase)
    
    if found:
        issues.append(f"Forbidden phrases detected: {found}")
        return False, issues
    
    return True, issues


# =====================================================
# CHECK 4: RAG Support
# =====================================================

def check_rag_support(
    text: str,
    metrics: dict,
    rag_text: str = ""
) -> tuple[bool, list[str]]:
    """
    Check if explanation is grounded in available context.
    
    Returns:
        (rag_supported: bool, issues: list[str])
    """
    issues = []
    
    found_nums = extract_numbers(text)
    metric_nums = collect_metric_numbers(metrics)
    
    # Find numbers NOT in metrics
    external_nums = [
        num for num in found_nums
        if not any(
            math.isclose(num, m, rel_tol=0.05, abs_tol=10.0)
            for m in metric_nums
        )
    ]
    
    # If using external numbers but no RAG context
    if external_nums and not rag_text:
        issues.append(f"Numbers not in metrics and no RAG support: {external_nums}")
        return False, issues
    
    return True, issues


# =====================================================
# CHECK 5: Reasoning Quality Estimation
# =====================================================

def estimate_reasoning_quality(
    numbers_ok: bool,
    forbidden_language_ok: bool,
    rag_supported: bool,
    has_content: bool
) -> Literal["good", "weak", "unsafe"]:
    """
    Deterministic quality heuristic.
    
    Rules:
    - good: all checks pass
    - weak: numbers mismatch OR speculative language OR missing RAG
    - unsafe: no content OR multiple failures
    """
    
    if not has_content:
        return "unsafe"
    
    # Count failures
    failures = sum([
        not numbers_ok,
        not forbidden_language_ok,
        not rag_supported
    ])
    
    if failures == 0:
        return "good"
    elif failures >= 2:
        return "unsafe"
    else:
        return "weak"


# =====================================================
# CHECK 6: Classification Hint
# =====================================================

def suggest_classification(
    reasoning_quality: Literal["good", "weak", "unsafe"]
) -> Literal["success", "fallback", "suppress"]:
    """
    Map quality to suggested action.
    
    This is NOT a final decision - just a recommendation.
    """
    if reasoning_quality == "good":
        return "success"
    elif reasoning_quality == "weak":
        return "fallback"
    else:
        return "suppress"


# =====================================================
# MAIN DIAGNOSTIC BUILDER
# =====================================================

def build_validation_report(
    explanation: str,
    metrics: dict,
    rag_text: str = ""
) -> ValidationReport:
    """
    Build comprehensive diagnostic report for LLM output.
    
    This is the single source of truth for all later decisions.
    """
    all_issues = []
    
    # Run all checks
    has_content, content_issues = check_content_quality(explanation)
    all_issues.extend(content_issues)
    
    numbers_ok, number_issues = check_numeric_consistency(explanation, metrics, rag_text)
    all_issues.extend(number_issues)
    
    forbidden_ok, forbidden_issues = check_forbidden_language(explanation)
    all_issues.extend(forbidden_issues)
    
    rag_supported, rag_issues = check_rag_support(explanation, metrics, rag_text)
    all_issues.extend(rag_issues)
    
    # Derive quality and classification
    quality = estimate_reasoning_quality(
        numbers_ok=numbers_ok,
        forbidden_language_ok=forbidden_ok,
        rag_supported=rag_supported,
        has_content=has_content
    )
    
    classification = suggest_classification(quality)
    
    return ValidationReport(
        numbers_ok=numbers_ok,
        forbidden_language_ok=forbidden_ok,
        rag_supported=rag_supported,
        has_content=has_content,
        reasoning_quality=quality,
        classification_hint=classification,
        issues=all_issues if all_issues else ["No issues detected"]
    )
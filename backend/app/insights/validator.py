import re
import math
import logging

logger = logging.getLogger(__name__)

FORBIDDEN_WORDS = [
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


# ----------------------------
# Number Extraction
# ----------------------------

def extract_numbers(text: str):
    """
    Extract numeric values from text, ignoring dates and day counts.
    """
    # Find all numbers including decimals
    raw = re.findall(r"\d+\.?\d*", text)
    
    nums = []
    for x in raw:
        val = float(x)
        # Ignore very small numbers (dates, day counts, percentages < 100)
        if val >= 100:
            nums.append(val)
    
    return nums


# ----------------------------
# Metric Collection
# ----------------------------

def collect_metric_numbers(metrics: dict):
    """
    Collect all numeric values from metrics as floats.
    """
    nums = set()  # Use set to avoid duplicates

    # Rolling averages
    for v in metrics["rolling"].values():
        nums.add(round(float(v), 2))

    # Monthly metrics
    for v in metrics["monthly"].values():
        if v is not None:
            nums.add(round(float(v), 2))

    # Category totals
    for c in metrics["categories"]:
        nums.add(round(float(c["total"]), 2))

    return nums


# ----------------------------
# Numeric Validator
# ----------------------------

def validate_numbers(text: str, metrics: dict, rag_text: str = "") -> bool:
    """
    Validate that numbers in text come from either:
    1. Computed metrics, OR
    2. RAG documents (allowed source)
    
    Rejects only numbers that appear nowhere in approved sources.
    """
    found = extract_numbers(text)
    
    if not found:
        # No numbers found, that's fine
        return True
    
    # Get approved numbers from metrics
    approved_metrics = collect_metric_numbers(metrics)
    
    # Get approved numbers from RAG documents
    approved_rag = set(extract_numbers(rag_text)) if rag_text else set()
    
    # Combine all approved numbers
    all_approved = approved_metrics.union(approved_rag)
    
    logger.debug(f"Found numbers in LLM output: {found}")
    logger.debug(f"Approved from metrics: {approved_metrics}")
    logger.debug(f"Approved from RAG: {approved_rag}")
    
    unapproved = []
    
    for f in found:
        matched = False
        
        for approved in all_approved:
            # Lenient tolerance for rounding
            if math.isclose(f, approved, rel_tol=0.05, abs_tol=10.0):
                matched = True
                break
        
        if not matched:
            unapproved.append(f)
    
    # Allow some flexibility: max 2 unapproved numbers OR < 20% unapproved
    unapproved_ratio = len(unapproved) / len(found) if found else 0
    
    if len(unapproved) > 2 and unapproved_ratio > 0.2:
        logger.warning(f"Too many unapproved numbers: {unapproved}")
        return False
    
    return True


# ----------------------------
# Main Validator
# ----------------------------

def validate_explanation(text: str, metrics: dict, rag_text: str = "") -> bool:
    """
    Validate LLM explanation against:
    1. Forbidden speculative language (phrases, not individual words)
    2. Numbers must come from metrics OR RAG documents
    """
    
    # 1. No forbidden language (check for phrases, not just words)
    lowered = text.lower()
    
    for phrase in FORBIDDEN_WORDS:
        if phrase in lowered:
            logger.warning(f"Found forbidden phrase: {phrase}")
            return False

    # 2. Validate numbers against both metrics AND RAG
    if not validate_numbers(text, metrics, rag_text):
        logger.warning("Number validation failed")
        return False

    logger.info("Validation passed!")
    return True
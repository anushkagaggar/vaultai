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
# Number Extraction (HARDENED)
# ----------------------------

def extract_numbers(text: str):
    """
    Extract numeric values from text while EXCLUDING:
    - Years (2020-2099)
    - Dates (patterns like 2026-02-12)
    - Ordinals (1st, 2nd, 3rd)
    - Time (3:30, 8.5 hours)
    - Small integers likely to be counts/days (< 32)
    
    ONLY extract financial amounts.
    """
    # Remove dollar signs first
    text = text.replace('$', '')  # ✅ NEW

    
    # Remove common date patterns first
    cleaned = re.sub(r'\b(19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b', '', text)  # 2026-02-12
    cleaned = re.sub(r'\b\d{1,2}:\d{2}\b', '', cleaned)  # 3:30
    cleaned = re.sub(r'\b\d+(st|nd|rd|th)\b', '', cleaned, flags=re.IGNORECASE)  # 1st, 2nd
    
    # Extract numbers (including comma-separated: $1,234.56)
    # Matches: 1234.56 or 1,234.56
    pattern = r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b'
    raw = re.findall(pattern, cleaned)
    
    nums = []
    for x in raw:
        # Remove commas and convert
        val = float(x.replace(',', ''))
        
        # Filter out:
        # - Years (2020-2099)
        # - Small day/count numbers (1-31)
        # - Percentages > 1000 without context (likely 2950% = actual value is 2950.0)
        if 2020 <= val <= 2099:
            continue  # Skip years
        if val < 100:
            continue  # Skip small numbers (days, counts, percentages)
        
        nums.append(val)
    
    return nums


# ----------------------------
# Metric Collection (UNCHANGED)
# ----------------------------

def collect_metric_numbers(metrics: dict):
    """
    Collect all numeric values from metrics as floats.
    """
    nums = set()

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
# Numeric Validator (WITH TOLERANCE)
# ----------------------------

def validate_numbers(text: str, metrics: dict, rag_text: str = "") -> bool:
    """
    A number is valid if it exists in:
    - computed metrics (with rounding tolerance)
    - OR retrieved RAG text (with rounding tolerance)
    """

    found = extract_numbers(text)
    if not found:
        return True

    metric_nums = collect_metric_numbers(metrics)
    rag_nums = set(extract_numbers(rag_text)) if rag_text else set()

    allowed = metric_nums.union(rag_nums)

    logger.debug(f"LLM numbers: {found}")
    logger.debug(f"Metric numbers: {metric_nums}")
    logger.debug(f"RAG numbers: {rag_nums}")

    invalid = []
    
    for num in found:
        matched = False
        
        # Check against all allowed numbers with tolerance
        for approved in allowed:
            # Allow ±5% relative error or ±10 absolute error
            if math.isclose(num, approved, rel_tol=0.05, abs_tol=10.0):
                matched = True
                break
        
        if not matched:
            invalid.append(num)

    if invalid:
        logger.warning(f"Numbers not grounded in data: {invalid}")
        return False

    return True


# ----------------------------
# Main Validator (UNCHANGED)
# ----------------------------

def validate_explanation(text: str, metrics: dict, rag_text: str = "") -> bool:
    """
    Validate LLM explanation against:
    1. Forbidden speculative language
    2. Numbers must come from metrics OR RAG documents
    """
    
    # 1. No forbidden language
    lowered = text.lower()
    
    for phrase in FORBIDDEN_WORDS:
        if phrase in lowered:
            logger.warning(f"Found forbidden phrase: {phrase}")
            return False

    # 2. Validate numbers
    if not validate_numbers(text, metrics, rag_text):
        logger.warning("Number validation failed")
        return False

    logger.info("Validation passed!")
    return True
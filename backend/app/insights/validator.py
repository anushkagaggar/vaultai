import re
import math


FORBIDDEN_WORDS = [
    "invest",
    "should",
    "recommend",
    "advice",
    "guarantee",
    "profit"
]


# ----------------------------
# Number Extraction
# ----------------------------

def extract_numbers(text: str):
    """
    Extract numeric values but ignore window indicators
    like 30 days, 90 days, etc.
    """

    raw = re.findall(r"\d+\.?\d*", text)

    nums = []

    for x in raw:

        val = float(x)

        # Ignore small integers (likely days/windows)
        if val.is_integer() and val < 100:
            continue

        nums.append(val)

    return nums


# ----------------------------
# Metric Collection
# ----------------------------

def collect_metric_numbers(metrics: dict):
    """
    Collect all numeric values from metrics as floats.
    """

    nums = []

    # Rolling averages
    for v in metrics["rolling"].values():
        nums.append(float(v))

    # Monthly metrics
    for v in metrics["monthly"].values():
        if v is not None:
            nums.append(float(v))

    # Category totals
    for c in metrics["categories"]:
        nums.append(float(c["total"]))

    return nums


# ----------------------------
# Numeric Validator
# ----------------------------

def validate_numbers(text: str, metrics: dict) -> bool:

    found = extract_numbers(text)
    expected = collect_metric_numbers(metrics)

    for f in found:

        matched = False

        for e in expected:

            # Relative + absolute tolerance
            if math.isclose(f, e, rel_tol=0.01, abs_tol=0.5):
                matched = True
                break

        if not matched:
            return False

    return True


# ----------------------------
# Main Validator
# ----------------------------

def validate_explanation(text: str, metrics: dict) -> bool:

    # 1. No forbidden language
    lowered = text.lower()

    for word in FORBIDDEN_WORDS:
        if word in lowered:
            return False


    # 2. Validate numbers
    if not validate_numbers(text, metrics):
        return False


    return True

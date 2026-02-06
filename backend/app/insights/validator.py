import re

FORBIDDEN_WORDS = [
    "invest",
    "should",
    "recommend",
    "advice",
    "guarantee",
    "profit"
]

def validate_explanation(text: str, metrics: dict) -> bool:

    # 1. No forbidden language
    lowered = text.lower()

    for word in FORBIDDEN_WORDS:
        if word in lowered:
            return False


    # 2. Check numbers match metrics
    numbers = re.findall(r"\d+\.?\d*", text)

    valid_numbers = []

    # collect all known numbers
    for v in metrics["rolling"].values():
        valid_numbers.append(str(v))

    for v in metrics["monthly"].values():
        if v is not None:
            valid_numbers.append(str(v))

    for cat in metrics["categories"]:
        valid_numbers.append(str(cat["total"]))


    for n in numbers:
        if n not in valid_numbers:
            return False

    return True

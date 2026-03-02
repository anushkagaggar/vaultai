"""
VaultAI V3 — agents/filters/numeric_guard.py
=============================================
Extract numbers from LLM output and compare against deterministic outputs.

PROBLEM THIS SOLVES
--------------------
LLMs hallucinate numbers. Given a budget with monthly_savings=25000,
the LLM might write "you can save approximately Rs.27,500 per month"
because 27,500 sounds plausible. That number was never in the plan.

The numeric guard:
  1. Extracts every number from the LLM text
  2. Builds an allowed-value set from projected_outcomes + assumptions
  3. Flags any LLM number not matching an allowed value ±tolerance
  4. Redacts unmatched numbers in-place

WHY REDACT RATHER THAN REJECT
--------------------------------
Rejecting the entire explanation on one bad number is too aggressive.
Redaction surgically removes the fabricated value while preserving
the sentence structure. The *_fallback path exists for cases where
the whole explanation is untrustworthy.

TOLERANCE STRATEGY
-------------------
tolerance = max(1.0, abs(value) * 0.02)

Small numbers (< 50):  ±1.0 absolute
Large numbers (> 50):  ±2% relative

2% catches reasonable LLM rounding ("Rs.24,998" → "Rs.25,000")
while still catching fabricated numbers (27,500 vs 25,000 is 10% off).

WHAT COUNTS AS A NUMBER
------------------------
Extracts: integers, decimals, comma-formatted, percentages.
Skips:    calendar years (1900–2099), ordinals (1st, 2nd, 3rd).

Author: VaultAI V3
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RELATIVE_TOLERANCE: float = 0.02   # 2% relative
ABSOLUTE_FLOOR:     float = 1.0    # minimum absolute tolerance

_REDACT_PLACEHOLDER = "[N]"

# Matches: 1000, 1,000, 1,00,000, 10.5, 10.5%, 0.07
_NUMBER_RE = re.compile(
    r"""
    (?<!\w)
    (?:
        \d{1,3}(?:,\d{2,3})+   # comma-formatted: 1,000 or 1,00,000
        | \d+(?:\.\d+)?         # plain integer or decimal
    )
    (?:%)?                      # optional trailing percent
    (?!\w)
    """,
    re.VERBOSE,
)

_YEAR_RE    = re.compile(r"\b(?:19|20)\d{2}\b")
_ORDINAL_RE = re.compile(r"\b\d+(?:st|nd|rd|th)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class NumericGuardResult:
    text_clean:       str
    numbers_found:    list[float] = field(default_factory=list)
    numbers_matched:  list[float] = field(default_factory=list)
    numbers_redacted: list[float] = field(default_factory=list)
    allowed_values:   list[float] = field(default_factory=list)
    any_redacted:     bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_number(s: str) -> float | None:
    try:
        return float(s.replace(",", "").rstrip("%"))
    except (ValueError, AttributeError):
        return None


def _is_year(s: str) -> bool:
    return bool(_YEAR_RE.fullmatch(s.strip()))


def _is_ordinal(s: str) -> bool:
    return bool(_ORDINAL_RE.fullmatch(s.strip()))


def _tolerance_for(value: float) -> float:
    return max(ABSOLUTE_FLOOR, abs(value) * RELATIVE_TOLERANCE)


def _matches_any(value: float, allowed: list[float]) -> bool:
    tol = _tolerance_for(value)
    return any(abs(value - a) <= tol for a in allowed)


def _extract_allowed_values(projected_outcomes: dict, assumptions: dict) -> list[float]:
    """Recursively collect all numeric leaf values from both dicts."""
    values: list[float] = []

    def _walk(obj: object) -> None:
        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            values.append(float(obj))
        elif isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _walk(item)

    _walk(projected_outcomes)
    _walk(assumptions)

    # Deduplicate preserving order
    seen: set[float] = set()
    unique: list[float] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def run_numeric_guard(
    llm_text:           str,
    projected_outcomes: dict,
    assumptions:        dict,
) -> NumericGuardResult:
    """
    Extract numbers from LLM text, compare to deterministic plan data,
    and redact any number that cannot be traced back to the plan.

    Pure function — no I/O, no side effects. Safe to call from sync nodes.
    """
    if not llm_text or not llm_text.strip():
        return NumericGuardResult(text_clean=llm_text or "")

    allowed = _extract_allowed_values(projected_outcomes or {}, assumptions or {})

    found:    list[float] = []
    matched:  list[float] = []
    redacted: list[float] = []

    def _replace_match(m: re.Match) -> str:
        raw = m.group(0)
        if _is_year(raw) or _is_ordinal(raw):
            return raw
        value = _parse_number(raw)
        if value is None:
            return raw

        found.append(value)

        if _matches_any(value, allowed):
            matched.append(value)
            return raw
        else:
            redacted.append(value)
            closest = min(allowed, key=lambda a: abs(a - value), default=None)
            logger.debug(
                "numeric_guard: redacted %.2f (closest allowed: %s)",
                value, f"{closest:.2f}" if closest is not None else "none",
            )
            return _REDACT_PLACEHOLDER

    text_clean = _NUMBER_RE.sub(_replace_match, llm_text)
    text_clean = re.sub(r"  +", " ", text_clean).strip()
    any_redacted = len(redacted) > 0

    if any_redacted:
        logger.info(
            "numeric_guard: redacted %d/%d numbers: %s",
            len(redacted), len(found), [f"{v:.2f}" for v in redacted],
        )
    else:
        logger.info("numeric_guard: all %d numbers matched — no redactions", len(found))

    return NumericGuardResult(
        text_clean       = text_clean,
        numbers_found    = found,
        numbers_matched  = matched,
        numbers_redacted = redacted,
        allowed_values   = allowed,
        any_redacted     = any_redacted,
    )
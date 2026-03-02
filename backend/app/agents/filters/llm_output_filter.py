"""
VaultAI V3 — agents/filters/llm_output_filter.py
==================================================
Full LLM output filter pipeline. Called by every *_filter node.

PIPELINE ORDER
--------------
1. SPECULATIVE LANGUAGE   — hedging words ("might", "could", "around")
2. DIRECTIVE LANGUAGE     — advice phrases ("you should", "I recommend")
3. NUMERIC GUARD          — redacts numbers not in projected_outcomes/assumptions
4. CLEANUP                — collapses double-spaces, fixes punctuation artefacts

WHY A SINGLE MODULE
--------------------
All three agents (budget, invest, goal) previously duplicated the same
regex patterns inline in each nodes.py. This is the single source of truth.

Each *_filter node becomes a thin wrapper:

    def budget_filter(state):
        trace = append_trace(state, "budget_filter")
        raw   = state.get("llm_explanation")
        if raw is None:
            filtered = _build_deterministic_summary(...)
        else:
            result   = filter_llm_output(raw, outcomes, assumptions)
            filtered = result.text_clean
        return {**state, "graph_trace": trace, "explanation_filtered": filtered}

PHASE 3 EXIT CRITERION
-----------------------
The filter catches predicted-return language from invest_explain:
  "will return X%", "expected return of X%", "projected return"
These are in the speculative pattern list.

Author: VaultAI V3
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.agents.filters.numeric_guard import run_numeric_guard, NumericGuardResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------

# Pass 1 — Speculative / hedging language
# Longer phrases first to avoid partial matches swallowing shorter ones.
_SPECULATIVE_PATTERNS: list[tuple[str, str]] = [
    (r"\bsomewhere between\b",   ""),
    (r"\bexpected to\b",         ""),
    (r"\blikely to\b",           ""),
    (r"\btends to\b",            ""),
    (r"\bup to\b",               ""),
    (r"\bwill return\b",         ""),     # invest: "will return X%"
    (r"\bprojected return\b",    ""),     # invest: "projected return of X%"
    (r"\bexpected return\b",     ""),     # invest: "expected return"
    (r"\byou should consider\b", ""),
    (r"\bapproximately\b",       ""),
    (r"\broughly\b",             ""),
    (r"\bperhaps\b",             ""),
    (r"\bpossibly\b",            ""),
    (r"\bprobably\b",            ""),
    (r"\baround\b",              ""),
    (r"\babout\b",               ""),
    (r"\bmight\b",               ""),
    (r"\bmay\b",                 ""),
    (r"\bcould\b",               ""),
    (r"\bguaranteed\b",          ""),
]

# Pass 2 — Directive / advice language
_DIRECTIVE_PATTERNS: list[tuple[str, str]] = [
    (r"\bit would be wise(?:\s+to)?\b",    ""),
    (r"\bit is advisable(?:\s+to)?\b",     ""),
    (r"\bI\s+(?:strongly\s+)?recommend\b", ""),
    (r"\bI\s+suggest\b",                   ""),
    (r"\bmake sure(?:\s+to)?\b",           ""),
    (r"\bensure\s+that\b",                 ""),
    (r"\byou\s+(?:really\s+)?should\b",    ""),
    (r"\byou\s+must\b",                    ""),
    (r"\byou\s+need\s+to\b",               ""),
    (r"\bconsider\b",                      ""),
]

# Compiled once at import time
_COMPILED_SPECULATIVE = [
    (re.compile(pat, re.IGNORECASE), repl)
    for pat, repl in _SPECULATIVE_PATTERNS
]
_COMPILED_DIRECTIVE = [
    (re.compile(pat, re.IGNORECASE), repl)
    for pat, repl in _DIRECTIVE_PATTERNS
]


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class FilterResult:
    """
    Full output of filter_llm_output().

    text_clean:          Final filtered text — safe to store and show to user.
    speculative_removed: Speculative phrases that were removed.
    directive_removed:   Directive phrases that were removed.
    numeric_result:      Full NumericGuardResult from pass 3.
    passes_applied:      Ordered list of passes that ran (for audit).
    """
    text_clean:          str
    speculative_removed: list[str]             = field(default_factory=list)
    directive_removed:   list[str]             = field(default_factory=list)
    numeric_result:      NumericGuardResult | None = None
    passes_applied:      list[str]             = field(default_factory=list)


# ---------------------------------------------------------------------------
# Individual passes
# ---------------------------------------------------------------------------

def _apply_speculative_pass(text: str) -> tuple[str, list[str]]:
    removed: list[str] = []
    for pattern, replacement in _COMPILED_SPECULATIVE:
        hits = pattern.findall(text)
        if hits:
            removed.extend(hits)
        text = pattern.sub(replacement, text)
    return text, removed


def _apply_directive_pass(text: str) -> tuple[str, list[str]]:
    removed: list[str] = []
    for pattern, replacement in _COMPILED_DIRECTIVE:
        hits = pattern.findall(text)
        if hits:
            removed.extend(hits)
        text = pattern.sub(replacement, text)
    return text, removed


def _apply_cleanup_pass(text: str) -> str:
    text = re.sub(r"  +",      " ",  text)   # collapse double spaces
    text = re.sub(r"\s*\.\s*\.", ".", text)   # fix ". ." artefacts
    text = re.sub(r",\s*,",    ",",  text)   # fix ",," artefacts
    text = re.sub(r"\s+\.",    ".",  text)   # fix " ." artefacts
    text = re.sub(r"\s+,",     ",",  text)   # fix " ," artefacts
    text = re.sub(r"\(\s*\)",  "",   text)   # remove empty parens
    text = re.sub(r"\[\s*\]",  "",   text)   # remove empty brackets
    text = re.sub(r"\s{2,}",   " ",  text)   # final double-space pass
    return text.strip()


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def filter_llm_output(
    llm_text:           str,
    projected_outcomes: dict,
    assumptions:        dict,
) -> FilterResult:
    """
    Run the full 4-pass filter pipeline on raw LLM output.

    Pass 1: Remove speculative/hedging language
    Pass 2: Remove directive/advice language
    Pass 3: Numeric guard — redact unrecognised numbers
    Pass 4: Cleanup — fix spacing and punctuation artefacts

    Args:
        llm_text:           Raw string from the LLM explain node.
        projected_outcomes: state["projected_outcomes"] for numeric matching.
        assumptions:        state["assumptions"] for numeric matching.

    Returns:
        FilterResult. text_clean is safe to store in DB and show to user.

    Pure function — no I/O, no side effects. Safe from sync nodes.
    """
    if not llm_text or not llm_text.strip():
        logger.warning("filter_llm_output: received empty text")
        return FilterResult(text_clean=llm_text or "")

    original_len  = len(llm_text)
    passes_applied: list[str] = []

    # Pass 1
    text, speculative_removed = _apply_speculative_pass(llm_text)
    passes_applied.append("speculative")

    # Pass 2
    text, directive_removed = _apply_directive_pass(text)
    passes_applied.append("directive")

    # Pass 3
    numeric_result = run_numeric_guard(text, projected_outcomes or {}, assumptions or {})
    text           = numeric_result.text_clean
    passes_applied.append("numeric_guard")

    # Pass 4
    text = _apply_cleanup_pass(text)
    passes_applied.append("cleanup")

    logger.info(
        "filter_llm_output: %d→%d chars | speculative=%d directive=%d redacted=%d",
        original_len, len(text),
        len(speculative_removed),
        len(directive_removed),
        len(numeric_result.numbers_redacted),
    )

    return FilterResult(
        text_clean          = text,
        speculative_removed = speculative_removed,
        directive_removed   = directive_removed,
        numeric_result      = numeric_result,
        passes_applied      = passes_applied,
    )
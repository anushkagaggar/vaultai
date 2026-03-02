"""
VaultAI V3 — integrations/market_api.py
=========================================
External market data adapter for the InvestAgent.

DESIGN PRINCIPLES
-----------------
1. TYPED FALLBACKS FIRST — every API call has a Pydantic fallback model.
   The invest subgraph runs end-to-end even when every external API is down.

2. GUARDRAIL ENFORCED HERE — raw price data and historical return series
   are NEVER in the public return type. fetch_market_context() returns:
     - risk_free_rate_pct  (from FRED / RBI proxy)
     - inflation_pct       (CPI)
     - freshness           ("live" | "cached" | "fallback")
   invest_explain receives only allocation percentages — never this object.

3. CACHE BEFORE NETWORK — module-level TTL cache.
   Macro rates: 7-day TTL. Avoids hammering free-tier APIs.

4. ALL I/O ASYNC — invest_fetch_data is async; everything here is awaitable.

PUBLIC API
----------
    from app.integrations.market_api import fetch_market_context
    context: MarketContext = await fetch_market_context()
    # Always returns. Falls back gracefully. Never raises.
"""

from __future__ import annotations

import logging
import os
import time

import httpx
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fallback constants — conservative Indian market estimates
# Sources: SEBI reports, RBI annual reports, long-run Nifty 50 data.
# ---------------------------------------------------------------------------
FALLBACK_RISK_FREE_RATE_PCT: float = 6.5   # RBI repo rate proxy (2024)
FALLBACK_INFLATION_PCT:      float = 5.5   # CPI India 5yr avg

_FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
_API_TIMEOUT_S = 8
_TTL_MACRO_S   = 7 * 24 * 3600   # 7 days

# Module-level cache: key -> (value, fetched_at_epoch)
_CACHE: dict[str, tuple[object, float]] = {}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MacroRates(BaseModel):
    """Internal model for FRED rates. Not exposed outside this module."""
    risk_free_rate_pct: float = Field(..., ge=0, le=30)
    inflation_pct:      float = Field(..., ge=0, le=30)
    source:             str

    @field_validator("risk_free_rate_pct", "inflation_pct")
    @classmethod
    def cap_rate(cls, v: float) -> float:
        return round(min(max(v, 0.0), 30.0), 4)


class MarketContext(BaseModel):
    """
    The ONLY type returned from fetch_market_context().

    invest_allocate reads risk_free_rate_pct and inflation_pct to inform
    allocation math. invest_explain receives NOTHING from this model —
    it gets only the allocation percentages written by invest_allocate.
    No price data. No historical returns. No OHLCV.
    """
    risk_free_rate_pct: float = Field(..., ge=0, le=30)
    inflation_pct:      float = Field(..., ge=0, le=30)
    freshness:          str   = Field(...)   # "live" | "cached" | "fallback"
    source_detail:      str   = Field(...)
    fetched_at:         float = Field(default_factory=time.time)

    @property
    def real_rate_pct(self) -> float:
        """Real rate via Fisher equation: (1+r)/(1+i) - 1."""
        return round(
            ((1 + self.risk_free_rate_pct / 100) /
             (1 + self.inflation_pct / 100) - 1) * 100, 2
        )

    def to_audit_dict(self) -> dict:
        """Safe dict for audit_payload. Contains no price data."""
        return {
            "risk_free_rate_pct": self.risk_free_rate_pct,
            "inflation_pct":      self.inflation_pct,
            "real_rate_pct":      self.real_rate_pct,
            "freshness":          self.freshness,
            "source_detail":      self.source_detail,
            "fetched_at":         self.fetched_at,
        }


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_get(key: str, ttl_s: float) -> object | None:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    value, fetched_at = entry
    if time.time() - fetched_at < ttl_s:
        return value
    del _CACHE[key]
    return None


def _cache_set(key: str, value: object) -> None:
    _CACHE[key] = (value, time.time())


def clear_cache() -> None:
    """Clear module-level cache. Call in tests between runs."""
    _CACHE.clear()


# ---------------------------------------------------------------------------
# FRED adapter
# ---------------------------------------------------------------------------

async def _fetch_fred_macro() -> MacroRates | None:
    """
    Fetch risk-free rate (DGS10) and breakeven inflation (T10YIE) from FRED.
    Returns None on any failure — caller uses hardcoded fallback.

    For Indian production deployment, replace series IDs:
        DGS10  → INDIRLTLT01STM   (India long-term rate)
        T10YIE → INDCPIALLMINMEI  (India CPI)
    The adapter shape stays identical — only series IDs change.
    """
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        logger.debug("market_api: FRED_API_KEY not set — skipping FRED fetch")
        return None

    cached = _cache_get("fred_macro", _TTL_MACRO_S)
    if cached is not None:
        c = cached  # type: ignore[assignment]
        logger.debug("market_api: FRED macro from cache")
        return MacroRates(
            risk_free_rate_pct=c.risk_free_rate_pct,
            inflation_pct=c.inflation_pct,
            source="fred_cached",
        )

    try:
        async with httpx.AsyncClient(timeout=_API_TIMEOUT_S) as client:
            # Fetch risk-free rate
            rfr_resp = await client.get(
                _FRED_BASE_URL,
                params={
                    "series_id":  "DGS10",
                    "api_key":    api_key,
                    "file_type":  "json",
                    "sort_order": "desc",
                    "limit":      1,
                },
            )
            rfr_resp.raise_for_status()
            rfr_obs = rfr_resp.json()["observations"][0]["value"]
            if rfr_obs in (".", ""):
                raise ValueError("FRED: missing value for DGS10")

            # Fetch inflation
            inf_resp = await client.get(
                _FRED_BASE_URL,
                params={
                    "series_id":  "T10YIE",
                    "api_key":    api_key,
                    "file_type":  "json",
                    "sort_order": "desc",
                    "limit":      1,
                },
            )
            inf_resp.raise_for_status()
            inf_obs = inf_resp.json()["observations"][0]["value"]
            if inf_obs in (".", ""):
                raise ValueError("FRED: missing value for T10YIE")

        rates = MacroRates(
            risk_free_rate_pct=float(rfr_obs),
            inflation_pct=float(inf_obs),
            source="fred_live",
        )
        _cache_set("fred_macro", rates)
        logger.info(
            "market_api: FRED live — rfr=%.2f%% inflation=%.2f%%",
            rates.risk_free_rate_pct, rates.inflation_pct,
        )
        return rates

    except httpx.TimeoutException:
        logger.warning("market_api: FRED timed out after %ds", _API_TIMEOUT_S)
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "market_api: FRED HTTP %d — %s",
            exc.response.status_code, exc.response.text[:200],
        )
    except Exception as exc:
        logger.warning(
            "market_api: FRED error — %s: %s", type(exc).__name__, exc
        )

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_market_context() -> MarketContext:
    """
    Fetch macro-economic context for invest allocation.

    Resolution order:
      1. Module-level cache (7-day TTL for macro rates)
      2. FRED API (requires FRED_API_KEY env var)
      3. Hardcoded conservative fallback (always succeeds)

    Returns MarketContext — always returns, never raises.
    .freshness == "live" | "cached" | "fallback"

    GUARDRAIL: returns risk-free rate + inflation ONLY.
    No equity prices. No return histories. No OHLCV.
    invest_explain never receives this object.
    """
    macro = await _fetch_fred_macro()

    if macro is not None:
        freshness = "live" if macro.source == "fred_live" else "cached"
        return MarketContext(
            risk_free_rate_pct=macro.risk_free_rate_pct,
            inflation_pct=macro.inflation_pct,
            freshness=freshness,
            source_detail=macro.source,
        )

    logger.warning("market_api: all sources failed — using hardcoded fallback")
    return MarketContext(
        risk_free_rate_pct=FALLBACK_RISK_FREE_RATE_PCT,
        inflation_pct=FALLBACK_INFLATION_PCT,
        freshness="fallback",
        source_detail="hardcoded_conservative_estimates",
    )
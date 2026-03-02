"""
VaultAI V3 — tests/test_invest_agent.py
=========================================
Phase 3 exit criterion tests.

All tests use mocked API responses — no real network calls.
Run with: pytest tests/test_invest_agent.py -v

Exit criteria verified:
  [x] All API calls wrapped with typed fallbacks
  [x] invest_validate: percentages sum to exactly 100%
  [x] LLM filter catches predicted-return language
  [x] external_freshness = "live" | "cached" | "fallback" in output
  [x] Custom profile validates sum == 100%
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ---------------------------------------------------------------------------
# market_api tests
# ---------------------------------------------------------------------------

class TestMarketApiWithFallback:
    """API calls wrapped in try/except with typed fallback models."""

    @pytest.mark.asyncio
    async def test_returns_fallback_when_no_api_key(self):
        """No FRED_API_KEY → fallback with correct shape."""
        from app.integrations.market_api import fetch_market_context, clear_cache
        clear_cache()

        with patch.dict("os.environ", {}, clear=True):
            ctx = await fetch_market_context()

        assert ctx.freshness == "fallback"
        assert ctx.risk_free_rate_pct > 0
        assert ctx.inflation_pct > 0
        assert ctx.source_detail != ""

    @pytest.mark.asyncio
    async def test_returns_live_when_fred_succeeds(self):
        """FRED success → freshness == live."""
        from app.integrations.market_api import fetch_market_context, clear_cache
        import httpx
        clear_cache()

        mock_rfr_resp = MagicMock()
        mock_rfr_resp.status_code = 200
        mock_rfr_resp.json.return_value = {
            "observations": [{"value": "4.25", "date": "2024-06-01"}]
        }
        mock_rfr_resp.raise_for_status = MagicMock()

        mock_inf_resp = MagicMock()
        mock_inf_resp.status_code = 200
        mock_inf_resp.json.return_value = {
            "observations": [{"value": "2.30", "date": "2024-06-01"}]
        }
        mock_inf_resp.raise_for_status = MagicMock()

        with patch.dict("os.environ", {"FRED_API_KEY": "test_key"}):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(
                    side_effect=[mock_rfr_resp, mock_inf_resp]
                )
                mock_client_cls.return_value = mock_client

                ctx = await fetch_market_context()

        assert ctx.freshness == "live"
        assert abs(ctx.risk_free_rate_pct - 4.25) < 0.01
        assert abs(ctx.inflation_pct - 2.30) < 0.01

    @pytest.mark.asyncio
    async def test_returns_fallback_on_timeout(self):
        """Network timeout → typed fallback, never raises."""
        from app.integrations.market_api import fetch_market_context, clear_cache
        import httpx
        clear_cache()

        with patch.dict("os.environ", {"FRED_API_KEY": "test_key"}):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(
                    side_effect=httpx.TimeoutException("timeout")
                )
                mock_client_cls.return_value = mock_client

                ctx = await fetch_market_context()

        assert ctx.freshness == "fallback"
        assert ctx.risk_free_rate_pct > 0   # conservative hardcoded value

    @pytest.mark.asyncio
    async def test_returns_fallback_on_http_error(self):
        """HTTP 500 from FRED → typed fallback."""
        from app.integrations.market_api import fetch_market_context, clear_cache
        import httpx
        clear_cache()

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch.dict("os.environ", {"FRED_API_KEY": "test_key"}):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(
                    side_effect=httpx.HTTPStatusError(
                        "500", request=MagicMock(), response=mock_resp
                    )
                )
                mock_client_cls.return_value = mock_client

                ctx = await fetch_market_context()

        assert ctx.freshness == "fallback"

    def test_market_context_has_no_price_data(self):
        """MarketContext model fields — guardrail: no price data fields."""
        from app.integrations.market_api import MarketContext
        import time
        ctx = MarketContext(
            risk_free_rate_pct=6.5,
            inflation_pct=5.5,
            freshness="fallback",
            source_detail="test",
            fetched_at=time.time(),
        )
        audit = ctx.to_audit_dict()

        # Must have these fields
        assert "risk_free_rate_pct" in audit
        assert "inflation_pct" in audit
        assert "freshness" in audit

        # Must NOT have any price/return fields
        forbidden = {
            "equity_price", "equity_return", "nifty", "sensex",
            "ohlcv", "historical_returns", "alpha_vantage",
            "debt_return", "liquid_return",
        }
        for field in forbidden:
            assert field not in audit, f"Guardrail violated: '{field}' in MarketContext.to_audit_dict()"


# ---------------------------------------------------------------------------
# invest_validate: Phase 3 exit criterion — exact 100% sum
# ---------------------------------------------------------------------------

class TestInvestValidate:

    def _make_state(self, equity, debt, liquid, amount=100000.0):
        """Build minimal state for invest_validate."""
        total_alloc = round(amount * equity / 100, 2) + \
                      round(amount * debt   / 100, 2) + \
                      round(amount - round(amount * equity / 100, 2)
                            - round(amount * debt / 100, 2), 2)
        return {
            "graph_trace": [],
            "degraded": False,
            "audit_payload": None,
            "projected_outcomes": {
                "equity_pct":      equity,
                "debt_pct":        debt,
                "liquid_pct":      liquid,
                "total_allocated": amount,
                "risk_profile":    "moderate",
                "allocation_method": "deterministic_template",
                "equity_amount":   round(amount * equity / 100, 2),
                "debt_amount":     round(amount * debt   / 100, 2),
                "liquid_amount":   round(amount * liquid / 100, 2),
            },
            "constraints": {
                "investment_amount": amount,
                "risk_profile": "moderate",
                "equity_pct": equity,
                "debt_pct":   debt,
                "liquid_pct": liquid,
                "template": {
                    "equity_pct": equity,
                    "debt_pct":   debt,
                    "liquid_pct": liquid,
                },
            },
        }

    def test_passed_for_exact_100_pct(self):
        """50 + 35 + 15 == 100.0 → PASSED."""
        from app.agents.invest.nodes import invest_validate
        from app.agents.State import ValidationStatus

        state  = self._make_state(50.0, 35.0, 15.0)
        result = invest_validate(state)
        assert result["validation_status"] == ValidationStatus.PASSED
        assert result["validation_errors"] == []

    def test_passed_for_conservative(self):
        """20 + 60 + 20 == 100.0 → PASSED."""
        from app.agents.invest.nodes import invest_validate
        from app.agents.State import ValidationStatus

        state  = self._make_state(20.0, 60.0, 20.0)
        result = invest_validate(state)
        assert result["validation_status"] == ValidationStatus.PASSED

    def test_passed_for_aggressive(self):
        """75 + 15 + 10 == 100.0 → PASSED."""
        from app.agents.invest.nodes import invest_validate
        from app.agents.State import ValidationStatus

        state  = self._make_state(75.0, 15.0, 10.0)
        result = invest_validate(state)
        assert result["validation_status"] == ValidationStatus.PASSED

    def test_failed_for_sum_under_100(self):
        """50 + 35 + 14 == 99.0 → FAILED (Phase 3 exit criterion)."""
        from app.agents.invest.nodes import invest_validate
        from app.agents.State import ValidationStatus

        state = self._make_state(50.0, 35.0, 14.0)
        # Fix the constraint to match the bad values
        state["constraints"]["liquid_pct"] = 14.0
        state["constraints"]["template"]["liquid_pct"] = 14.0

        result = invest_validate(state)
        assert result["validation_status"] == ValidationStatus.FAILED
        assert any("100" in e for e in result["validation_errors"])

    def test_failed_for_sum_over_100(self):
        """50 + 35 + 16 == 101.0 → FAILED."""
        from app.agents.invest.nodes import invest_validate
        from app.agents.State import ValidationStatus

        state = self._make_state(50.0, 35.0, 16.0)
        state["constraints"]["liquid_pct"] = 16.0
        state["constraints"]["template"]["liquid_pct"] = 16.0

        result = invest_validate(state)
        assert result["validation_status"] == ValidationStatus.FAILED

    def test_failed_when_outcomes_missing(self):
        """projected_outcomes is None → FAILED with clear message."""
        from app.agents.invest.nodes import invest_validate
        from app.agents.State import ValidationStatus

        state = {
            "graph_trace": [], "degraded": False, "audit_payload": None,
            "projected_outcomes": None,
            "constraints": {"investment_amount": 100000},
        }
        result = invest_validate(state)
        assert result["validation_status"] == ValidationStatus.FAILED
        assert "invest_allocate" in result["validation_errors"][0]


# ---------------------------------------------------------------------------
# invest_checkpoint: unit tests for the pure checkpoint function
# ---------------------------------------------------------------------------

class TestInvestCheckpoint:

    def test_passes_valid_allocation(self):
        from app.agents.invest.checkpoint import run_invest_checkpoint

        outcomes = {
            "equity_pct": 50.0, "debt_pct": 35.0, "liquid_pct": 15.0,
            "total_allocated": 100000.0,
        }
        constraints = {
            "investment_amount": 100000.0,
            "equity_pct": 50.0, "debt_pct": 35.0, "liquid_pct": 15.0,
        }
        result = run_invest_checkpoint(outcomes, constraints)
        assert result.passed is True
        assert result.errors == []
        assert abs(result.pct_sum - 100.0) < 0.01

    def test_fails_partial_sum(self):
        from app.agents.invest.checkpoint import run_invest_checkpoint

        outcomes = {
            "equity_pct": 50.0, "debt_pct": 35.0, "liquid_pct": 10.0,
            "total_allocated": 95000.0,
        }
        constraints = {
            "investment_amount": 100000.0,
            "equity_pct": 50.0, "debt_pct": 35.0, "liquid_pct": 10.0,
        }
        result = run_invest_checkpoint(outcomes, constraints)
        assert result.passed is False
        assert any("PHASE3_EXIT_CRITERION" in e for e in result.errors)

    def test_fails_none_outcomes(self):
        from app.agents.invest.checkpoint import run_invest_checkpoint
        result = run_invest_checkpoint(None, {"investment_amount": 100000})
        assert result.passed is False


# ---------------------------------------------------------------------------
# LLM filter: catches predicted-return language (Phase 3 exit criterion)
# ---------------------------------------------------------------------------

class TestLlmFilterCatchesPredictedReturns:

    OUTCOMES = {
        "equity_pct": 50.0, "debt_pct": 35.0, "liquid_pct": 15.0,
        "equity_amount": 50000.0, "debt_amount": 35000.0, "liquid_amount": 15000.0,
        "total_allocated": 100000.0,
    }
    ASSUMPTIONS = {
        "investment_amount": 100000.0, "risk_profile": "moderate",
        "horizon_months": 36, "risk_free_rate_pct": 6.5,
    }

    def test_removes_speculative_language(self):
        from app.agents.filters.llm_output_filter import filter_llm_output

        raw = "Your portfolio might earn around 12% per year over time."
        result = filter_llm_output(raw, self.OUTCOMES, self.ASSUMPTIONS)

        assert "might" not in result.text_clean.lower()
        assert "around" not in result.text_clean.lower()
        assert len(result.speculative_removed) >= 2

    def test_removes_directive_language(self):
        from app.agents.filters.llm_output_filter import filter_llm_output

        raw = "You should consider rebalancing annually. I recommend a SIP."
        result = filter_llm_output(raw, self.OUTCOMES, self.ASSUMPTIONS)

        assert "you should" not in result.text_clean.lower()
        assert "i recommend" not in result.text_clean.lower()

    def test_redacts_hallucinated_number(self):
        from app.agents.filters.llm_output_filter import filter_llm_output

        # 87000 is not in OUTCOMES or ASSUMPTIONS — should be redacted
        raw = "Your equity allocation of Rs.87,000 will grow significantly."
        result = filter_llm_output(raw, self.OUTCOMES, self.ASSUMPTIONS)

        assert result.numeric_result is not None
        assert result.numeric_result.any_redacted is True
        assert 87000.0 in result.numeric_result.numbers_redacted

    def test_keeps_correct_number(self):
        from app.agents.filters.llm_output_filter import filter_llm_output

        # 50000.0 IS in outcomes (equity_amount)
        raw = "Your equity allocation is Rs.50,000."
        result = filter_llm_output(raw, self.OUTCOMES, self.ASSUMPTIONS)

        assert "50,000" in result.text_clean or "50000" in result.text_clean
        assert result.numeric_result is not None
        assert not result.numeric_result.any_redacted

    def test_invest_filter_node_uses_filter_pipeline(self):
        """invest_filter node delegates to filter_llm_output when available."""
        from app.agents.invest.nodes import invest_filter

        state = {
            "graph_trace": [],
            "degraded": False,
            "audit_payload": None,
            "llm_explanation": (
                "Your investment might grow around 15% annually. "
                "You should consider rebalancing every year."
            ),
            "projected_outcomes": self.OUTCOMES,
            "assumptions": self.ASSUMPTIONS,
        }

        result = invest_filter(state)
        filtered = result["explanation_filtered"]

        assert "might" not in filtered.lower()
        assert "around" not in filtered.lower()


# ---------------------------------------------------------------------------
# external_freshness in output — Phase 3 exit criterion
# ---------------------------------------------------------------------------

class TestExternalFreshnessLabel:

    @pytest.mark.asyncio
    async def test_freshness_fallback_sets_degraded(self):
        """
        When market API is unavailable, external_freshness == FALLBACK
        and degraded == True.
        """
        from app.agents.invest.nodes import invest_fetch_data
        from app.agents.State import ExternalFreshness

        v2_analytics = {
            "rolling": {"90_day_avg": 30000},
            "monthly": {},
            "trend_type": "drop",
            "categories": [],
        }

        state = {
            "user_id": "1",
            "graph_trace": [],
            "degraded": False,
            "audit_payload": None,
            "request_params": {"_v2_analytics": v2_analytics},
        }

        with patch(
            "app.agents.invest.nodes.fetch_market_context",
            new_callable=AsyncMock,
        ) as mock_fetch:
            from app.integrations.market_api import MarketContext
            import time
            mock_fetch.return_value = MarketContext(
                risk_free_rate_pct=6.5,
                inflation_pct=5.5,
                freshness="fallback",
                source_detail="test_fallback",
                fetched_at=time.time(),
            )
            result = await invest_fetch_data(state)

        assert result["external_freshness"] == ExternalFreshness.FALLBACK
        assert result["degraded"] is True
        assert result["external_data"]["freshness"] == "fallback"

    @pytest.mark.asyncio
    async def test_freshness_live_does_not_set_degraded(self):
        """When market API returns live data, degraded stays False."""
        from app.agents.invest.nodes import invest_fetch_data
        from app.agents.State import ExternalFreshness

        v2_analytics = {
            "rolling": {"90_day_avg": 30000},
            "monthly": {},
            "trend_type": "stable",
            "categories": [],
        }

        state = {
            "user_id": "1",
            "graph_trace": [],
            "degraded": False,
            "audit_payload": None,
            "request_params": {"_v2_analytics": v2_analytics},
        }

        with patch(
            "app.agents.invest.nodes.fetch_market_context",
            new_callable=AsyncMock,
        ) as mock_fetch:
            from app.integrations.market_api import MarketContext
            import time
            mock_fetch.return_value = MarketContext(
                risk_free_rate_pct=4.25,
                inflation_pct=2.30,
                freshness="live",
                source_detail="fred_live",
                fetched_at=time.time(),
            )
            result = await invest_fetch_data(state)

        assert result["external_freshness"] == ExternalFreshness.LIVE
        assert result["degraded"] is False
        assert result["external_data"]["freshness"] == "live"


# ---------------------------------------------------------------------------
# Custom risk profile
# ---------------------------------------------------------------------------

class TestCustomRiskProfile:

    def test_custom_profile_valid_allocation(self):
        """Custom with exact 100% → allocates correctly."""
        from app.agents.invest.nodes import invest_allocate

        v2 = {"rolling": {}, "monthly": {}, "trend_type": "stable", "categories": []}
        state = {
            "graph_trace": [],
            "degraded": False,
            "audit_payload": None,
            "v2_analytics": v2,
            "external_data": {"risk_free_rate_pct": 6.5, "inflation_pct": 5.5},
            "request_params": {
                "investment_amount":  100000,
                "risk_profile":       "custom",
                "custom_equity_pct":  40.0,
                "custom_debt_pct":    40.0,
                "custom_liquid_pct":  20.0,
                "horizon_months":     24,
            },
        }

        result = invest_allocate(state)
        outcomes = result["projected_outcomes"]

        assert outcomes["equity_pct"] == 40.0
        assert outcomes["debt_pct"]   == 40.0
        assert outcomes["liquid_pct"] == 20.0
        assert abs(outcomes["equity_amount"] + outcomes["debt_amount"]
                   + outcomes["liquid_amount"] - 100000) < 1.0

    def test_custom_profile_rejects_bad_sum(self):
        """Custom where percentages don't sum to 100% → ValueError."""
        from app.agents.invest.nodes import invest_allocate

        v2 = {"rolling": {}, "monthly": {}, "trend_type": "stable", "categories": []}
        state = {
            "graph_trace": [],
            "degraded": False,
            "audit_payload": None,
            "v2_analytics": v2,
            "external_data": {"risk_free_rate_pct": 6.5, "inflation_pct": 5.5},
            "request_params": {
                "investment_amount": 100000,
                "risk_profile":      "custom",
                "custom_equity_pct": 40.0,
                "custom_debt_pct":   40.0,
                "custom_liquid_pct": 15.0,   # 40+40+15 = 95 ≠ 100
                "horizon_months":    24,
            },
        }

        with pytest.raises(ValueError, match="sum to 100"):
            invest_allocate(state)

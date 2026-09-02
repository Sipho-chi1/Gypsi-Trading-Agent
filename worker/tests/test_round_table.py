"""
Unit and Integration Tests for The Round Table.

Covers all 8 requirements in the consolidated spec:
1. Isolation test: asserts analyse_independently signature cannot accept proposal/signal.
2. Market context test: empty catalysts -> no event risk; near-term catalyst -> event_risk flag.
3. Portfolio concentration test: 3+ same-direction positions -> portfolio_concentration flag.
4. Golden-case tests with REAL SMCSignal fixtures:
   - Clean agreement inside killzone -> approve (1.0)
   - Empty active_killzones -> downsize (outside_killzone, 0.6)
   - Direction contradiction -> reject (contradiction)
   - Real catalyst inside holding window -> reject (event_risk)
5. Size factor clamping test: size_factor always in [0.25, 1.0].
6. Asset-class prompt test: options_enabled=False -> no options/IV prompt; options_enabled=True -> options/IV included.
7. End-to-end integration test: Real SMCSignal -> Round Table -> journal_writer.log_trade.
"""
import inspect
import json
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from signal_engine.instrument import Instrument, get_instrument
from signal_engine.smc_detector import (
    SMCSignal,
    OrderBlock,
    FairValueGap,
    analyse_pair,
)
from round_table.schemas import (
    IndependentRead,
    PortfolioState,
    RoundTableInput,
    RoundTableVerdict,
)
from round_table.market_context import Catalyst, build_market_context, set_catalysts_fetcher
from round_table.independent_market_agent import (
    analyse_independently,
    build_system_prompt,
    set_llm_caller as set_market_agent_llm,
)
from round_table.risk_gate_agent import (
    evaluate,
    set_llm_caller as set_risk_gate_llm,
)
from round_table.graph import build_round_table
import journal_writer


class TestRoundTableIsolation(unittest.TestCase):
    """STEP 2: Isolation unit test — assert analyse_independently signature cannot receive proposal/signal."""

    def test_signature_does_not_accept_proposal_or_signal(self):
        sig = inspect.signature(analyse_independently)
        param_names = list(sig.parameters.keys())

        # Exact allowed parameters: instrument and market_context ONLY
        self.assertEqual(param_names, ["instrument", "market_context"])

        # Strictly assert forbidden parameter names
        forbidden = ["proposal", "signal", "portfolio_state", "trade", "bias"]
        for param in forbidden:
            self.assertNotIn(
                param,
                param_names,
                f"Isolation violation: analyse_independently must never accept '{param}'!",
            )


class TestAssetClassPrompt(unittest.TestCase):
    """STEP 2: Asset-class adaptive prompt test."""

    def test_forex_and_crypto_prompts_do_not_mention_options_or_iv(self):
        eurusd = get_instrument("EURUSD")  # Forex, options_enabled=False
        btcusd = get_instrument("BTCUSD")  # Crypto, options_enabled=False

        prompt_forex = build_system_prompt(eurusd)
        prompt_crypto = build_system_prompt(btcusd)

        for prompt in [prompt_forex, prompt_crypto]:
            self.assertNotIn("IV rank", prompt)
            self.assertNotIn("options pricing", prompt)
            self.assertNotIn("iv_rank", prompt)

    def test_equity_and_etf_prompts_include_options_and_iv(self):
        spy = get_instrument("SPY")      # ETF, options_enabled=True
        aapl = get_instrument("AAPL")    # Equity, options_enabled=True

        prompt_spy = build_system_prompt(spy)
        prompt_aapl = build_system_prompt(aapl)

        for prompt in [prompt_spy, prompt_aapl]:
            self.assertIn("IV rank", prompt)
            self.assertIn("options pricing", prompt)
            self.assertIn("iv_rank", prompt)


class TestMarketContextAndEventRisk(unittest.TestCase):
    """STEP 3: Real market context & event risk check."""

    def setUp(self):
        set_risk_gate_llm(None)
        # Isolate from live Alpaca API: no catalysts expected in unit tests
        set_catalysts_fetcher(lambda _inst: [])

    def tearDown(self):
        set_catalysts_fetcher(None)

    def test_empty_catalysts_produces_no_event_risk_flag(self):
        instrument = get_instrument("SPY")
        ctx = build_market_context(instrument)
        self.assertEqual(ctx["catalysts"], [])

        proposal = SMCSignal(
            pair="SPY",
            bias="bullish",
            entry_price=500.0,
            stop_loss=495.0,
            take_profit=510.0,
            rr=2.0,
            confluence_score=5,
            active_killzones=["NY_AM"],
            in_kill_zone=True,
            reason="High confluence bullish setup",
        )
        read = IndependentRead(
            direction="long",
            confidence=0.85,
            reasoning="Bullish order block and liquidity swept.",
            confluence_factors=["bullish order block on H4"],
            catalysts=[],  # genuinely empty
            htf_bias="bullish",
        )

        verdict = evaluate(proposal, read)
        self.assertNotIn("event_risk", verdict.bias_flags)
        self.assertEqual(verdict.decision, "approve")

    def test_catalyst_inside_holding_window_triggers_event_risk_and_reject(self):
        proposal = SMCSignal(
            pair="AAPL",
            bias="bullish",
            entry_price=200.0,
            stop_loss=196.0,
            take_profit=208.0,
            rr=2.0,
            confluence_score=5,
            active_killzones=["NY_AM"],
            in_kill_zone=True,
            reason="Bullish FVG retest",
        )
        # Catalyst in 2 days (holding window is ~3 days)
        read = IndependentRead(
            direction="long",
            confidence=0.85,
            reasoning="Bullish setup with pending earnings",
            confluence_factors=["Bullish FVG"],
            catalysts=[{"type": "earnings", "days_until": 2, "source": "calendar"}],
            htf_bias="bullish",
        )

        verdict = evaluate(proposal, read)
        self.assertIn("event_risk", verdict.bias_flags)
        self.assertEqual(verdict.decision, "reject")


class TestPortfolioConcentration(unittest.TestCase):
    """STEP 4: Portfolio-level exposure awareness."""

    def test_three_same_direction_positions_triggers_concentration_flag(self):
        proposal = SMCSignal(
            pair="NVDA",
            bias="bullish",
            entry_price=120.0,
            stop_loss=116.0,
            take_profit=128.0,
            rr=2.0,
            confluence_score=6,
            active_killzones=["NY_AM"],
            in_kill_zone=True,
            reason="Strong order flow",
        )
        read = IndependentRead(
            direction="long",
            confidence=0.9,
            reasoning="Strong institutional accumulation",
            confluence_factors=["Order block"],
            catalysts=[],
            htf_bias="bullish",
        )
        portfolio = PortfolioState(
            open_positions=[
                {"symbol": "MSFT", "direction": "bullish", "notional_risk": 1000},
                {"symbol": "AAPL", "direction": "bullish", "notional_risk": 1000},
                {"symbol": "SPY", "direction": "bullish", "notional_risk": 1500},
            ],
            total_risk_deployed_pct=3.5,
            same_direction_symbols=["MSFT", "AAPL", "SPY"],  # 3 open bullish positions
        )

        verdict = evaluate(proposal, read, portfolio)
        self.assertIn("portfolio_concentration", verdict.bias_flags)
        self.assertEqual(verdict.decision, "downsize")
        self.assertEqual(verdict.size_factor, 0.6)  # 1 flag -> 0.6


class TestGoldenScenarios(unittest.TestCase):
    """STEP 5: Golden-case tests with REAL SMCSignal fixtures."""

    def setUp(self):
        set_risk_gate_llm(None)
        set_market_agent_llm(None)

    def test_golden_1_clean_agreement_inside_killzone(self):
        """Clean agreement inside killzone with high confluence -> approve, 1.0."""
        proposal = SMCSignal(
            pair="EURUSD",
            bias="bullish",
            entry_price=1.0850,
            stop_loss=1.0820,
            take_profit=1.0910,
            rr=2.0,
            confluence_score=6,
            active_killzones=["London"],
            in_kill_zone=True,
            reason="Bullish OB after London sweep",
        )
        read = IndependentRead(
            direction="long",
            confidence=0.85,
            reasoning="London liquidity sweep with strong displacement.",
            confluence_factors=["Bullish OB on H1", "Equal lows swept"],
            catalysts=[],
            htf_bias="bullish",
        )

        verdict = evaluate(proposal, read)
        self.assertEqual(verdict.decision, "approve")
        self.assertEqual(verdict.bias_flags, [])
        self.assertEqual(verdict.size_factor, 1.0)

    def test_golden_2_outside_killzone(self):
        """Clean setup but outside killzone -> downsize, outside_killzone, 0.6."""
        proposal = SMCSignal(
            pair="GBPUSD",
            bias="bullish",
            entry_price=1.2700,
            stop_loss=1.2670,
            take_profit=1.2760,
            rr=2.0,
            confluence_score=5,
            active_killzones=[],  # Empty killzones
            in_kill_zone=False,
            reason="Asian range breakout attempt",
        )
        read = IndependentRead(
            direction="long",
            confidence=0.8,
            reasoning="Market structure shift on M15.",
            confluence_factors=["Bullish MSS"],
            catalysts=[],
            htf_bias="bullish",
        )

        verdict = evaluate(proposal, read)
        self.assertEqual(verdict.decision, "downsize")
        self.assertIn("outside_killzone", verdict.bias_flags)
        self.assertEqual(verdict.size_factor, 0.6)

    def test_golden_3_direction_contradiction(self):
        """Direction contradiction (bullish vs short) -> reject, contradiction."""
        proposal = SMCSignal(
            pair="USDJPY",
            bias="bullish",
            entry_price=155.0,
            stop_loss=154.5,
            take_profit=156.0,
            rr=2.0,
            confluence_score=5,
            active_killzones=["London_NY_Overlap"],
            in_kill_zone=True,
            reason="Retest of daily level",
        )
        read = IndependentRead(
            direction="short",  # Direct disagreement
            confidence=0.9,
            reasoning="Bearish breaker block and distribution phase active.",
            confluence_factors=["Bearish breaker on H4"],
            catalysts=[],
            htf_bias="bearish",
        )

        verdict = evaluate(proposal, read)
        self.assertEqual(verdict.decision, "reject")
        self.assertIn("contradiction", verdict.bias_flags)

    def test_golden_4_real_catalyst_in_holding_window(self):
        """Real catalyst in holding window -> reject, event_risk."""
        proposal = SMCSignal(
            pair="SPY",
            bias="bullish",
            entry_price=510.0,
            stop_loss=505.0,
            take_profit=520.0,
            rr=2.0,
            confluence_score=5,
            active_killzones=["NY_AM"],
            in_kill_zone=True,
            reason="Bullish trend continuation",
        )
        read = IndependentRead(
            direction="long",
            confidence=0.85,
            reasoning="FOMC rate decision imminent.",
            confluence_factors=["Bullish FVG"],
            catalysts=[{"type": "economic_release", "description": "FOMC", "days_until": 1, "source": "fed"}],
            htf_bias="bullish",
        )

        verdict = evaluate(proposal, read)
        self.assertEqual(verdict.decision, "reject")
        self.assertIn("event_risk", verdict.bias_flags)


class TestSizeFactorClamping(unittest.TestCase):
    """STEP 5: Size factor clamping & deterministic rule testing."""

    def test_deterministic_size_factor_and_clamping(self):
        proposal = SMCSignal(
            pair="SPY",
            bias="bullish",
            entry_price=500.0,
            stop_loss=495.0,
            take_profit=510.0,
            rr=2.0,
            confluence_score=5,
            active_killzones=[],  # Flag 1: outside_killzone
            in_kill_zone=False,
            reason="Test",
        )
        read = IndependentRead(
            direction="long",
            confidence=0.8,
            reasoning="Test read",
            confluence_factors=[],
            catalysts=[],
            htf_bias="bearish",  # Flag 2: htf_conflict
        )

        # Force mock LLM to return an out-of-bounds size factor (e.g. 1.5 or 0.05)
        set_risk_gate_llm(lambda sys, user: json.dumps({
            "decision": "downsize",
            "reason": "Risk flags present",
            "bias_flags": ["outside_killzone", "htf_conflict"],
            "size_factor": 1.5,  # Out of bounds!
        }))

        verdict = evaluate(proposal, read)
        # 2 flags -> deterministic size factor is 0.35, clamped within [0.25, 1.0]
        self.assertEqual(verdict.size_factor, 0.35)
        self.assertGreaterEqual(verdict.size_factor, 0.25)
        self.assertLessEqual(verdict.size_factor, 1.0)
        set_risk_gate_llm(None)


class TestEndToEndRoundTable(unittest.IsolatedAsyncioTestCase):
    """STEP 7 & 8: End-to-end integration test with real SMCSignal -> Round Table -> journal_writer."""

    async def test_end_to_end_flow_and_journal_logging(self):
        instrument = get_instrument("SPY")
        round_table = build_round_table()

        # Mock LLM calls for predictable independent read and risk gate
        set_market_agent_llm(lambda sys, user: json.dumps({
            "direction": "long",
            "confidence": 0.9,
            "reasoning": "Bullish momentum aligned with daily trend.",
            "confluence_factors": ["Bullish Order Block"],
            "catalysts": [],
            "htf_bias": "bullish",
            "iv_rank": 22.5,
        }))

        set_risk_gate_llm(lambda sys, user: json.dumps({
            "decision": "approve",
            "reason": "Consensus on bullish bias with high confluence.",
            "bias_flags": [],
            "size_factor": 1.0,
        }))

        proposal = SMCSignal(
            pair="SPY",
            bias="bullish",
            entry_price=505.50,
            stop_loss=500.00,
            take_profit=516.50,
            rr=2.0,
            confluence_score=6,
            active_killzones=["NY_AM"],
            in_kill_zone=True,
            reason="Bullish OB tap inside NY AM killzone",
        )

        portfolio_state = PortfolioState(
            open_positions=[],
            total_risk_deployed_pct=1.0,
            same_direction_symbols=[],
        )

        # 1. Invoke the Round Table StateGraph
        verdict = round_table.invoke(RoundTableInput(
            instrument=instrument,
            proposal=proposal,
            portfolio_state=portfolio_state,
        ))

        self.assertEqual(verdict.decision, "approve")
        self.assertEqual(verdict.size_factor, 1.0)
        self.assertIsNotNone(verdict.independent_read)
        self.assertEqual(verdict.independent_read.direction, "long")

        # 2. Test logging with journal_writer (mocking DB session)
        mock_session = AsyncMock()
        mock_contract = MagicMock(expiry="2026-09-18", strike=510.0, premium_estimate=3.5)
        mock_position = MagicMock(quantity=2, status="open")

        with patch("journal_writer.get_session") as mock_get_session:
            mock_get_session.return_value.__aenter__.return_value = mock_session
            await journal_writer.log_trade(
                instrument=instrument,
                signal=proposal,
                verdict=verdict,
                contract=mock_contract,
                position=mock_position,
            )

            # Assert database query executed with signal.entry_price
            mock_session.execute.assert_called_once()
            executed_args = mock_session.execute.call_args[0]
            params = executed_args[1]

            self.assertEqual(params["symbol"], "SPY")
            self.assertEqual(params["entry"], 505.50)  # Correct entry_price used
            self.assertEqual(params["verdict_decision"], "approve")
            self.assertEqual(params["size_factor"], 1.0)
            self.assertEqual(params["bias_flags"], [])

        set_market_agent_llm(None)
        set_risk_gate_llm(None)


if __name__ == "__main__":
    unittest.main()


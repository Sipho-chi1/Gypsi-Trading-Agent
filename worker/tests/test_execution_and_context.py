"""
Unit tests for execution pipeline (contract_selector, executor, mcp_client)
and market context integrations.
"""
from dataclasses import dataclass
from unittest.mock import MagicMock, patch
import pytest

from execution.contract_selector import select_contract, calculate_strike, calculate_target_expiry
from execution.executor import place_order, get_live_account_balance, OpenPosition
from execution.mcp_client import AlpacaMCPClient, AlpacaMCPError
from round_table.market_context import build_market_context, fetch_catalysts, fetch_iv_rank, set_catalysts_fetcher
from signal_engine.instrument import get_instrument


@dataclass
class MockSignal:
    bias: str = "bullish"
    entry_price: float = 500.0
    stop_loss: float = 495.0
    take_profit: float = 510.0


@dataclass
class MockVerdict:
    decision: str = "approve"
    size_factor: float = 1.0
    reason: str = "Clear alignment"


def test_calculate_strike_increments():
    # Call options
    call_strike = calculate_strike(500.0, "call", otm_pct=0.01)
    assert call_strike == 505.0 or call_strike == 500.0

    # Put options
    put_strike = calculate_strike(500.0, "put", otm_pct=0.01)
    assert put_strike == 495.0 or put_strike == 500.0

    # Low priced instrument
    low_price_strike = calculate_strike(15.25, "call")
    assert isinstance(low_price_strike, float)


def test_calculate_target_expiry():
    expiry = calculate_target_expiry(days_out=21)
    assert len(expiry) == 10  # YYYY-MM-DD
    assert expiry.count("-") == 2


def test_select_contract_full_consensus():
    inst = get_instrument("SPY")
    signal = MockSignal(bias="bullish", entry_price=510.0)
    verdict = MockVerdict(decision="approve", size_factor=1.0)

    contract = select_contract(inst, signal, verdict)
    assert contract.symbol == "SPY"
    assert contract.option_type == "call"
    assert contract.structure == "single_leg"
    assert contract.strike > 0
    assert contract.premium_estimate > 0


def test_select_contract_downsized():
    inst = get_instrument("QQQ")
    signal = MockSignal(bias="bearish", entry_price=440.0)
    verdict = MockVerdict(decision="downsize", size_factor=0.35)

    contract = select_contract(inst, signal, verdict)
    assert contract.symbol == "QQQ"
    assert contract.option_type == "put"
    assert contract.structure == "vertical_spread"


def test_executor_place_order():
    inst = get_instrument("SPY")
    signal = MockSignal(bias="bullish", entry_price=500.0, stop_loss=495.0)
    verdict = MockVerdict(decision="approve", size_factor=1.0)
    contract = select_contract(inst, signal, verdict)

    with patch("execution.executor.submit_option_order") as mock_submit:
        pos = place_order(inst, signal, contract, verdict, account_balance=100_000.0)
        assert pos.symbol == "SPY"
        assert pos.side == "buy"
        assert pos.quantity >= 1
        assert mock_submit.called


def test_market_context_defaults():
    set_catalysts_fetcher(lambda _: [])
    try:
        inst = get_instrument("SPY")
        context = build_market_context(inst)
        assert "catalysts" in context
        assert isinstance(context["catalysts"], list)
        assert "iv_rank" in context
    finally:
        set_catalysts_fetcher(None)


def test_market_context_forex_no_options():
    set_catalysts_fetcher(lambda _: [])
    try:
        inst = get_instrument("EURUSD")
        context = build_market_context(inst)
        assert "catalysts" in context
        assert "iv_rank" not in context
    finally:
        set_catalysts_fetcher(None)


def test_mcp_client_tool_call():
    client = AlpacaMCPClient(base_url="http://localhost:8080")

    with patch("httpx.Client") as MockClient:
        mock_instance = MockClient.return_value.__enter__.return_value
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "jsonrpc": "2.0",
            "id": "123",
            "result": {"status": "accepted", "id": "order-1"},
        }
        mock_resp.raise_for_status = MagicMock()
        mock_instance.post.return_value = mock_resp

        contract = MagicMock(symbol="SPY", strike=510.0, expiry="2026-09-19", option_type="call")
        res = client.place_option_order(contract, quantity=2, side="buy")
        assert res.get("status") == "accepted"

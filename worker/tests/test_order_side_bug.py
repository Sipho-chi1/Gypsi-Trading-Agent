"""
Regression tests for P0-2: a bearish thesis must still BUY a put — Gypsi
never writes/sells options, it only ever opens a long option position
(a call for bullish, a put for bearish). See execution/executor.py::place_order().
"""
from dataclasses import dataclass
from unittest.mock import patch
import pytest

from execution.contract_selector import select_contract
from execution.executor import place_order
from signal_engine.instrument import get_instrument


@dataclass
class MockSignal:
    bias: str
    entry_price: float = 500.0
    stop_loss: float = 495.0
    take_profit: float = 510.0


@dataclass
class MockVerdict:
    decision: str = "approve"
    size_factor: float = 1.0
    reason: str = "Clear alignment"


@pytest.mark.parametrize(
    "bias,expected_option_type",
    [
        ("bullish", "call"),
        ("bearish", "put"),
    ],
)
def test_contract_selector_maps_bias_to_option_type(bias, expected_option_type):
    inst = get_instrument("SPY")
    signal = MockSignal(bias=bias, entry_price=500.0)
    verdict = MockVerdict(decision="approve", size_factor=1.0)

    contract = select_contract(inst, signal, verdict)
    assert contract.option_type == expected_option_type


@pytest.mark.parametrize("bias", ["bullish", "bearish"])
def test_executor_always_buys_never_sells(bias):
    """
    Currently FAILS for bias="bearish" on unfixed code: executor.py does
    `side = "buy" if signal.bias == "bullish" else "sell"`, which tries to
    SELL (write) a put instead of BUYING it for a bearish thesis. After
    P0-2 is fixed, side should be "buy" in both cases.
    """
    inst = get_instrument("SPY")
    signal = MockSignal(bias=bias, entry_price=500.0, stop_loss=495.0)
    verdict = MockVerdict(decision="approve", size_factor=1.0)
    contract = select_contract(inst, signal, verdict)

    with patch("execution.executor.submit_option_order") as mock_submit:
        pos = place_order(inst, signal, contract, verdict, account_balance=100_000.0)

    assert pos.side == "buy", (
        f"bias={bias!r} produced side={pos.side!r} — a {bias} thesis should "
        f"BUY a {contract.option_type}, never sell/write one."
    )
    mock_submit.assert_called_once_with(contract, pos.quantity, "buy")
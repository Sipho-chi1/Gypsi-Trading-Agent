"""
Regression test for P0-1: run_iteration() must actually AWAIT
journal_writer.log_trade() / log_no_trade(), not just call them and
discard the coroutine.

We substitute AsyncMock for both functions and assert they were actually
AWAITED, not merely called. Calling an async function without awaiting it
still registers as "called" on a mock, but the coroutine never runs —
which is exactly the current bug (nothing lands in Postgres).

Works whether run_iteration is sync (current, buggy) or async (post-fix):
we detect which via inspect.iscoroutinefunction and drive it accordingly.
"""
import asyncio
import inspect
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

import run_loop
from round_table.schemas import PortfolioState, RoundTableVerdict
from signal_engine.instrument import get_instrument


@dataclass
class MockSignal:
    bias: str = "bullish"
    entry_price: float = 500.0
    stop_loss: float = 495.0
    take_profit: float = 510.0
    reason: str = "mock signal"


def _call_run_iteration(*args, **kwargs):
    """Invoke run_iteration whether it's sync (current) or async (post-fix)."""
    if inspect.iscoroutinefunction(run_loop.run_iteration):
        asyncio.run(run_loop.run_iteration(*args, **kwargs))
    else:
        run_loop.run_iteration(*args, **kwargs)


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_rejected_trade_is_actually_logged():
    inst = get_instrument("SPY")
    signal = MockSignal(bias="bullish")
    verdict = RoundTableVerdict(decision="reject", reason="test reject", bias_flags=[])

    fake_round_table = MagicMock()
    fake_round_table.invoke.return_value = verdict

    with patch("run_loop.fetch_multi_tf", return_value={"D1": object()}), \
         patch("run_loop.analyse_pair", return_value=signal), \
         patch("run_loop.can_trade", return_value=(True, "")), \
         patch("run_loop.fetch_portfolio_state", return_value=PortfolioState()), \
         patch("run_loop.log_no_trade", new_callable=AsyncMock) as mock_log_no_trade, \
         patch("run_loop.log_trade", new_callable=AsyncMock) as mock_log_trade:

        _call_run_iteration(fake_round_table, [inst], account_balance=100_000.0)

    assert mock_log_no_trade.await_count == 1, (
        "log_no_trade() was called but never actually AWAITED — the "
        "rejected trade is NOT being written to Postgres (P0-1 bug)."
    )
    mock_log_trade.assert_not_awaited()


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_approved_trade_is_actually_logged():
    inst = get_instrument("SPY")
    signal = MockSignal(bias="bullish", entry_price=500.0, stop_loss=495.0)
    verdict = RoundTableVerdict(
        decision="approve", reason="test approve", bias_flags=[], size_factor=1.0
    )

    fake_round_table = MagicMock()
    fake_round_table.invoke.return_value = verdict
    fake_position = MagicMock(quantity=1, status="open")

    with patch("run_loop.fetch_multi_tf", return_value={"D1": object()}), \
         patch("run_loop.analyse_pair", return_value=signal), \
         patch("run_loop.can_trade", return_value=(True, "")), \
         patch("run_loop.fetch_portfolio_state", return_value=PortfolioState()), \
         patch("run_loop.select_contract", return_value=MagicMock(expiry="2026-09-19", strike=505.0)), \
         patch("run_loop.place_order", return_value=fake_position), \
         patch("run_loop.log_no_trade", new_callable=AsyncMock) as mock_log_no_trade, \
         patch("run_loop.log_trade", new_callable=AsyncMock) as mock_log_trade:

        _call_run_iteration(fake_round_table, [inst], account_balance=100_000.0)

    assert mock_log_trade.await_count == 1, (
        "log_trade() was called but never actually AWAITED — the "
        "approved trade is NOT being written to Postgres (P0-1 bug)."
    )
    mock_log_no_trade.assert_not_awaited()
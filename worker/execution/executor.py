"""
Execution Agent — the last stage. Consumes a RoundTableVerdict and either
places an order (approve/downsize) or logs a skip (reject). Mirrors the
branching style of the original forex_bot/executor.py's place_order(), but
routes through the Alpaca CLI instead of MT5 or an MCP sidecar.
"""
from dataclasses import dataclass
import logging

from execution.alpaca_cli_client import get_account, submit_option_order, AlpacaCLIError
from signal_engine.risk_manager import position_size

logger = logging.getLogger(__name__)


@dataclass
class OpenPosition:
    symbol: str
    quantity: int
    side: str
    contract: object
    status: str = "open"


def get_live_account_balance(fallback: float = 100_000.0) -> float:
    """Pulls live account equity via alpaca_cli_client.get_account() with fallback."""
    try:
        acc = get_account()
        if isinstance(acc, dict) and "equity" in acc:
            return float(acc["equity"])
    except (AlpacaCLIError, KeyError, ValueError, Exception) as e:
        logger.debug("Using fallback balance for position sizing: %s", e)
    return fallback


def place_order(instrument, signal, contract, verdict, account_balance: float | None = None) -> OpenPosition:
    if account_balance is None:
        account_balance = get_live_account_balance()

    sizing = position_size(
        account_balance=account_balance,
        entry=signal.entry_price,
        stop_loss=signal.stop_loss,
        instrument=instrument,
        is_options=True,
        contract_premium=contract.premium_estimate,
    )
    qty = max(int(sizing.quantity * verdict.size_factor), 0)
    if qty == 0:
        return OpenPosition(instrument.symbol, 0, "none", contract, status="skipped_zero_size")

    side = "buy" if signal.bias == "bullish" else "sell"
    submit_option_order(contract, qty, side)
    return OpenPosition(instrument.symbol, qty, side, contract)

"""
Execution Agent — the last stage. Consumes a RoundTableVerdict and either
places an order (approve/downsize) or logs a skip (reject). Mirrors the
branching style of the original forex_bot/executor.py's place_order(), but
routes through the Alpaca MCP client instead of MT5.
"""
from dataclasses import dataclass

from execution.mcp_client import AlpacaMCPClient
from signal_engine.risk_manager import position_size

_mcp = AlpacaMCPClient()


@dataclass
class OpenPosition:
    symbol: str
    quantity: int
    side: str
    contract: object
    status: str = "open"


def place_order(instrument, signal, contract, verdict) -> OpenPosition:
    sizing = position_size(
        account_balance=100_000.0,  # TODO: pull live equity
        entry=signal.entry,
        stop_loss=signal.stop_loss,
        instrument=instrument,
        is_options=True,
        contract_premium=contract.premium_estimate,
    )
    qty = max(int(sizing.quantity * verdict.size_factor), 0)
    if qty == 0:
        return OpenPosition(instrument.symbol, 0, "none", contract, status="skipped_zero_size")

    side = "buy" if signal.bias == "bullish" else "sell"
    _mcp.place_option_order(contract, qty, side)
    return OpenPosition(instrument.symbol, qty, side, contract)

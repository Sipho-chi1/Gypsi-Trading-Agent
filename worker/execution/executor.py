"""
Execution Agent — the last stage. Consumes a RoundTableVerdict and either
places an order (approve/downsize) or logs a skip (reject). Mirrors the
branching style of the original forex_bot/executor.py's place_order(), but
routes through the Alpaca CLI instead of MT5 or an MCP sidecar.
"""
from dataclasses import dataclass

from execution.alpaca_cli_client import submit_option_order
from signal_engine.risk_manager import position_size


@dataclass
class OpenPosition:
    symbol: str
    quantity: int
    side: str
    contract: object
    status: str = "open"


def place_order(instrument, signal, contract, verdict) -> OpenPosition:
    sizing = position_size(
        account_balance=100_000.0,  # TODO: pull live equity via alpaca_cli_client.get_account()
        entry=signal.entry_price,
        stop_loss=signal.stop_loss,   # was missing entirely — position_size() requires
                                        # this positionally between entry and instrument;
                                        # the previous version would have raised a TypeError
                                        # the first time this function actually ran.
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

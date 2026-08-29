"""
Risk Manager Module — Position sizing & pre-trade kill switch.

Supports:
- Dollar-risk sizing for Equities / Shares.
- Premium-at-risk sizing for Options.
- Standard/Mini/Micro lot sizing for Forex.
- Account-level daily drawdown and loss streak kill switches.
"""
from dataclasses import dataclass
from typing import Optional, Union

from signal_engine.instrument import Instrument, get_instrument

RISK_PER_TRADE_PCT = 0.01          # 1% of account equity per trade
MAX_DAILY_LOSS_PCT = 0.03          # kill switch for the day (3% max loss)
MAX_CONSECUTIVE_LOSSES = 4


@dataclass
class SizingResult:
    quantity: float        # shares, options contracts, or forex lots
    risk_dollars: float
    notes: str = ""


def position_size(
    account_balance: float,
    entry: float,
    stop_loss: float,
    instrument: Union[str, Instrument],
    is_options: bool = False,
    contract_premium: Optional[float] = None,
) -> SizingResult:
    """Calculate position size across Equities, Options, and Forex."""
    inst = get_instrument(instrument)
    risk_dollars = account_balance * RISK_PER_TRADE_PCT

    if is_options:
        if not contract_premium:
            raise ValueError("contract_premium required for options sizing")
        max_loss_per_contract = contract_premium * inst.contract_multiplier
        qty = max(int(risk_dollars // max_loss_per_contract), 0)
        return SizingResult(float(qty), risk_dollars, "sized on premium at risk")

    if inst.asset_class == "forex":
        stop_pips = inst.price_to_pips(abs(entry - stop_loss))
        if stop_pips <= 0:
            return SizingResult(0.0, risk_dollars, "invalid stop distance")
        # Standard lot pip value = $10 per pip per 100k lot on EURUSD
        pip_value_per_standard_lot = (10.0 if "JPY" not in inst.symbol else 9.0)
        lot_size = risk_dollars / (stop_pips * pip_value_per_standard_lot)
        return SizingResult(round(lot_size, 2), risk_dollars, "sized on forex lot risk")

    # Equities / Shares
    price_risk_per_share = abs(entry - stop_loss)
    if price_risk_per_share <= 0:
        return SizingResult(0.0, risk_dollars, "invalid stop distance")
    qty = int(risk_dollars // price_risk_per_share)
    return SizingResult(float(qty), risk_dollars, "sized on stop distance")


def can_trade(
    account_balance: float,
    daily_pnl: float = 0.0,
    consecutive_losses: int = 0,
) -> tuple[bool, str]:
    """Pre-Round-Table kill-switch checks."""
    if daily_pnl <= -account_balance * MAX_DAILY_LOSS_PCT:
        return False, "daily loss cap hit"
    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        return False, "consecutive loss limit hit"
    return True, "ok"

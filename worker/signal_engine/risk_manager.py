"""
Rewritten from forex_bot/risk_manager.py.

The original calculate_position_size_lots() / get_pip_value() were built
entirely around forex lot math (standard lot = 100k units) — that concept
doesn't exist for equities or options. This version sizes every position as
a fraction of account equity in dollar terms, and branches on options vs
underlying so premium-at-risk sizing (options) and price-distance sizing
(shares) don't get conflated.

can_trade() — the pre-Round-Table sanity/kill-switch check — is carried
over unchanged in spirit from the original.
"""
from dataclasses import dataclass

RISK_PER_TRADE_PCT = 0.01          # 1% of account equity per trade
MAX_DAILY_LOSS_PCT = 0.03          # kill switch for the day
MAX_CONSECUTIVE_LOSSES = 4


@dataclass
class SizingResult:
    quantity: int          # shares, or number of options contracts
    risk_dollars: float
    notes: str = ""


def position_size(account_balance: float, entry: float, stop_loss: float,
                   instrument, is_options: bool = True,
                   contract_premium: float | None = None) -> SizingResult:
    risk_dollars = account_balance * RISK_PER_TRADE_PCT

    if is_options:
        if not contract_premium:
            raise ValueError("contract_premium required for options sizing")
        max_loss_per_contract = contract_premium * instrument.contract_multiplier
        qty = max(int(risk_dollars // max_loss_per_contract), 0)
        return SizingResult(qty, risk_dollars, "sized on premium at risk")

    price_risk_per_share = abs(entry - stop_loss)
    if price_risk_per_share <= 0:
        return SizingResult(0, risk_dollars, "invalid stop distance")
    qty = int(risk_dollars // price_risk_per_share)
    return SizingResult(qty, risk_dollars, "sized on stop distance")


def can_trade(account_balance: float, daily_pnl: float = 0.0,
              consecutive_losses: int = 0) -> tuple[bool, str]:
    """Pre-Round-Table kill-switch — cheap checks that run before we bother
    paying for any LLM calls."""
    if daily_pnl <= -account_balance * MAX_DAILY_LOSS_PCT:
        return False, "daily loss cap hit"
    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        return False, "consecutive loss limit hit"
    return True, "ok"

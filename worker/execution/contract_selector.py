"""
Options contract selection — the one piece with no analog in the original
forex bot (forex has no options). Maps the Round Table's verdict/conviction
level to a concrete, defined-risk options structure.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class ContractSelection:
    symbol: str
    expiry: str            # e.g. "2026-09-19"
    strike: float
    option_type: str       # "call" | "put"
    structure: str          # "single_leg" | "vertical_spread"
    premium_estimate: float


def calculate_target_expiry(days_out: int = 21, base_date: datetime | None = None) -> str:
    """Calculates the target Friday expiration date ~2-4 weeks out."""
    base = base_date or datetime.now()
    target = base + timedelta(days=days_out)
    days_to_friday = (4 - target.weekday()) % 7
    friday = target + timedelta(days=days_to_friday)
    return friday.strftime("%Y-%m-%d")


def calculate_strike(entry_price: float, option_type: str, otm_pct: float = 0.01) -> float:
    """
    Calculates strike price near ~30-50 delta (slightly OTM or ATM).
    Rounds to appropriate strike increments for equity/ETF options.
    """
    if entry_price >= 200:
        step = 5.0 if entry_price >= 500 else 2.5
    elif entry_price >= 50:
        step = 1.0
    elif entry_price >= 20:
        step = 0.5
    else:
        step = 0.1

    if option_type == "call":
        raw_strike = entry_price * (1.0 + otm_pct)
    else:
        raw_strike = entry_price * (1.0 - otm_pct)

    return round(round(raw_strike / step) * step, 2)


def select_contract(instrument, signal, verdict) -> ContractSelection:
    """
    Policy:
      - full consensus (size_factor >= 0.8) -> single-leg call/put,
        ~30-50 delta, 2-4 weeks out.
      - downsize (0 < size_factor < 0.8) -> defined-risk vertical
        spread instead of a naked leg, to cap worst case.
    """
    bias_str = str(getattr(signal, "bias", "bullish")).lower()
    option_type = "call" if bias_str in ("bullish", "long", "buy") else "put"

    size_factor = float(getattr(verdict, "size_factor", 1.0))
    structure = "single_leg" if size_factor >= 0.8 else "vertical_spread"

    expiry = calculate_target_expiry(days_out=21)
    entry_price = float(getattr(signal, "entry_price", 100.0))
    strike = calculate_strike(entry_price, option_type)

    # Estimate option premium (~2.0% of underlying stock price for a 2-4 week option)
    premium_estimate = round(max(0.20, entry_price * 0.02), 2)

    symbol = getattr(instrument, "symbol", str(instrument))
    return ContractSelection(
        symbol=symbol,
        expiry=expiry,
        strike=strike,
        option_type=option_type,
        structure=structure,
        premium_estimate=premium_estimate,
    )

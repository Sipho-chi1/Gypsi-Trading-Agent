"""
Instrument abstraction — the piece that makes the SMC detector work on any
market, not just forex.

The original bot hardcoded pip size, lot-based position sizing, and forex
session windows throughout smc_detector.py / risk_manager.py / config.py.
Every one of those assumptions gets replaced by a per-instrument config
object instead of a global constant, so the detection math (swing structure,
order blocks, FVGs, CHoCH/BOS) can stay asset-agnostic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Union


@dataclass(frozen=True)
class Instrument:
    symbol: str
    asset_class: str            # "equity" | "etf" | "crypto" | "forex"
    tick_size: float            # replaces hardcoded pip-size logic
    market_open: time | None = None    # None for 24/7 or 24/5 assets
    market_close: time | None = None
    contract_multiplier: int = 100   # standard equity options multiplier, 100_000 for standard forex lot
    options_enabled: bool = True

    @property
    def pip_size(self) -> float:
        """Returns the pip size for forex or the tick size for equities."""
        if self.asset_class == "forex":
            return 0.01 if "JPY" in self.symbol.upper() else 0.0001
        return self.tick_size

    def price_to_pips(self, price_diff: float) -> float:
        """Converts price distance into pips or tick equivalents."""
        unit = self.pip_size
        return abs(price_diff) / unit if unit > 0 else 0.0


# Watchlist & catalogue for Equities, ETFs, Crypto, and Forex
_CATALOGUE: dict[str, Instrument] = {
    # Equities & ETFs
    "SPY": Instrument("SPY", "etf", tick_size=0.01, market_open=time(9, 30), market_close=time(16, 0)),
    "QQQ": Instrument("QQQ", "etf", tick_size=0.01, market_open=time(9, 30), market_close=time(16, 0)),
    "AAPL": Instrument("AAPL", "equity", tick_size=0.01, market_open=time(9, 30), market_close=time(16, 0)),
    "MSFT": Instrument("MSFT", "equity", tick_size=0.01, market_open=time(9, 30), market_close=time(16, 0)),
    "NVDA": Instrument("NVDA", "equity", tick_size=0.01, market_open=time(9, 30), market_close=time(16, 0)),
    # Forex Majors & Crosses
    "EURUSD": Instrument("EURUSD", "forex", tick_size=0.00001, contract_multiplier=100_000, options_enabled=False),
    "GBPUSD": Instrument("GBPUSD", "forex", tick_size=0.00001, contract_multiplier=100_000, options_enabled=False),
    "USDJPY": Instrument("USDJPY", "forex", tick_size=0.001, contract_multiplier=100_000, options_enabled=False),
    "AUDUSD": Instrument("AUDUSD", "forex", tick_size=0.00001, contract_multiplier=100_000, options_enabled=False),
    "EURGBP": Instrument("EURGBP", "forex", tick_size=0.00001, contract_multiplier=100_000, options_enabled=False),
    "USDCAD": Instrument("USDCAD", "forex", tick_size=0.00001, contract_multiplier=100_000, options_enabled=False),
    "USDCHF": Instrument("USDCHF", "forex", tick_size=0.00001, contract_multiplier=100_000, options_enabled=False),
    # Crypto
    "BTCUSD": Instrument("BTCUSD", "crypto", tick_size=0.01, contract_multiplier=1, options_enabled=False),
    "ETHUSD": Instrument("ETHUSD", "crypto", tick_size=0.01, contract_multiplier=1, options_enabled=False),
}


def get_instrument(symbol_or_instrument: Union[str, Instrument]) -> Instrument:
    """Retrieve an Instrument object or generate a suitable fallback."""
    if isinstance(symbol_or_instrument, Instrument):
        return symbol_or_instrument
    sym = str(symbol_or_instrument).upper()
    if sym in _CATALOGUE:
        return _CATALOGUE[sym]
    # Inferred fallback
    if len(sym) == 6 and sym.isalpha():
        # likely forex pair
        tick = 0.001 if "JPY" in sym else 0.00001
        return Instrument(sym, "forex", tick_size=tick, contract_multiplier=100_000, options_enabled=False)
    return Instrument(sym, "equity", tick_size=0.01, market_open=time(9, 30), market_close=time(16, 0))


def load_watchlist(symbols: list[str]) -> list[Instrument]:
    return [get_instrument(s) for s in symbols]

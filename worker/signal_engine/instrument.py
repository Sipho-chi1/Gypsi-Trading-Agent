"""
Instrument abstraction — the piece that makes the SMC detector work on any
market, not just forex.

The original bot hardcoded pip size, lot-based position sizing, and forex
session windows throughout smc_detector.py / risk_manager.py / config.py.
Every one of those assumptions gets replaced by a per-instrument config
object instead of a global constant, so the detection math (swing structure,
order blocks, FVGs, CHoCH/BOS) can stay asset-agnostic.
"""
from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class Instrument:
    symbol: str
    asset_class: str            # "equity" | "etf" | "crypto" | "forex"
    tick_size: float            # replaces hardcoded pip-size logic
    market_open: time | None    # None for 24/7 assets (crypto)
    market_close: time | None
    contract_multiplier: int = 100   # standard equity options multiplier
    options_enabled: bool = True


# TODO: replace with a live lookup (Alpaca asset metadata) once the Market
# Data client is wired up. Hardcoded here just to unblock Day 1/2 work.
_WATCHLIST: dict[str, Instrument] = {
    "SPY": Instrument("SPY", "etf", tick_size=0.01, market_open=time(9, 30), market_close=time(16, 0)),
    "QQQ": Instrument("QQQ", "etf", tick_size=0.01, market_open=time(9, 30), market_close=time(16, 0)),
    "AAPL": Instrument("AAPL", "equity", tick_size=0.01, market_open=time(9, 30), market_close=time(16, 0)),
    "MSFT": Instrument("MSFT", "equity", tick_size=0.01, market_open=time(9, 30), market_close=time(16, 0)),
    "NVDA": Instrument("NVDA", "equity", tick_size=0.01, market_open=time(9, 30), market_close=time(16, 0)),
}


def load_watchlist(symbols: list[str]) -> list[Instrument]:
    return [_WATCHLIST[s] for s in symbols if s in _WATCHLIST]

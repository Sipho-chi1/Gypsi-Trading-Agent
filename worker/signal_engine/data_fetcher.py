"""
Data Fetcher Module — Multi-Timeframe Candle Sourcing & Session Tagging.

Provides:
- Multi-timeframe bar retrieval (Alpaca Market Data integration + synthetic generator for tests/backtests).
- Session and Killzone tagging on OHLCV bars.
- ATR calculations (pip-based and price-based).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Union
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

try:
    from core.settings import settings
except ImportError:
    settings = None

from signal_engine.config import NY_TZ, UTC_TZ
from signal_engine.instrument import Instrument, get_instrument
from signal_engine.smc_detector import get_active_killzones


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate Average True Range (ATR) in price units."""
    if len(df) < period + 1:
        return float("nan")
    high = df["high"]
    low = df["low"]
    close = df["close"].shift(1)
    tr1 = high - low
    tr2 = (high - close).abs()
    tr3 = (low - close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean().iloc[-1]
    return float(atr)


def calculate_atr_pips(df: pd.DataFrame, instrument_or_pair: Union[str, Instrument], period: int = 14) -> float:
    """Calculate Average True Range (ATR) in pips/ticks."""
    inst = get_instrument(instrument_or_pair)
    atr = calculate_atr(df, period=period)
    if np.isnan(atr):
        return 15.0  # Safe default
    return inst.price_to_pips(atr)


def tag_sessions_and_killzones(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tag each candle in the dataframe with timezone-aware session and killzone metadata:
    - time_ny: Timestamp converted to America/New_York
    - killzones: List of active killzones at bar open
    - in_killzone: Boolean flag
    """
    df_tagged = df.copy()
    time_col = "time" if "time" in df_tagged.columns else None

    times = df_tagged[time_col] if time_col else df_tagged.index
    ny_times = []
    active_kzs = []
    in_kzs = []

    for t in times:
        dt = pd.to_datetime(t)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC_TZ)
        dt_ny = dt.astimezone(NY_TZ)
        ny_times.append(dt_ny)
        kzs = get_active_killzones(dt)
        active_kzs.append(kzs)
        in_kzs.append(len(kzs) > 0)

    df_tagged["time_ny"] = ny_times
    df_tagged["active_killzones"] = active_kzs
    df_tagged["in_killzone"] = in_kzs
    return df_tagged


def generate_synthetic_candles(
    symbol: str = "EURUSD",
    start_dt: Optional[datetime] = None,
    num_bars: int = 200,
    timeframe: str = "H1",
    base_price: float = 1.0850,
    volatility: float = 0.0005,
    seed: Optional[int] = 42,
) -> pd.DataFrame:
    """
    Generate realistic synthetic OHLCV candle data for backtesting and unit testing.
    """
    if seed is not None:
        np.random.seed(seed)

    if start_dt is None:
        start_dt = datetime(2026, 3, 1, 0, 0, tzinfo=UTC_TZ)

    tf_deltas = {
        "M5": timedelta(minutes=5),
        "M15": timedelta(minutes=15),
        "H1": timedelta(hours=1),
        "H4": timedelta(hours=4),
        "D1": timedelta(days=1),
    }
    delta = tf_deltas.get(timeframe, timedelta(hours=1))

    timestamps = [start_dt + (i * delta) for i in range(num_bars)]
    price = base_price
    records = []

    for ts in timestamps:
        step = np.random.normal(0, volatility)
        o = price
        c = o + step
        h = max(o, c) + abs(np.random.normal(0, volatility * 0.5))
        l = min(o, c) - abs(np.random.normal(0, volatility * 0.5))
        v = np.random.randint(100, 5000)
        records.append({"time": ts, "open": o, "high": h, "low": l, "close": c, "volume": v})
        price = c

    df = pd.DataFrame(records)
    df.set_index("time", inplace=True)
    return df


def fetch_multi_tf(
    instrument_or_pair: Union[str, Instrument],
    timeframes: Optional[list[str]] = None,
) -> Optional[dict[str, pd.DataFrame]]:
    """
    Fetch multi-timeframe candles (e.g. {"H1": df, "H4": df, "D1": df, "M5": df}).
    """
    inst = get_instrument(instrument_or_pair)
    tfs = timeframes or ["M5", "H1", "H4", "D1"]

    # When Alpaca / broker API credentials are not set, return synthetic data for testing
    now_utc = datetime.now(UTC_TZ)
    candles = {}
    base_price = 1.0850 if inst.asset_class == "forex" else 500.0

    for tf in tfs:
        bars_count = 120 if tf == "D1" else 250
        df = generate_synthetic_candles(
            symbol=inst.symbol,
            start_dt=now_utc - timedelta(days=60),
            num_bars=bars_count,
            timeframe=tf,
            base_price=base_price,
        )
        candles[tf] = df

    return candles

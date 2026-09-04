"""
Data Fetcher Module — Multi-Timeframe Candle Sourcing & Session Tagging.

Provides:
- Multi-timeframe bar retrieval (Alpaca Market Data integration + synthetic generator for tests/backtests).
- Session and Killzone tagging on OHLCV bars.
- ATR calculations (pip-based and price-based).
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Optional, Union
from zoneinfo import ZoneInfo

import httpx
import numpy as np
import pandas as pd

try:
    from core.settings import settings
except ImportError:
    settings = None

from signal_engine.config import NY_TZ, UTC_TZ
from signal_engine.instrument import Instrument, get_instrument
from signal_engine.smc_detector import get_active_killzones

logger = logging.getLogger(__name__)


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


ALPACA_TIMEFRAME_MAP = {
    "M1": "1Min",
    "M5": "5Min",
    "M15": "15Min",
    "H1": "1Hour",
    "H4": "4Hour",
    "D1": "1Day",
}


def _parse_alpaca_bars(bars_data: Union[list, dict], symbol: str) -> list[dict]:
    """Extract list of bar dicts from Alpaca response payload."""
    if isinstance(bars_data, list):
        return bars_data
    if isinstance(bars_data, dict):
        if symbol in bars_data and isinstance(bars_data[symbol], list):
            return bars_data[symbol]
        # Check slash notation for crypto e.g. BTC/USD
        if "/" not in symbol and len(symbol) == 6:
            slash_sym = f"{symbol[:3]}/{symbol[3:]}"
            if slash_sym in bars_data and isinstance(bars_data[slash_sym], list):
                return bars_data[slash_sym]
        for val in bars_data.values():
            if isinstance(val, list):
                return val
    return []


def _bars_to_dataframe(bars: list[dict]) -> pd.DataFrame:
    """Convert Alpaca bars into DataFrame matching generate_synthetic_candles output."""
    records = []
    for b in bars:
        records.append({
            "time": pd.to_datetime(b["t"]),
            "open": float(b["o"]),
            "high": float(b["h"]),
            "low": float(b["l"]),
            "close": float(b["c"]),
            "volume": float(b["v"]),
        })
    df = pd.DataFrame(records)
    df.set_index("time", inplace=True)
    return df


def fetch_multi_tf(
    instrument_or_pair: Union[str, Instrument],
    timeframes: Optional[list[str]] = None,
) -> Optional[dict[str, pd.DataFrame]]:
    """
    Fetch multi-timeframe candles (e.g. {"H1": df, "H4": df, "D1": df, "M5": df}).
    Fetches real bars from Alpaca Market Data API when credentials are set,
    falling back to synthetic candles when credentials are unset, forex is used,
    or the live API call fails.
    """
    inst = get_instrument(instrument_or_pair)
    tfs = timeframes or ["M5", "H1", "H4", "D1"]

    now_utc = datetime.now(UTC_TZ)
    candles = {}
    base_price = 1.0850 if inst.asset_class == "forex" else 500.0

    def _fallback_synthetic(tf: str) -> pd.DataFrame:
        bars_count = 120 if tf == "D1" else 250
        return generate_synthetic_candles(
            symbol=inst.symbol,
            start_dt=now_utc - timedelta(days=60),
            num_bars=bars_count,
            timeframe=tf,
            base_price=base_price,
        )

    # 1. Forex check: Alpaca does not provide forex market data
    if inst.asset_class == "forex":
        logger.warning(
            "Forex asset class (%s) is not supported by Alpaca Market Data API — running on synthetic data by design",
            inst.symbol,
        )
        for tf in tfs:
            candles[tf] = _fallback_synthetic(tf)
        return candles

    # 2. Credential check
    api_key = getattr(settings, "ALPACA_API_KEY", "") if settings else ""
    secret_key = getattr(settings, "ALPACA_SECRET_KEY", "") if settings else ""

    if not api_key or not secret_key:
        logger.warning(
            "Alpaca API credentials missing (ALPACA_API_KEY / ALPACA_SECRET_KEY not set) — falling back to synthetic candles for %s",
            inst.symbol,
        )
        for tf in tfs:
            candles[tf] = _fallback_synthetic(tf)
        return candles

    # 3. Check supported asset classes for live Alpaca data
    if inst.asset_class not in ("equity", "etf", "crypto"):
        logger.warning(
            "Asset class '%s' for %s is not supported by Alpaca Market Data API — falling back to synthetic candles",
            inst.asset_class,
            inst.symbol,
        )
        for tf in tfs:
            candles[tf] = _fallback_synthetic(tf)
        return candles

    # 4. Fetch live bars from Alpaca Market Data API
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            for tf in tfs:
                bars_count = 120 if tf == "D1" else 250
                alpaca_tf = ALPACA_TIMEFRAME_MAP.get(tf, tf)

                if inst.asset_class in ("equity", "etf"):
                    url = f"https://data.alpaca.markets/v2/stocks/{inst.symbol}/bars"
                    params = {"timeframe": alpaca_tf, "limit": bars_count}
                elif inst.asset_class == "crypto":
                    url = "https://data.alpaca.markets/v1beta3/crypto/us/bars"
                    params = {"symbols": inst.symbol, "timeframe": alpaca_tf, "limit": bars_count}
                else:
                    candles[tf] = _fallback_synthetic(tf)
                    continue

                try:
                    resp = client.get(url, headers=headers, params=params)
                    if resp.status_code != 200:
                        logger.warning(
                            "Alpaca Market Data API returned status %s for %s (%s): %s — falling back to synthetic candles",
                            resp.status_code,
                            inst.symbol,
                            tf,
                            resp.text,
                        )
                        candles[tf] = _fallback_synthetic(tf)
                        continue

                    data = resp.json()
                    bars = _parse_alpaca_bars(data.get("bars", []), inst.symbol)
                    if not bars:
                        logger.warning(
                            "Alpaca Market Data API returned empty bars payload for %s (%s) — falling back to synthetic candles",
                            inst.symbol,
                            tf,
                        )
                        candles[tf] = _fallback_synthetic(tf)
                        continue

                    df = _bars_to_dataframe(bars)
                    candles[tf] = df

                except Exception as e:
                    logger.warning(
                        "Failed to fetch live bars from Alpaca for %s (%s): %s — falling back to synthetic candles",
                        inst.symbol,
                        tf,
                        e,
                    )
                    candles[tf] = _fallback_synthetic(tf)

    except Exception as e:
        logger.warning(
            "Alpaca Market Data HTTP client error for %s: %s — falling back to synthetic candles",
            inst.symbol,
            e,
        )
        for tf in tfs:
            if tf not in candles:
                candles[tf] = _fallback_synthetic(tf)

    return candles

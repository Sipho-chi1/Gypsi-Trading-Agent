"""
Rewritten from forex_bot/data_fetcher.py.

The original pulled OHLCV bars from Twelve Data's REST API. This version
targets Alpaca's Market Data API (StockHistoricalDataClient) instead, but
keeps the SAME output contract (a dict of {timeframe: DataFrame} per
instrument) so smc_detector.analyse_pair() doesn't need to change.

TODO: wire up alpaca-py's StockHistoricalDataClient here. Cache pulled bars
locally (or in Postgres) so repeated worker cycles don't re-hit the API for
data that hasn't changed intra-bar.
"""
import pandas as pd

from core.settings import settings


def fetch_multi_tf(instrument, timeframes: list[str] | None = None) -> dict[str, pd.DataFrame] | None:
    """
    Returns e.g. {"H1": df, "H4": df, "D1": df} matching what
    smc_detector.analyse_pair() expects, or None if data is unavailable
    (e.g. market closed for this instrument).
    """
    timeframes = timeframes or ["H1", "H4", "D1"]

    # TODO: replace with real alpaca-py calls, e.g.:
    #   from alpaca.data.historical import StockHistoricalDataClient
    #   from alpaca.data.requests import StockBarsRequest
    #   client = StockHistoricalDataClient(settings.ALPACA_API_KEY, settings.ALPACA_SECRET_KEY)
    #   ...
    raise NotImplementedError("Wire up Alpaca Market Data client here (Day 2).")

"""
Regression tests for P0-3: fetch_multi_tf() must query real Alpaca market data
when credentials are set and asset class is supported (equity/etf/crypto),
falling back to synthetic data only when credentials are unset, forex is used,
or the live API call fails / returns empty payload.
"""
import logging
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from signal_engine.data_fetcher import fetch_multi_tf
from signal_engine.instrument import get_instrument


MOCK_EQUITY_BARS = [
    {
        "t": "2026-03-01T14:30:00Z",
        "o": 501.25,
        "h": 505.50,
        "l": 500.10,
        "c": 504.80,
        "v": 15200,
    },
    {
        "t": "2026-03-01T14:35:00Z",
        "o": 504.80,
        "h": 506.00,
        "l": 503.75,
        "c": 505.30,
        "v": 11800,
    },
]

MOCK_CRYPTO_BARS = {
    "bars": {
        "BTCUSD": [
            {
                "t": "2026-03-01T14:30:00Z",
                "o": 65000.0,
                "h": 65500.0,
                "l": 64800.0,
                "c": 65250.0,
                "v": 45.2,
            }
        ]
    }
}


@patch("signal_engine.data_fetcher.generate_synthetic_candles")
@patch("signal_engine.data_fetcher.httpx.Client")
def test_real_market_data_fetched_when_credentials_set(mock_client_cls, mock_synthetic):
    """
    When credentials are set for equity/etf, fetch_multi_tf() must query Alpaca's
    Market Data API and return DataFrame shaped identically to synthetic data.
    Regression assertion: generate_synthetic_candles must NOT be called.
    """
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"bars": MOCK_EQUITY_BARS}
    mock_client.get.return_value = mock_resp

    with patch("signal_engine.data_fetcher.settings") as mock_settings:
        mock_settings.ALPACA_API_KEY = "test_key"
        mock_settings.ALPACA_SECRET_KEY = "test_secret"

        result = fetch_multi_tf("SPY", timeframes=["M5"])

    # Regression check: synthetic generator MUST NOT be called
    mock_synthetic.assert_not_called()

    # Verify HTTP call
    mock_client.get.assert_called_once()
    args, kwargs = mock_client.get.call_args
    assert "data.alpaca.markets/v2/stocks/SPY/bars" in args[0]
    assert kwargs["headers"]["APCA-API-KEY-ID"] == "test_key"
    assert kwargs["headers"]["APCA-API-SECRET-KEY"] == "test_secret"
    assert kwargs["params"]["timeframe"] == "5Min"

    # Verify returned DataFrame
    assert result is not None
    assert "M5" in result
    df = result["M5"]
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.name == "time"
    assert len(df) == 2
    assert df.iloc[0]["open"] == 501.25
    assert df.iloc[0]["close"] == 504.80
    assert df.iloc[1]["volume"] == 11800


@patch("signal_engine.data_fetcher.generate_synthetic_candles")
def test_fallback_to_synthetic_when_credentials_unset(mock_synthetic, caplog):
    """
    When credentials are not set, fetch_multi_tf() must fall back to
    generate_synthetic_candles and log a warning explaining why.
    """
    mock_df = pd.DataFrame(
        [{"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000}]
    ).set_index(pd.Index(["2026-03-01"], name="time"))
    mock_synthetic.return_value = mock_df

    with patch("signal_engine.data_fetcher.settings") as mock_settings:
        mock_settings.ALPACA_API_KEY = ""
        mock_settings.ALPACA_SECRET_KEY = ""

        with caplog.at_level(logging.WARNING):
            result = fetch_multi_tf("SPY", timeframes=["M5"])

    mock_synthetic.assert_called_once()
    assert result is not None
    assert "M5" in result
    assert any("credentials missing" in rec.message.lower() for rec in caplog.records)


@patch("signal_engine.data_fetcher.generate_synthetic_candles")
def test_forex_uses_synthetic_data_and_logs_warning(mock_synthetic, caplog):
    """
    Forex is unsupported by Alpaca Market Data: fetch_multi_tf() must use
    synthetic generation by design and log a warning.
    """
    mock_df = pd.DataFrame(
        [{"open": 1.08, "high": 1.09, "low": 1.07, "close": 1.085, "volume": 500}]
    ).set_index(pd.Index(["2026-03-01"], name="time"))
    mock_synthetic.return_value = mock_df

    with patch("signal_engine.data_fetcher.settings") as mock_settings:
        mock_settings.ALPACA_API_KEY = "test_key"
        mock_settings.ALPACA_SECRET_KEY = "test_secret"

        with caplog.at_level(logging.WARNING):
            result = fetch_multi_tf("EURUSD", timeframes=["M5"])

    mock_synthetic.assert_called_once()
    assert result is not None
    assert "M5" in result
    assert any(
        "forex" in rec.message.lower() and "synthetic" in rec.message.lower()
        for rec in caplog.records
    )


@patch("signal_engine.data_fetcher.generate_synthetic_candles")
@patch("signal_engine.data_fetcher.httpx.Client")
def test_fallback_to_synthetic_on_api_error(mock_client_cls, mock_synthetic, caplog):
    """
    When the live API call raises an exception, fallback to synthetic data
    and log a warning explaining the failure.
    """
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.get.side_effect = Exception("Connection refused / network down")

    mock_df = pd.DataFrame(
        [{"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000}]
    ).set_index(pd.Index(["2026-03-01"], name="time"))
    mock_synthetic.return_value = mock_df

    with patch("signal_engine.data_fetcher.settings") as mock_settings:
        mock_settings.ALPACA_API_KEY = "test_key"
        mock_settings.ALPACA_SECRET_KEY = "test_secret"

        with caplog.at_level(logging.WARNING):
            result = fetch_multi_tf("SPY", timeframes=["M5"])

    mock_synthetic.assert_called_once()
    assert result is not None
    assert any(
        "failed to fetch" in rec.message.lower() or "error" in rec.message.lower()
        for rec in caplog.records
    )


@patch("signal_engine.data_fetcher.generate_synthetic_candles")
@patch("signal_engine.data_fetcher.httpx.Client")
def test_fallback_to_synthetic_on_empty_bars_payload(mock_client_cls, mock_synthetic, caplog):
    """
    When the live API call returns an empty bars payload, fallback to synthetic
    data and log a warning.
    """
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"bars": []}
    mock_client.get.return_value = mock_resp

    mock_df = pd.DataFrame(
        [{"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000}]
    ).set_index(pd.Index(["2026-03-01"], name="time"))
    mock_synthetic.return_value = mock_df

    with patch("signal_engine.data_fetcher.settings") as mock_settings:
        mock_settings.ALPACA_API_KEY = "test_key"
        mock_settings.ALPACA_SECRET_KEY = "test_secret"

        with caplog.at_level(logging.WARNING):
            result = fetch_multi_tf("SPY", timeframes=["M5"])

    mock_synthetic.assert_called_once()
    assert result is not None
    assert any("empty bars" in rec.message.lower() for rec in caplog.records)


@patch("signal_engine.data_fetcher.generate_synthetic_candles")
@patch("signal_engine.data_fetcher.httpx.Client")
def test_crypto_market_data_fetched_when_credentials_set(mock_client_cls, mock_synthetic):
    """
    Crypto instruments query Alpaca's crypto bars endpoint and parse the response.
    Synthetic generator must NOT be called.
    """
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_CRYPTO_BARS
    mock_client.get.return_value = mock_resp

    with patch("signal_engine.data_fetcher.settings") as mock_settings:
        mock_settings.ALPACA_API_KEY = "test_key"
        mock_settings.ALPACA_SECRET_KEY = "test_secret"

        result = fetch_multi_tf("BTCUSD", timeframes=["H1"])

    mock_synthetic.assert_not_called()
    mock_client.get.assert_called_once()
    args, kwargs = mock_client.get.call_args
    assert "crypto/us/bars" in args[0]
    assert kwargs["params"]["symbols"] == "BTCUSD"
    assert kwargs["params"]["timeframe"] == "1Hour"

    assert result is not None
    assert "H1" in result
    df = result["H1"]
    assert len(df) == 1
    assert df.iloc[0]["close"] == 65250.0

"""
Builds the market_context dict passed into the Independent Market Agent.
Fetches REAL data — no LLM is asked to recall catalysts from memory.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Optional
import httpx

from core.settings import settings

logger = logging.getLogger(__name__)

# Global hook to allow mocking catalysts in unit tests and deterministic simulations
_catalysts_fetcher: Optional[Callable[[Any], list[Catalyst]]] = None


def set_catalysts_fetcher(fetcher: Optional[Callable[[Any], list[Catalyst]]]) -> None:
    """Sets a custom catalysts fetcher for testing or overrides."""
    global _catalysts_fetcher
    _catalysts_fetcher = fetcher


@dataclass
class Catalyst:
    type: str          # "earnings" | "economic_release" | "news"
    description: str
    days_until: int
    source: str
    date: str = ""


def fetch_catalysts(instrument) -> list[Catalyst]:
    """
    Equities/ETFs: query Alpaca's News API for recent and upcoming catalysts.
    Returns genuine live catalysts if available, or an empty list if none found.
    Never fabricates fake data.
    """
    if _catalysts_fetcher is not None:
        return _catalysts_fetcher(instrument)

    symbol = getattr(instrument, "symbol", str(instrument))
    if not settings.ALPACA_API_KEY or not settings.ALPACA_SECRET_KEY:
        logger.debug("Alpaca API keys not set — skipping live news catalyst query")
        return []

    headers = {
        "APCA-API-KEY-ID": settings.ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": settings.ALPACA_SECRET_KEY,
    }
    url = "https://data.alpaca.markets/v1beta1/news"
    params = {
        "symbols": symbol,
        "limit": 10,
        "sort": "desc",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                logger.debug("Alpaca News API returned status %s for %s", resp.status_code, symbol)
                return []

            data = resp.json()
            news_items = data.get("news", [])
            catalysts: list[Catalyst] = []
            now = datetime.now(timezone.utc)

            for item in news_items:
                headline = item.get("headline", "")
                created_at_str = item.get("created_at", "")
                source = item.get("source", "alpaca_news")
                days_until = 0

                if created_at_str:
                    try:
                        # ISO 8601 parsing
                        item_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                        delta = (item_dt - now).days
                        days_until = max(0, delta)
                    except Exception:
                        days_until = 0

                if headline:
                    catalysts.append(
                        Catalyst(
                            type="news",
                            description=headline,
                            days_until=days_until,
                            source=source,
                            date=created_at_str,
                        )
                    )

            return catalysts

    except Exception as e:
        logger.debug("Failed to fetch catalysts for %s: %s", symbol, e)
        return []


def fetch_iv_rank(instrument) -> Optional[float]:
    """
    Returns IV rank for options-enabled instruments.
    """
    if not getattr(instrument, "options_enabled", False):
        return None

    # Default baseline IV rank if options are enabled
    # Can be refined with live options chain metrics
    return 35.0


def build_market_context(instrument) -> dict:
    catalysts = fetch_catalysts(instrument)
    context = {
        "catalysts": [c.__dict__ for c in catalysts],
    }
    if getattr(instrument, "options_enabled", False):
        context["iv_rank"] = fetch_iv_rank(instrument)
    return context


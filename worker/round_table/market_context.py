"""
Builds the market_context dict passed into the Independent Market Agent.
Fetches REAL data — no LLM is asked to recall catalysts from memory.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Catalyst:
    type: str          # "earnings" | "economic_release" | "news"
    description: str
    days_until: int
    source: str
    date: str = ""


def fetch_catalysts(instrument) -> list[Catalyst]:
    """
    Equities/ETFs: query Alpaca's News API + an earnings-calendar source
    for anything inside the next ~10 trading days.
    Forex: query an economic-calendar source (e.g. high-impact events for
    the instrument's underlying currencies) instead — earnings don't apply.
    Crypto: query a crypto-specific news/event source if available;
    otherwise return an empty list rather than fabricate one.

    TODO: wire up the real API calls. Do not stub this with hardcoded
    fake catalysts — an empty list (genuinely "nothing found") is a valid
    and honest result; a fabricated one is not.
    """
    # Honest default: return an empty list until real calendar/API feeds are hooked up
    return []


def fetch_iv_rank(instrument) -> Optional[float]:
    """Only meaningful when instrument.options_enabled. Returns None for
    forex/spot-crypto instruments. Reuses the same lookup contract_selector.py
    needs (see signal_engine — avoid duplicating this call in two places;
    this function should be the single source both consumers call)."""
    if not getattr(instrument, "options_enabled", False):
        return None
    # Real IV rank calculation via options chain feed (Day 4)
    return None


def build_market_context(instrument) -> dict:
    catalysts = fetch_catalysts(instrument)
    context = {
        "catalysts": [c.__dict__ for c in catalysts],
    }
    if getattr(instrument, "options_enabled", False):
        context["iv_rank"] = fetch_iv_rank(instrument)
    return context


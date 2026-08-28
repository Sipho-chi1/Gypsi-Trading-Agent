"""
Thin wrapper around Alpaca's MCP server. All order placement should route
through here rather than a raw SDK call, so the hackathon's MCP requirement
is structural (every real order goes through it), not decorative.
"""
import httpx

from core.settings import settings


class AlpacaMCPClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.ALPACA_MCP_URL

    def place_option_order(self, contract, quantity: int, side: str) -> dict:
        # TODO: call the MCP server's order-placement tool over its
        # protocol (see Alpaca's Trading MCP Server docs). Keeping this as
        # a thin, swappable client means execution.py doesn't need to know
        # MCP wire-format details.
        raise NotImplementedError("Wire up MCP call here (Day 4).")

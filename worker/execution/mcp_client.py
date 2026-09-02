"""
Thin wrapper around Alpaca's MCP server. All order placement should route
through here rather than a raw SDK call, so the hackathon's MCP requirement
is structural (every real order goes through it), not decorative.
"""
import logging
import uuid
import httpx

from core.settings import settings

logger = logging.getLogger(__name__)


class AlpacaMCPError(RuntimeError):
    pass


class AlpacaMCPClient:
    def __init__(self, base_url: str | None = None, timeout: float = 20.0):
        self.base_url = (base_url or settings.ALPACA_MCP_URL).rstrip("/")
        self.timeout = timeout

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Invokes a tool on the MCP server via JSON-RPC 2.0 protocol."""
        req_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.base_url}/jsonrpc", json=payload)
                resp.raise_for_status()
                data = resp.json()

                if "error" in data:
                    raise AlpacaMCPError(f"MCP server error: {data['error']}")

                return data.get("result", {})
        except Exception as e:
            logger.error("MCP tool call '%s' failed: %s", tool_name, e)
            raise AlpacaMCPError(f"Failed to communicate with MCP server at {self.base_url}: {e}") from e

    def place_option_order(self, contract, quantity: int, side: str) -> dict:
        """
        Submits an option order through the Alpaca MCP server.
        """
        symbol = getattr(contract, "symbol", str(contract))
        strike = getattr(contract, "strike", None)
        expiry = getattr(contract, "expiry", None)
        option_type = getattr(contract, "option_type", "call")

        arguments = {
            "symbol": symbol,
            "strike": strike,
            "expiry": expiry,
            "type": option_type,
            "qty": quantity,
            "side": side,
            "order_type": "market",
        }

        return self.call_tool("submit_option_order", arguments)

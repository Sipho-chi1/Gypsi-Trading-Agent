"""
Alpaca Trading MCP Server sidecar.
Exposes JSON-RPC 2.0 / MCP tools for order placement and account reads over Railway private network.
"""
import os
import uuid
import logging
from typing import Any
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp.server")

app = FastAPI(title="Alpaca Trading MCP Server")

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")


def _get_alpaca_headers() -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        "Content-Type": "application/json",
    }


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "submit_option_order":
        symbol = arguments.get("symbol", "")
        qty = arguments.get("qty", 1)
        side = arguments.get("side", "buy")
        order_type = arguments.get("order_type", "market")

        if ALPACA_API_KEY and ALPACA_SECRET_KEY:
            url = f"{ALPACA_BASE_URL}/v2/orders"
            payload = {
                "symbol": symbol,
                "qty": str(qty),
                "side": side,
                "type": order_type,
                "time_in_force": "day",
            }
            try:
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(url, headers=_get_alpaca_headers(), json=payload)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as e:
                logger.error("Alpaca API order submission failed: %s", e)
                raise RuntimeError(f"Alpaca API order submission failed: {e}") from e

        # Mock / paper response if keys are not present
        return {
            "id": str(uuid.uuid4()),
            "client_order_id": str(uuid.uuid4()),
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": order_type,
            "status": "accepted",
            "filled_qty": "0",
        }

    elif name == "get_account":
        if ALPACA_API_KEY and ALPACA_SECRET_KEY:
            url = f"{ALPACA_BASE_URL}/v2/account"
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, headers=_get_alpaca_headers())
                resp.raise_for_status()
                return resp.json()
        return {
            "id": "mock-account-id",
            "equity": "100000.00",
            "cash": "100000.00",
            "status": "ACTIVE",
        }

    else:
        raise ValueError(f"Unknown tool name: {name}")


@app.post("/jsonrpc")
async def handle_jsonrpc(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
        )

    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {})

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        try:
            result = execute_tool(tool_name, tool_args)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as e:
            logger.error("Error executing tool %s: %s", tool_name, e)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)},
            }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "submit_option_order",
                        "description": "Submit an option order to Alpaca",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "symbol": {"type": "string"},
                                "qty": {"type": "integer"},
                                "side": {"type": "string"},
                                "order_type": {"type": "string"},
                            },
                            "required": ["symbol", "qty", "side"],
                        },
                    },
                    {
                        "name": "get_account",
                        "description": "Get account details and live equity",
                        "inputSchema": {"type": "object"},
                    },
                ]
            },
        }
    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not found"},
        }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "alpaca-mcp-sidecar"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)

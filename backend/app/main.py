"""FastAPI entrypoint — serves trade/verdict history to the Vercel-hosted
Next.js dashboard. Never talks to Alpaca or the LLM providers directly;
that's the worker's job. This service only reads from Postgres."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import trades, round_table, health

app = FastAPI(title="Gypsi API")

# TODO: restrict to the deployed Vercel origin before submission.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(trades.router, prefix="/trades", tags=["trades"])
app.include_router(round_table.router, prefix="/round-table", tags=["round-table"])


@app.get("/")
async def root():
    return {
        "name": "Gypsi API",
        "status": "running",
        "docs_url": "/docs",
        "endpoints": [
            "/health",
            "/trades",
            "/trades/performance",
            "/round-table/recent",
        ],
    }


"""FastAPI entrypoint — serves trade/verdict history to the Vercel-hosted
Next.js dashboard. Never talks to Alpaca or the LLM providers directly;
that's the worker's job. This service only reads from Postgres."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import trades, round_table, health
from app.core.config import settings

app = FastAPI(title="Gypsi API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
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


"""Centralised env-driven settings for the worker."""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


load_dotenv()

def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass
class Settings:
    ALPACA_API_KEY: str = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY: str = os.getenv("ALPACA_SECRET_KEY", "")
    ALPACA_BASE_URL: str = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://gypsi:gypsi@localhost:5432/gypsi")
    ALPACA_MCP_URL: str = os.getenv("ALPACA_MCP_URL", "http://localhost:8080")

    POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))
    WATCHLIST: list[str] = field(default_factory=lambda: _split_csv(os.getenv("WATCHLIST", "SPY,QQQ")))


settings = Settings()

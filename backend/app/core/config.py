from dataclasses import dataclass, field
import os
from dotenv import load_dotenv, find_dotenv

# Load .env from project root or environment
load_dotenv(find_dotenv(usecwd=True))


def _split_cors_origins(raw: str) -> list[str]:
    if not raw or raw.strip() == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


@dataclass
class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://gypsi:gypsi@localhost:5432/gypsi")
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    CORS_ORIGINS: list[str] = field(
        default_factory=lambda: _split_cors_origins(
            os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,https://gypsi.vercel.app,*")
        )
    )


settings = Settings()

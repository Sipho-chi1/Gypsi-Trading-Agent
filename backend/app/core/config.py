import os
from dataclasses import dataclass
from dotenv import load_dotenv, find_dotenv

# Load .env from project root or environment
load_dotenv(find_dotenv(usecwd=True))


@dataclass
class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://gypsi:gypsi@localhost:5432/gypsi")
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))


settings = Settings()

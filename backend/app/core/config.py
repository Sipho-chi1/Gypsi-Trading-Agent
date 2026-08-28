import os
from dataclasses import dataclass


@dataclass
class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://gypsi:gypsi@localhost:5432/gypsi")


settings = Settings()

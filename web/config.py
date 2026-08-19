from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    mongo_uri: str = os.getenv("FANTASTAT_MONGO_URI", "mongodb://localhost:27017")
    mongo_database: str = os.getenv("FANTASTAT_MONGO_DATABASE", "fantastat")


settings = Settings()

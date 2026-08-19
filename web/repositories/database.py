from __future__ import annotations

from pymongo import MongoClient
from config import settings


class Database:
    def __init__(self, uri: str | None = None, database: str | None = None):
        self.client = MongoClient(uri or settings.mongo_uri)
        self.db = self.client[database or settings.mongo_database]

    def collection(self, name: str):
        return self.db[name]

from __future__ import annotations

from pymongo import MongoClient
from pymongo.database import Database as MongoDatabase

from config import settings


class Database:
    """Small MongoDB connection wrapper.

    Keep this boring. It centralises the local Mongo connection and avoids
    creating ad-hoc clients in routes or services.
    """

    def __init__(self, uri: str | None = None, database: str | None = None):
        self.uri = uri or settings.mongo_uri
        self.database_name = database or settings.mongo_database
        self.client = MongoClient(self.uri)
        self.db: MongoDatabase = self.client[self.database_name]

    def collection(self, name: str):
        return self.db[name]

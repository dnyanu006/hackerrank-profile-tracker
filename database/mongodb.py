"""MongoDB connection and persistence helpers."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import certifi
from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConfigurationError, OperationFailure, PyMongoError, ServerSelectionTimeoutError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _validate_mongodb_uri(uri: str) -> None:
    """Verify the URI format and required settings without exposing secrets."""
    if not uri:
        raise RuntimeError("MONGODB_URI is missing. Copy .env.example to .env and configure it.")
    if not uri.startswith(("mongodb://", "mongodb+srv://")):
        raise RuntimeError("MONGODB_URI must start with mongodb:// or mongodb+srv://.")

    parsed = urlparse(uri)
    if not parsed.username:
        raise RuntimeError(
            "MONGODB_URI is missing the MongoDB Atlas username. Use the database user from "
            "Security > Database Access and keep the database user name in .env."
        )
    if not parsed.password:
        raise RuntimeError(
            "MONGODB_URI is missing the password for the Atlas database user. Reset or update the "
            "password in MongoDB Atlas and save the new value locally in .env."
        )


def get_database() -> tuple[MongoClient, Database]:
    """Connect to MongoDB, ping it, and return the client and database."""
    uri = os.getenv("MONGODB_URI", "").strip()
    database_name = os.getenv("MONGODB_DATABASE", "hackerrank_tracker").strip()
    _validate_mongodb_uri(uri)
    if not database_name:
        raise RuntimeError("MONGODB_DATABASE must not be empty.")

    try:
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            tls=True,
            tlsCAFile=certifi.where(),
        )
    except ConfigurationError as exc:
        raise RuntimeError(
            "MONGODB_URI is not a valid MongoDB connection string. Check the Atlas driver URI "
            "and URL-encode special characters in the password locally."
        ) from exc
    try:
        client.admin.command("ping")
    except OperationFailure as exc:
        client.close()
        if exc.code == 18 or "Authentication failed" in str(exc):
            raise RuntimeError(
                "MongoDB authentication failed. In MongoDB Atlas, open "
                "Security > Database Access, edit the database user, reset its password, "
                "and update MONGODB_URI locally in .env. Do not share the password."
            ) from exc
        raise RuntimeError("MongoDB rejected the connection.") from exc
    except ServerSelectionTimeoutError as exc:
        client.close()
        raise RuntimeError(
            "MongoDB server selection timed out. Check the Atlas IP allowlist, "
            "cluster status, and network connection."
        ) from exc
    except PyMongoError as exc:
        client.close()
        raise RuntimeError("Could not connect to MongoDB.") from exc
    return client, client[database_name]


def create_indexes(database: Database) -> None:
    """Create idempotent indexes used by sync operations."""
    database.sync_logs.create_index([("username", ASCENDING), ("started_at", DESCENDING)])


def upsert_document(
    collection: Collection,
    username: str,
    document: dict[str, Any],
    *,
    collected_at: datetime | None = None,
):
    """Replace the current snapshot for a username without creating duplicates."""
    timestamp = collected_at or datetime.now(timezone.utc)
    payload = {
        **document,
        "username": username,
        "collected_at": timestamp,
        "updated_at": datetime.now(timezone.utc),
    }
    collection.create_index("username", unique=True)
    return collection.replace_one({"username": username}, payload, upsert=True)


def record_sync_log(
    database: Database,
    username: str,
    *,
    started_at: datetime,
    status: str,
    sections: dict[str, str],
    error: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "username": username,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc),
        "status": status,
        "sections": sections,
    }
    if error:
        payload["error"] = error
    database.sync_logs.insert_one(payload)

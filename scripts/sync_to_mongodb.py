"""Collect a public HackerRank profile and synchronize it to MongoDB."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.mongodb import create_indexes, get_database, record_sync_log, upsert_document
from scripts.hackerrank_collector import collect_hackerrank_profile, validate_username

LOGGER = logging.getLogger(__name__)


def _availability(value: object) -> str:
    if isinstance(value, dict):
        return "collected" if value else "not available publicly"
    if isinstance(value, list):
        return "collected" if value else "not available publicly"
    return "collected" if value is not None else "not available publicly"


def sync_username(username: str) -> None:
    username = validate_username(username)
    started_at = datetime.now(timezone.utc)
    client = None
    try:
        print(f"Collecting public HackerRank data for {username}...")
        collected = collect_hackerrank_profile(username)
        client, database = get_database()
        create_indexes(database)
        collected_at = collected["collected_at"]
        results = {
            "profile": upsert_document(
                database.hackerrank_profiles, username, collected["profile"], collected_at=collected_at
            )
        }
        if collected["statistics"]:
            results["statistics"] = upsert_document(
                database.hackerrank_statistics, username, collected["statistics"], collected_at=collected_at
            )
        if collected["badges"]:
            results["badges"] = upsert_document(
                database.hackerrank_badges,
                username,
                {"badges": collected["badges"]},
                collected_at=collected_at,
            )
        if collected["contests"]:
            results["contests"] = upsert_document(
                database.hackerrank_contests,
                username,
                {"contests": collected["contests"]},
                collected_at=collected_at,
            )
        if collected["recent_activity"]:
            results["recent_activity"] = upsert_document(
                database.hackerrank_submissions,
                username,
                {"recent_activity": collected["recent_activity"]},
                collected_at=collected_at,
            )
        sections = {
            "profile": _availability(collected["profile"]),
            "statistics": _availability(collected["statistics"]),
            "badges": _availability(collected["badges"]),
            "contests": _availability(collected["contests"]),
            "recent_activity": _availability(collected["recent_activity"]),
        }
        record_sync_log(database, username, started_at=started_at, status="successful", sections=sections)
        print("\nHackerRank Profile Sync")
        print("-----------------------")
        print(f"Username: {username}")
        for name, status in sections.items():
            print(f"{name.replace('_', ' ').title()}: {status}")
        print("MongoDB: connected")
        print(f"Profile record: {'inserted' if results['profile'].upserted_id else 'updated'}")
        print("Sync: successful")
    except Exception as exc:
        if client is not None:
            try:
                record_sync_log(
                    database,
                    username,
                    started_at=started_at,
                    status="failed",
                    sections={},
                    error=str(exc),
                )
            except Exception:
                LOGGER.exception("Could not record failed sync")
        print(f"Sync failed: {exc}", file=sys.stderr)
        raise
    finally:
        if client is not None:
            client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync a public HackerRank profile to MongoDB.")
    parser.add_argument("username", nargs="?", help="HackerRank username")
    args = parser.parse_args()
    username = args.username or input("HackerRank username: ").strip()
    try:
        sync_username(username)
    except (RuntimeError, ValueError, OSError):
        return 1
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())

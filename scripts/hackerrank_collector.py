"""Collect information exposed by a public HackerRank profile page."""

from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

LOGGER = logging.getLogger(__name__)
PROFILE_URL_TEMPLATE = "https://www.hackerrank.com/profile/{username}"
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
DEFAULT_TIMEOUT = 15


def validate_username(username: str) -> str:
    """Validate and normalize a HackerRank username."""
    normalized = username.strip()
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Username must be 1-100 characters and contain only letters, "
            "numbers, '.', '_' or '-'."
        )
    return normalized


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _load_embedded_data(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Load JSON data the public page explicitly embeds in its HTML."""
    documents: list[dict[str, Any]] = []
    for script in soup.find_all("script"):
        text = script.string or script.get_text()
        if not text.strip():
            continue
        script_type = (script.get("type") or "").lower()
        script_id = (script.get("id") or "").lower()
        if script_type == "application/ld+json" or script_id == "__next_data__":
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                documents.append(parsed)
            elif isinstance(parsed, list):
                documents.extend(item for item in parsed if isinstance(item, dict))
    return documents


def _find_value(documents: list[dict[str, Any]], names: set[str]) -> Any:
    lowered_names = {name.lower() for name in names}
    for document in documents:
        for item in _walk_dicts(document):
            for key, value in item.items():
                if key.lower() in lowered_names and value not in (None, "", [], {}):
                    return value
    return None


def _find_list(documents: list[dict[str, Any]], names: set[str]) -> list[Any]:
    value = _find_value(documents, names)
    if isinstance(value, list):
        return value
    return []


def _meta_content(soup: BeautifulSoup, *names: str) -> str | None:
    for name in names:
        tag = soup.find("meta", attrs={"name": name}) or soup.find(
            "meta", attrs={"property": name}
        )
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def _page_context(html: str) -> tuple[BeautifulSoup, list[dict[str, Any]]]:
    soup = BeautifulSoup(html, "html.parser")
    return soup, _load_embedded_data(soup)


def _request_profile(username: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[str, str]:
    url = PROFILE_URL_TEMPLATE.format(username=quote(username, safe=""))
    headers = {"User-Agent": "hackerrank-profile-tracker/1.0 (public profile reader)"}
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(f"HackerRank returned HTTP {exc.response.status_code}.") from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not fetch the public profile: {exc}") from exc
    return url, response.text


def get_public_profile(username: str, *, html: str | None = None) -> dict[str, Any]:
    """Return public profile fields found in page metadata or embedded JSON."""
    username = validate_username(username)
    profile_url = PROFILE_URL_TEMPLATE.format(username=quote(username, safe=""))
    if html is None:
        profile_url, html = _request_profile(username)

    soup, documents = _page_context(html)
    full_name = _find_value(documents, {"name", "fullName", "displayName"})
    if not isinstance(full_name, str):
        full_name = _meta_content(soup, "author")

    return {
        "username": username,
        "profile_url": profile_url,
        "display_name": full_name,
        "avatar_url": _find_value(documents, {"image", "avatar", "avatarUrl", "profileImage"})
        or _meta_content(soup, "og:image"),
        "bio": _find_value(documents, {"bio", "about", "description"})
        or _meta_content(soup, "description", "og:description"),
        "location": _find_value(documents, {"location", "addressLocality"}),
        "education": _find_list(documents, {"education", "educations"}),
        "work_experience": _find_list(documents, {"workExperience", "experience", "work"}),
        "skills": _find_list(documents, {"skills", "skill"}),
    }


def get_statistics(username: str, *, html: str | None = None) -> dict[str, Any]:
    """Return statistics only when present in public embedded page data."""
    username = validate_username(username)
    if html is None:
        _, html = _request_profile(username)
    _, documents = _page_context(html)
    field_names = {
        "solved_challenges": {"solvedChallenges", "solved_challenges", "challengesSolved"},
        "scores": {"score", "scores", "points"},
        "rank": {"rank", "ranking", "globalRank"},
        "domains": {"domains", "categories", "tracks"},
        "difficulty_statistics": {"difficultyStatistics", "difficultyStats"},
    }
    statistics = {key: _find_value(documents, names) for key, names in field_names.items()}
    return {key: value for key, value in statistics.items() if value is not None}


def get_badges(username: str, *, html: str | None = None) -> list[Any]:
    """Return publicly embedded badges, if HackerRank provides them in the page."""
    username = validate_username(username)
    if html is None:
        _, html = _request_profile(username)
    _, documents = _page_context(html)
    return _find_list(documents, {"badges", "badgeList"})


def get_contests(username: str, *, html: str | None = None) -> list[Any]:
    """Return publicly embedded contest data, if available."""
    username = validate_username(username)
    if html is None:
        _, html = _request_profile(username)
    _, documents = _page_context(html)
    return _find_list(documents, {"contests", "contestHistory", "contest_history"})


def get_recent_activity(username: str, *, html: str | None = None) -> list[Any]:
    """Return publicly embedded activity data, if available."""
    username = validate_username(username)
    if html is None:
        _, html = _request_profile(username)
    _, documents = _page_context(html)
    return _find_list(documents, {"recentActivity", "activity", "submissions"})


def collect_hackerrank_profile(username: str) -> dict[str, Any]:
    """Fetch once and collect all reliably parseable public profile data."""
    username = validate_username(username)
    profile_url, html = _request_profile(username)
    LOGGER.info("Fetched public profile page for %s", username)
    profile = get_public_profile(username, html=html)
    profile["profile_url"] = profile_url
    statistics = get_statistics(username, html=html)
    badges = get_badges(username, html=html)
    contests = get_contests(username, html=html)
    recent_activity = get_recent_activity(username, html=html)
    return {
        "profile": profile,
        "statistics": statistics,
        "badges": badges,
        "contests": contests,
        "recent_activity": recent_activity,
        "collected_at": datetime.now(timezone.utc),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read a public HackerRank profile.")
    parser.add_argument("username", nargs="?", help="HackerRank username")
    args = parser.parse_args()
    username = args.username or input("HackerRank username: ").strip()
    try:
        collected = collect_hackerrank_profile(username)
    except (RuntimeError, ValueError) as exc:
        print(f"Collection failed: {exc}")
        return 1
    print(json.dumps(collected, indent=2, default=str))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())

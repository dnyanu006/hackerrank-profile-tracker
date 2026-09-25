"""Collect real public information exposed by a HackerRank profile page."""

from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import requests
from bs4 import BeautifulSoup

LOGGER = logging.getLogger(__name__)
PROFILE_URL_TEMPLATE = "https://www.hackerrank.com/{username}"
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
DEFAULT_TIMEOUT = 15


def _guess_username_from_url(raw_url: str) -> str | None:
    """Resolve a public HackerRank profile URL into a username."""
    text = (raw_url or "").strip()
    if not text:
        return None
    candidate = text
    if not candidate.startswith("http://") and not candidate.startswith("https://"):
        candidate = "https://" + candidate if "hackerrank.com" in candidate else candidate
    if "hackerrank.com" not in candidate:
        return None

    parsed = urlparse(candidate)
    path = parsed.path.strip("/")
    if not path:
        return None
    segments = [segment for segment in path.split("/") if segment]
    for marker in ("profile", "users", "u"):
        if marker in segments:
            idx = segments.index(marker)
            if idx + 1 < len(segments) and segments[idx + 1]:
                username = segments[idx + 1]
                if USERNAME_PATTERN.fullmatch(username):
                    return username
    if len(segments) == 1 and USERNAME_PATTERN.fullmatch(segments[0]):
        return segments[0]
    if parsed.query:
        params = parse_qs(parsed.query)
        username = params.get("username", [None])[0]
        if username and USERNAME_PATTERN.fullmatch(username):
            return username
    return None


def validate_username(username: str) -> str:
    """Validate and normalize either a HackerRank username or public profile URL."""
    raw = (username or "").strip()
    if not raw:
        raise ValueError("Please enter a valid HackerRank username or profile URL.")

    url_username = _guess_username_from_url(raw)
    if url_username:
        return url_username

    normalized = raw.strip("/")
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError("Please enter a valid HackerRank username or profile URL.")
    return normalized


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _json_documents_from_script(script_text: str) -> list[dict[str, Any]]:
    """Parse the specific JSON objects embedded in public page scripts."""
    documents: list[dict[str, Any]] = []
    try:
        parsed = json.loads(script_text)
    except json.JSONDecodeError:
        return documents
    if isinstance(parsed, dict):
        documents.append(parsed)
    elif isinstance(parsed, list):
        documents.extend(item for item in parsed if isinstance(item, dict))
    return documents


def _load_embedded_data(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Load only JSON data embedded in script tags or metadata containers."""
    documents: list[dict[str, Any]] = []
    for script in soup.find_all("script"):
        text = script.string or script.get_text("", strip=True)
        if not text:
            continue
        script_type = (script.get("type") or "").lower()
        script_id = (script.get("id") or "").lower()
        script_kind = script_type or script_id
        if script_kind in {"application/ld+json", "__next_data__", "application/json"}:
            documents.extend(_json_documents_from_script(text))
    for script in soup.find_all("script", type=True):
        if "application/ld+json" in (script.get("type") or "").lower():
            text = script.string or script.get_text("", strip=True)
            documents.extend(_json_documents_from_script(text))
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
            value = str(tag["content"]).strip()
            if value:
                return value
    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical and canonical.get("href"):
        href = str(canonical["href"]).strip()
        if href:
            return href
    return None


def _page_context(html: str) -> tuple[BeautifulSoup, list[dict[str, Any]]]:
    soup = BeautifulSoup(html, "html.parser")
    return soup, _load_embedded_data(soup)


def _request_profile(username: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[str, str]:
    profile_url = PROFILE_URL_TEMPLATE.format(username=quote(username, safe=""))
    headers = {"User-Agent": "hackerrank-profile-tracker/1.0 (public profile reader)"}
    try:
        response = requests.get(profile_url, headers=headers, timeout=timeout)
        if response.status_code == 404:
            raise RuntimeError("HackerRank profile could not be found.")
        response.raise_for_status()
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            raise RuntimeError("HackerRank profile could not be found.") from exc
        raise RuntimeError("Unable to fetch the HackerRank profile right now. Please try again.") from exc
    except requests.RequestException as exc:
        raise RuntimeError("Unable to fetch the HackerRank profile right now. Please try again.") from exc
    return profile_url, response.text


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    if isinstance(value, (dict, list)):
        return value if value else None
    return value


def _value_or_not_available(value: Any) -> Any:
    return _clean_value(value)


def _is_generic_hackerrank_text(value: str) -> bool:
    """Reject non-user platform text such as marketing copy and site descriptions."""
    lowered = re.sub(r"\s+", " ", value.strip().lower())
    if not lowered:
        return True

    generic_markers = (
        "join over",
        "millions of developers",
        "solve code challenges on hackerrank",
        "prepare for programming interviews",
        "one of the best ways",
        "practice coding",
        "learn to code",
        "code challenges",
        "developer skills",
        "programming interviews",
        "algorithmic thinking",
        "developer skills platform",
    )
    if any(marker in lowered for marker in generic_markers):
        return True
    if "hackerrank" in lowered and ("join " in lowered or "prepare" in lowered or "code challenges" in lowered):
        return True
    return False


def _extract_profile_bio(documents: list[dict[str, Any]], soup: BeautifulSoup) -> str | None:
    """Only keep a bio when it clearly belongs to the user's public profile."""
    candidates: list[str] = []
    for names in ({"bio", "about", "summary", "profileBio"}, {"description", "profileDescription"}, {"userBio", "biography"}):
        value = _find_value(documents, names)
        if isinstance(value, str):
            candidates.append(value)

    meta_value = _meta_content(soup, "description", "og:description")
    if meta_value:
        candidates.append(meta_value)

    for candidate in candidates:
        cleaned = _clean_value(candidate)
        if not isinstance(cleaned, str):
            continue
        if not cleaned.strip():
            continue
        if _is_generic_hackerrank_text(cleaned):
            continue
        if "hackerrank" in cleaned.lower() and any(
            phrase in cleaned.lower() for phrase in ("join over", "code challenges", "programming interviews", "prepare for")
        ):
            continue
        return cleaned

    return "Not publicly available"


def get_public_profile(username: str, *, html: str | None = None) -> dict[str, Any]:
    """Return public profile data only when it is explicitly present on the page."""
    username = validate_username(username)
    profile_url = PROFILE_URL_TEMPLATE.format(username=quote(username, safe=""))
    if html is None:
        profile_url, html = _request_profile(username)

    soup, documents = _page_context(html)
    full_name = _find_value(documents, {"name", "fullName", "displayName"})
    if not isinstance(full_name, str):
        full_name = _meta_content(soup, "author", "og:title", "twitter:title")
    if isinstance(full_name, str):
        lowered = full_name.strip().lower()
        if "hackerrank" in lowered and (
            "programming problems" in lowered or "competitions" in lowered or "developer skills" in lowered or "login" in lowered
        ):
            full_name = None

    profile = {
        "username": username,
        "profile_url": profile_url,
        "display_name": _value_or_not_available(full_name),
        "location": _value_or_not_available(_find_value(documents, {"location", "addressLocality", "city"})),
        "institution": _value_or_not_available(_find_value(documents, {"school", "institution", "organization", "university"})),
        "professional_status": _value_or_not_available(_find_value(documents, {"title", "role", "professionalStatus", "headline"})),
        "bio": _extract_profile_bio(documents, soup),
        "member_since": _value_or_not_available(_find_value(documents, {"memberSince", "joinedAt", "createdAt", "registeredAt"})),
        "avatar_url": _value_or_not_available(_find_value(documents, {"image", "avatar", "avatarUrl", "profileImage"}) or _meta_content(soup, "og:image", "twitter:image")),
    }
    if profile["display_name"] is None:
        profile["display_name"] = None
    return profile


def get_statistics(username: str, *, html: str | None = None) -> dict[str, Any]:
    """Return real numeric statistics only when explicitly exposed on the page."""
    username = validate_username(username)
    if html is None:
        _, html = _request_profile(username)
    _, documents = _page_context(html)
    field_names = {
        "problems_solved": {"solvedChallenges", "solved_challenges", "problemsSolved", "challengesSolved"},
        "badges": {"badges", "badgesCount", "badgeCount", "numBadges"},
        "certificates": {"certificates", "certificatesCount", "certificateCount", "numCertificates"},
        "skills": {"skills", "skill"},
        "domains": {"domains", "categories", "tracks"},
        "contest_rating": {"contestRating", "rating", "contest_rating"},
        "contest_rank": {"contestRank", "rank", "globalRank"},
    }
    statistics = {key: _find_value(documents, names) for key, names in field_names.items()}
    return {key: value for key, value in statistics.items() if value is not None}


def get_badges(username: str, *, html: str | None = None) -> list[Any]:
    """Return badge records only when HackerRank exposes them publicly."""
    username = validate_username(username)
    if html is None:
        _, html = _request_profile(username)
    _, documents = _page_context(html)
    badges = _find_list(documents, {"badges", "badgeList", "badgesEarned"})
    if isinstance(badges, list):
        return badges
    return []


def get_contests(username: str, *, html: str | None = None) -> list[Any]:
    """Return contest records only when HackerRank exposes them publicly."""
    username = validate_username(username)
    if html is None:
        _, html = _request_profile(username)
    _, documents = _page_context(html)
    contests = _find_list(documents, {"contests", "contestHistory", "contest_history"})
    if isinstance(contests, list):
        return contests
    return []


def get_recent_activity(username: str, *, html: str | None = None) -> list[Any]:
    """Return recent public activity data only when present."""
    username = validate_username(username)
    if html is None:
        _, html = _request_profile(username)
    _, documents = _page_context(html)
    activity = _find_list(documents, {"recentActivity", "activity", "submissions", "recent_activity"})
    if isinstance(activity, list):
        return activity
    return []


def collect_hackerrank_profile(username: str) -> dict[str, Any]:
    """Fetch once and collect all legitimately public profile sections."""
    username = validate_username(username)
    profile_url, html = _request_profile(username)
    LOGGER.info("Fetched public profile page for %s", username)
    profile = get_public_profile(username, html=html)
    profile["profile_url"] = profile_url
    return {
        "profile": profile,
        "statistics": get_statistics(username, html=html),
        "badges": get_badges(username, html=html),
        "contests": get_contests(username, html=html),
        "recent_activity": get_recent_activity(username, html=html),
        "collected_at": datetime.now(timezone.utc),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read a public HackerRank profile.")
    parser.add_argument("username", nargs="?", help="HackerRank username or public profile URL")
    args = parser.parse_args()
    username = args.username or input("HackerRank username or profile URL: ").strip()
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

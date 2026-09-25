from __future__ import annotations

import datetime as dt
from typing import Any

import streamlit as st

from database.mongodb import get_database, upsert_document
from scripts.hackerrank_collector import collect_hackerrank_profile, validate_username

st.set_page_config(page_title="HackerRank Profile Tracker & Analyzer", page_icon="💻", layout="wide")


def _display_value(value: Any, *, fallback: str = "Not publicly available") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed if trimmed else fallback
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else fallback
    if isinstance(value, dict):
        return str(value) if value else fallback
    return str(value)


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _build_metrics(profile: dict[str, Any], statistics: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = []
    metrics.append({"label": "Username", "value": _display_value(profile.get("username"), fallback="Not publicly available")})
    metrics.append({"label": "Problems Solved", "value": _display_value(statistics.get("problems_solved"), fallback="Not publicly available")})
    metrics.append({"label": "Badges", "value": _display_value(statistics.get("badges"), fallback="Not publicly available")})
    metrics.append({"label": "Contest Rating", "value": _display_value(statistics.get("contest_rating"), fallback="Not publicly available")})
    metrics.append({"label": "Contest Rank", "value": _display_value(statistics.get("contest_rank"), fallback="Not publicly available")})
    return metrics


def _describe_recent_activity(activity: Any) -> list[dict[str, str]]:
    if not isinstance(activity, list):
        return []
    cleaned: list[dict[str, str]] = []
    for item in activity[:8]:
        if not isinstance(item, dict):
            continue
        cleaned.append(
            {
                "challenge": _display_value(item.get("challenge") or item.get("problem") or item.get("name"), fallback="Not publicly available"),
                "action": _display_value(item.get("action") or item.get("type") or item.get("event"), fallback="Not publicly available"),
                "date": _display_value(item.get("date") or item.get("timestamp") or item.get("createdAt"), fallback="Not publicly available"),
                "contest": _display_value(item.get("contest") or item.get("contest_name"), fallback="Not publicly available"),
            }
        )
    return cleaned


def _normalize_badges(badges: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for badge in _safe_list(badges):
        if not isinstance(badge, dict):
            continue
        items.append(
            {
                "name": _display_value(badge.get("name") or badge.get("title"), fallback="Not publicly available"),
                "category": _display_value(badge.get("category") or badge.get("type"), fallback="Not publicly available"),
                "level": _display_value(badge.get("level"), fallback="Not publicly available"),
                "earned": _display_value(badge.get("earnedAt") or badge.get("date") or badge.get("awardedAt"), fallback="Not publicly available"),
            }
        )
    return items


def _normalize_skills(skills: Any) -> list[str]:
    if not isinstance(skills, list):
        return []
    tags: list[str] = []
    for skill in skills:
        if isinstance(skill, dict):
            label = skill.get("name") or skill.get("skill") or skill.get("title")
            if label:
                tags.append(str(label))
        elif isinstance(skill, str):
            label = skill.strip()
            if label:
                tags.append(label)
    return tags


def _normalize_contests(contests: Any) -> list[dict[str, str]]:
    data: list[dict[str, str]] = []
    for contest in _safe_list(contests):
        if not isinstance(contest, dict):
            continue
        data.append(
            {
                "name": _display_value(contest.get("name") or contest.get("contestName") or contest.get("title"), fallback="Not publicly available"),
                "rating": _display_value(contest.get("rating") or contest.get("score") or contest.get("contestRating"), fallback="Not publicly available"),
                "rank": _display_value(contest.get("rank") or contest.get("contestRank"), fallback="Not publicly available"),
                "date": _display_value(contest.get("date") or contest.get("contestDate") or contest.get("createdAt"), fallback="Not publicly available"),
                "participation": _display_value(contest.get("participation") or contest.get("submissions") or contest.get("participated"), fallback="Not publicly available"),
            }
        )
    return data


def _empty_state_message(message: str) -> None:
    st.info(message)


def _render_profile_card(label: str, value: Any) -> None:
    st.markdown(f"**{label}:** { _display_value(value) }")


def _save_to_mongodb(profile: dict[str, Any], collected: dict[str, Any]) -> tuple[bool, str]:
    try:
        client, database = get_database()
    except RuntimeError as exc:
        return False, str(exc)
    try:
        upsert_document(database.hackerrank_profiles, profile.get("username", "unknown"), profile)
        if collected.get("statistics"):
            upsert_document(database.hackerrank_statistics, profile.get("username", "unknown"), collected["statistics"])
        if collected.get("badges"):
            upsert_document(database.hackerrank_badges, profile.get("username", "unknown"), {"badges": collected["badges"]})
        if collected.get("contests"):
            upsert_document(database.hackerrank_contests, profile.get("username", "unknown"), {"contests": collected["contests"]})
        if collected.get("recent_activity"):
            upsert_document(database.hackerrank_submissions, profile.get("username", "unknown"), {"recent_activity": collected["recent_activity"]})
        return True, "Success"
    except Exception:
        return False, "Failed"
    finally:
        client.close()


def main() -> None:
    st.title("HackerRank Profile Tracker & Analyzer")
    st.caption("Analyze publicly available HackerRank profile information")

    with st.form("profile_form", clear_on_submit=False):
        input_value = st.text_input("Enter HackerRank Username or Profile URL", placeholder="dnyaneshwariphal or https://www.hackerrank.com/dnyaneshwariphal")
        submitted = st.form_submit_button("Analyze Profile")

    if not submitted:
        st.info("Enter a valid HackerRank username or public profile URL to begin.")
        return

    user_input = (input_value or "").strip()
    if not user_input:
        st.error("Please enter a valid HackerRank username or profile URL.")
        return

    username = ""
    try:
        username = validate_username(user_input)
    except ValueError:
        st.error("Please enter a valid HackerRank username or profile URL.")
        return

    try:
        collected = collect_hackerrank_profile(username)
    except RuntimeError as exc:
        st.error(str(exc))
        return
    except Exception:
        st.error("Unable to fetch the HackerRank profile right now. Please try again.")
        return

    profile = collected.get("profile", {})
    statistics = collected.get("statistics", {})
    badges = _normalize_badges(collected.get("badges", []))
    contests = _normalize_contests(collected.get("contests", []))
    activity = _describe_recent_activity(collected.get("recent_activity", []))

    st.subheader("Profile Overview")
    metric_cols = st.columns(5)
    metrics = _build_metrics(profile, statistics)
    for col, metric in zip(metric_cols, metrics):
        with col:
            st.metric(metric["label"], metric["value"])

    profile_cols = st.columns(2)
    with profile_cols[0]:
        st.markdown("### Profile Details")
        _render_profile_card("Username", profile.get("username"))
        _render_profile_card("Display Name", profile.get("display_name"))
        _render_profile_card("Location", profile.get("location"))
        _render_profile_card("Institution", profile.get("institution"))
        _render_profile_card("Professional Status", profile.get("professional_status"))
        _render_profile_card("Profile URL", profile.get("profile_url"))
        _render_profile_card("Bio", profile.get("bio"))
        _render_profile_card("Member/Join Information", profile.get("member_since"))

    with profile_cols[1]:
        st.markdown("### Coding Statistics")
        stat_items = {
            "Problems Solved": statistics.get("problems_solved"),
            "Badges": statistics.get("badges"),
            "Certificates": statistics.get("certificates"),
            "Skills": statistics.get("skills"),
            "Domains": statistics.get("domains"),
            "Contest Rating": statistics.get("contest_rating"),
            "Contest Rank": statistics.get("contest_rank"),
        }
        for label, value in stat_items.items():
            if value is None:
                st.write(f"{label}: Not publicly available")
            elif isinstance(value, list):
                st.write(f"{label}: {', '.join(str(item) for item in value) if value else 'Not publicly available'}")
            else:
                st.write(f"{label}: {value}")

    st.markdown("### Skills & Domains")
    skill_list = _normalize_skills(statistics.get("skills")) or _normalize_skills(profile.get("skills"))
    if skill_list:
        st.write(" ".join(f"<span style='background:#E6F4FF;padding:6px 10px;border-radius:999px;display:inline-block;margin:4px;'>{skill}</span>" for skill in skill_list), unsafe_allow_html=True)
    else:
        _empty_state_message("No publicly available skill or domain information found.")

    st.markdown("### Badges & Achievements")
    if badges:
        badge_cols = st.columns(3)
        for idx, badge in enumerate(badges[:6]):
            with badge_cols[idx % 3]:
                st.markdown(f"#### {badge['name']}")
                st.write(f"Category: {badge['category']}")
                st.write(f"Level: {badge['level']}")
                st.write(f"Earned: {badge['earned']}")
    else:
        _empty_state_message("No publicly available badges")

    st.markdown("### Contest Performance")
    if contests:
        st.dataframe(contests, use_container_width=True)
        numeric_ratings = []
        for contest in contests:
            if not isinstance(contest, dict):
                continue
            value = contest.get("rating") or contest.get("score") or contest.get("contestRating")
            if isinstance(value, (int, float)):
                numeric_ratings.append(float(value))
            elif isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    try:
                        numeric_ratings.append(float(cleaned))
                    except ValueError:
                        pass
        if numeric_ratings:
            st.line_chart({"rating": numeric_ratings})
    else:
        _empty_state_message("No publicly available contest data")

    st.markdown("### Recent Activity")
    if activity:
        st.dataframe(activity, use_container_width=True)
    else:
        _empty_state_message("Recent public activity is not available.")

    st.markdown("### Sync Information")
    last_synced = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    source_url = f"https://www.hackerrank.com/{username}"
    status = "Success"
    if not profile.get("username"):
        status = "Failed"
    st.write(f"Last synced: {last_synced}")
    st.write(f"Source: {source_url}")
    st.write(f"Collection status: {status}")

    mongo_ok, mongo_msg = _save_to_mongodb(profile, collected)
    if not mongo_ok:
        st.warning(f"Profile collected, but MongoDB synchronization failed. Details: {mongo_msg}")


if __name__ == "__main__":
    main()

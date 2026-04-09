from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
    "you",
    "your",
}


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def safe_json_loads(value: Any, default: Any = None) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return default

    cleaned = (
        value.strip()
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return default
    return default


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        value = raw.strip()
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            ordered.append(value)
    return ordered


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,\n ]+", value) if item.strip()]
    return [str(value).strip()]


def parse_competitors(value: Any) -> list[str]:
    return [item.lstrip("@") for item in as_list(value)]


def slugify(value: str) -> str:
    lowered = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return lowered or "run"


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json_artifact(output_dir: Path, prefix: str, payload: dict[str, Any]) -> Path:
    ensure_directory(output_dir)
    artifact_path = output_dir / f"{prefix}.json"
    artifact_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return artifact_path


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def poll_until(
    fetcher: Callable[[], dict[str, Any]],
    *,
    is_complete: Callable[[dict[str, Any]], bool],
    interval_seconds: int,
    attempts: int,
) -> dict[str, Any]:
    last_payload: dict[str, Any] = {}
    for _ in range(attempts):
        last_payload = fetcher()
        if is_complete(last_payload):
            return last_payload
        time.sleep(interval_seconds)
    return last_payload


def _pick_metric(item: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        raw = item.get(key)
        if raw in (None, ""):
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return default


def rank_instagram_reels(reels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    now = datetime.now(UTC)

    for reel in reels:
        views = max(_pick_metric(reel, "videoPlayCount", "igPlayCount", "viewsCount", "views", "videoViewCount", default=1), 1)
        likes = _pick_metric(reel, "likesCount", "likes")
        comments = _pick_metric(reel, "commentsCount", "comments")
        shares = _pick_metric(reel, "reshareCount", "shares")
        engagement = likes + comments + shares
        engagement_rate = engagement / views

        timestamp = parse_datetime(reel.get("timestamp"))
        age_hours = max((now - timestamp).total_seconds() / 3600, 1.0) if timestamp else 24.0
        velocity_score = engagement_rate * 1000 / max(age_hours, 1)

        enriched = dict(reel)
        enriched.update(
            {
                "views": int(views),
                "likesCount": int(likes),
                "commentsCount": int(comments),
                "reshareCount": int(shares),
                "engagement_rate": round(engagement_rate, 6),
                "age_hours": round(age_hours, 2),
                "velocity_score": round(velocity_score, 3),
            }
        )
        ranked.append(enriched)

    ranked.sort(key=lambda item: (item["velocity_score"], item["views"]), reverse=True)
    return ranked


def select_recent_best_reels(
    reels: list[dict[str, Any]],
    *,
    recent_days: int = 2,
    limit: int = 5,
) -> list[dict[str, Any]]:
    threshold = datetime.now(UTC) - timedelta(days=recent_days)
    recent = []
    for reel in reels:
        timestamp = parse_datetime(reel.get("timestamp"))
        if timestamp and timestamp >= threshold:
            recent.append(reel)
    return (recent or reels)[:limit]


def analyze_instagram_reels(reels: list[dict[str, Any]], *, top_n: int = 10) -> dict[str, Any]:
    top_reels = reels[:top_n]
    if not top_reels:
        return {
            "total_reels": 0,
            "top_hashtags": [],
            "keywords": [],
            "content_patterns": {},
            "top_creators": [],
        }

    hashtags = Counter()
    keywords = Counter()
    creators = Counter()
    tracks = Counter()
    durations: list[float] = []
    engagement_rates: list[float] = []

    for reel in top_reels:
        creators.update([str(reel.get("ownerUsername") or reel.get("username") or "unknown")])
        tracks.update([str(reel.get("musicInfo", {}).get("songName") or reel.get("musicName") or "unknown")])
        durations.append(_pick_metric(reel, "videoDuration", "duration"))
        engagement_rates.append(float(reel.get("engagement_rate", 0)))

        caption = " ".join(
            str(reel.get(key, "")) for key in ("caption", "title", "transcript")
        ).lower()
        for word in re.findall(r"[a-zA-Z][a-zA-Z0-9']{2,}", caption):
            if word not in STOP_WORDS:
                keywords.update([word])

        for tag in as_list(reel.get("hashtags")):
            hashtags.update([tag.lstrip("#").lower()])

    avg_duration = sum(durations) / len([value for value in durations if value > 0] or [1])
    avg_engagement = sum(engagement_rates) / len(engagement_rates)

    return {
        "total_reels": len(top_reels),
        "top_hashtags": [{"hashtag": tag, "count": count} for tag, count in hashtags.most_common(15)],
        "keywords": [{"keyword": word, "count": count} for word, count in keywords.most_common(20)],
        "top_creators": [{"creator": name, "count": count} for name, count in creators.most_common(10)],
        "top_tracks": [{"track": track, "count": count} for track, count in tracks.most_common(10)],
        "content_patterns": {
            "avg_duration": round(avg_duration, 2),
            "avg_engagement_rate": round(avg_engagement, 6),
            "high_velocity_examples": [
                {
                    "url": reel.get("url"),
                    "caption": str(reel.get("caption") or "")[:200],
                    "velocity_score": reel.get("velocity_score"),
                }
                for reel in top_reels[:5]
            ],
        },
    }


def summarize_tweets(tweets: list[dict[str, Any]], *, top_n: int = 10) -> dict[str, Any]:
    valid = [tweet for tweet in tweets if tweet.get("text") or tweet.get("full_text")]
    ranked = []
    hashtag_counter = Counter()

    for tweet in valid:
        text = str(tweet.get("text") or tweet.get("full_text") or "")
        score = sum(
            _pick_metric(tweet, key)
            for key in ("views", "favorites", "retweets", "replies", "bookmarks")
        )
        ranked.append({**tweet, "engagement_score": int(score), "text": text})
        hashtag_counter.update([tag.lower() for tag in re.findall(r"#(\w+)", text)])

    ranked.sort(key=lambda item: item["engagement_score"], reverse=True)
    return {
        "tweet_count": len(valid),
        "top_hashtags": [{"hashtag": tag, "count": count} for tag, count in hashtag_counter.most_common(15)],
        "top_tweets": [
            {
                "author": tweet.get("author") or tweet.get("userName") or tweet.get("ownerUsername"),
                "text": tweet["text"][:280],
                "url": tweet.get("url"),
                "engagement_score": tweet["engagement_score"],
            }
            for tweet in ranked[:top_n]
        ],
    }


def summarize_linkedin_posts(posts: list[dict[str, Any]], *, top_n: int = 10) -> dict[str, Any]:
    ranked = []
    for post in posts:
        stats = post.get("stats", {})
        engagement = sum(
            float(stats.get(key, 0) or 0)
            for key in ("total_reactions", "comments", "shares")
        )
        ranked.append(
            {
                **post,
                "engagement_score": int(engagement),
                "text": str(post.get("text") or ""),
            }
        )

    ranked.sort(key=lambda item: item["engagement_score"], reverse=True)
    return {
        "post_count": len(posts),
        "top_posts": [
            {
                "author": post.get("author", {}).get("name") or post.get("authorName"),
                "text": post["text"][:500],
                "url": post.get("post_url") or post.get("url"),
                "engagement_score": post["engagement_score"],
            }
            for post in ranked[:top_n]
        ],
    }

from __future__ import annotations

import math
import os
import re
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from growth.growth_manager import (
    GrowthManager,
    GrowthContext,
)
from growth.evidence_engine import build_evidence_findings

from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from instagram_cache import (
    load_analysis_cache,
    save_analysis_cache,
)


# =========================================================
# Environment
# =========================================================

load_dotenv()

APP_API_TOKEN = os.getenv(
    "APP_API_TOKEN",
    "",
).strip()

BOXAPI_TOKEN = os.getenv(
    "BOXAPI_TOKEN",
    "",
).strip()

BOXAPI_USER_SEARCH_URL = (
    "https://boxapi.ir/api/instagram/user/"
    "search"
)

BOXAPI_PROFILE_URL = (
    "https://boxapi.ir/api/instagram/user/"
    "get_info_by_id"
)

BOXAPI_MEDIA_URL = (
    "https://boxapi.ir/api/instagram/user/"
    "get_media"
)


# =========================================================
# Router
# =========================================================

router = APIRouter(
    prefix="/v1/instagram",
    tags=["Instagram Analyzer"],
)


# =========================================================
# Schemas
# =========================================================

class InstagramAnalyzeRequest(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=200,
    )

    media_count: int = Field(
        default=12,
        ge=3,
        le=30,
    )

    # Optional IANA timezone (for example, Asia/Tehran). Existing clients may
    # omit it; recommendations are then explicitly labelled as UTC.
    account_timezone: str | None = Field(default=None, max_length=100)


class InstagramProfileResponse(BaseModel):
    id: str
    username: str
    full_name: str
    biography: str
    profile_picture_url: str
    followers_count: int
    following_count: int
    media_count: int
    is_private: bool
    is_verified: bool


class InstagramMediaSummary(BaseModel):
    id: str
    code: str | None = None
    media_type: str
    caption: str
    like_count: int
    comment_count: int
    view_count: int
    published_at: str | None = None
    thumbnail_url: str | None = None
    permalink: str | None = None


class InstagramAnalyticsResponse(BaseModel):
    analyzed_media_count: int
    average_likes: float
    average_comments: float
    average_views: float
    estimated_engagement_rate: float
    posting_consistency_score: int
    caption_usage_score: int
    public_performance_score: int
    posts_per_week: float
    suggested_publish_hour: int | None = None
    suggested_publish_time: str | None = None
    suggested_publish_timezone: str | None = None
    suggested_publish_explanation: str | None = None
    best_content_type: str | None = None


class InstagramSuggestion(BaseModel):
    title: str
    description: str
    priority: str


class InstagramAuditScores(BaseModel):
    overall_score: int
    bio_score: int
    content_score: int
    branding_score: int
    engagement_score: int
    consistency_score: int
    caption_score: int
    hashtag_score: int
    reels_score: int


class InstagramAuditInsight(BaseModel):
    title: str
    description: str
    score: int
    category: str
    priority: str


class InstagramBioAnalysis(BaseModel):
    score: int
    character_count: int
    has_clear_value: bool
    has_call_to_action: bool
    has_contact_hint: bool
    recommended_bio: str


class InstagramContentAnalysis(BaseModel):
    analyzed_media_count: int
    reels_count: int
    carousel_count: int
    image_count: int
    reels_ratio: int
    carousel_ratio: int
    image_ratio: int
    average_caption_length: int
    hashtag_usage_score: int
    dominant_content_type: str | None = None


class InstagramPostingPlan(BaseModel):
    posts_per_week: int
    reels_per_week: int
    carousels_per_week: int
    images_per_week: int
    stories_per_day: int
    suggested_publish_time: str | None = None
    content_mix: str


class InstagramGrowthAction(BaseModel):
    day_range: str
    title: str
    description: str
    priority: str


class InstagramAnalyzeResponse(BaseModel):
    success: bool
    profile: InstagramProfileResponse | None = None
    analytics: InstagramAnalyticsResponse | None = None
    recent_media: list[InstagramMediaSummary] = Field(default_factory=list)
    suggestions: list[InstagramSuggestion] = Field(default_factory=list)
    audit: InstagramAuditScores | None = None
    strengths: list[InstagramAuditInsight] = Field(default_factory=list)
    weaknesses: list[InstagramAuditInsight] = Field(default_factory=list)
    bio_analysis: InstagramBioAnalysis | None = None
    content_analysis: InstagramContentAnalysis | None = None
    posting_plan: InstagramPostingPlan | None = None
    growth_plan: list[InstagramGrowthAction] = Field(default_factory=list)

    # V6 findings retain the observations and sample size behind each claim.
    evidence_findings: list[dict[str, Any]] = Field(default_factory=list)

    # AI Growth Manager
    growth_manager: dict[str, Any] | None = None

    audit_version: int = 6
    source: str
    analyzed_at: str | None = None
    message: str | None = None


# =========================================================
# AI Content Director Context
# =========================================================

def build_content_director_context(
    analysis: InstagramAnalyzeResponse,
) -> dict[str, Any]:
    """Create a stable, JSON-friendly context for AI Content Director V5.

    The function intentionally contains no network or AI-provider dependency.
    It converts the real Analyzer output into a compact structure that can be
    consumed by dashboard_api.py or any future LLM-backed director.
    """
    profile = analysis.profile
    analytics = analysis.analytics

    if profile is None or analytics is None:
        return {
            "username": "",
            "full_name": "",
            "biography": "",
            "followers_count": 0,
            "following_count": 0,
            "media_count": 0,
            "analytics": {},
            "recent_media": [],
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
            "growth_plan": [],
            "growth_manager": None,
            "evidence_findings": [],
        }

    recent_media = []
    for item in (analysis.recent_media or [])[:12]:
        recent_media.append({
            "id": item.id,
            "media_type": item.media_type,
            "caption": item.caption,
            "like_count": item.like_count,
            "comment_count": item.comment_count,
            "view_count": item.view_count,
            "published_at": item.published_at,
            "permalink": item.permalink,
        })

    return {
        "username": profile.username,
        "full_name": profile.full_name,
        "biography": profile.biography,
        "followers_count": profile.followers_count,
        "following_count": profile.following_count,
        "media_count": profile.media_count,
        "is_verified": profile.is_verified,
        "analytics": {
            "analyzed_media_count": analytics.analyzed_media_count,
            "average_likes": analytics.average_likes,
            "average_comments": analytics.average_comments,
            "average_views": analytics.average_views,
            "estimated_engagement_rate": analytics.estimated_engagement_rate,
            "posting_consistency_score": analytics.posting_consistency_score,
            "caption_usage_score": analytics.caption_usage_score,
            "public_performance_score": analytics.public_performance_score,
            "posts_per_week": analytics.posts_per_week,
            "suggested_publish_time": analytics.suggested_publish_time,
            "suggested_publish_timezone": analytics.suggested_publish_timezone,
            "suggested_publish_explanation": analytics.suggested_publish_explanation,
            "best_content_type": analytics.best_content_type,
        },
        "recent_media": recent_media,
        "strengths": [item.model_dump(mode="json") for item in (analysis.strengths or [])],
        "weaknesses": [item.model_dump(mode="json") for item in (analysis.weaknesses or [])],
        "suggestions": [item.model_dump(mode="json") for item in (analysis.suggestions or [])],
        "growth_plan": [item.model_dump(mode="json") for item in (analysis.growth_plan or [])],
        "growth_manager": analysis.growth_manager,
        "evidence_findings": analysis.evidence_findings,
        "bio_analysis": analysis.bio_analysis.model_dump(mode="json") if analysis.bio_analysis else None,
        "content_analysis": analysis.content_analysis.model_dump(mode="json") if analysis.content_analysis else None,
        "posting_plan": analysis.posting_plan.model_dump(mode="json") if analysis.posting_plan else None,
        "audit": analysis.audit.model_dump(mode="json") if analysis.audit else None,
    }


# =========================================================
# Authentication
# =========================================================

def verify_app_token(
    authorization: str | None,
) -> None:
    if not APP_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail=(
                "APP_API_TOKEN روی سرور تنظیم نشده است."
            ),
        )

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail=(
                "Authorization header is required."
            ),
        )

    expected = f"Bearer {APP_API_TOKEN}"

    if authorization.strip() != expected:
        raise HTTPException(
            status_code=401,
            detail="توکن برنامه معتبر نیست.",
        )


# =========================================================
# General helpers
# =========================================================

def normalize_instagram_username(
    raw_value: str,
) -> str:
    value = raw_value.strip()

    value = re.sub(
        r"^https?://",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = re.sub(
        r"^www\.",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = value.removeprefix("@").strip()

    if value.lower().startswith("instagram.com/"):
        value = value.split("/", 1)[1]

    value = (
        value
        .split("?")[0]
        .split("#")[0]
        .split("/")[0]
        .removeprefix("@")
        .strip()
    )

    if not re.fullmatch(
        r"[A-Za-z0-9._]{1,30}",
        value,
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "نام کاربری یا لینک اینستاگرام "
                "معتبر نیست."
            ),
        )

    return value


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        if value is None:
            return default

        if isinstance(value, bool):
            return int(value)

        return int(float(value))

    except (TypeError, ValueError):
        return default


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(
        minimum,
        min(value, maximum),
    )


def first_non_empty(
    *values: Any,
) -> Any:
    for value in values:
        if value is None:
            continue

        if isinstance(value, str):
            if value.strip():
                return value.strip()
            continue

        return value

    return None


def resolve_account_timezone(account_timezone: str | None) -> ZoneInfo:
    """Return a validated account timezone, defaulting explicitly to UTC."""
    timezone_name = (account_timezone or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise HTTPException(
            status_code=422,
            detail="منطقه زمانی حساب معتبر نیست؛ یک نام IANA مانند Asia/Tehran ارسال کنید.",
        ) from error


# =========================================================
# BoxAPI response helpers
# =========================================================

def unwrap_boxapi_response(
    payload: dict[str, Any],
) -> Any:
    current: Any = payload

    if isinstance(current, dict):
        status = current.get("status")

        if status not in (None, "done", "success"):
            message = (
                current.get("message")
                or current.get("error")
                or "BoxAPI پاسخ ناموفق برگرداند."
            )

            raise HTTPException(
                status_code=502,
                detail=str(message),
            )

        response = current.get("response")

        if isinstance(response, dict):
            status_code = safe_int(
                response.get("status_code"),
                200,
            )

            if status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "BoxAPI با وضعیت "
                        f"{status_code} پاسخ داد."
                    ),
                )

            if "body" in response:
                current = response["body"]
            else:
                current = response

    return current


def find_user_recursively(
    value: Any,
) -> dict[str, Any] | None:
    if isinstance(value, dict):
        direct_user = value.get("user")

        if isinstance(direct_user, dict):
            return direct_user

        if (
            "username" in value
            and (
                "id" in value
                or "pk" in value
                or "full_name" in value
            )
        ):
            return value

        preferred_keys = (
            "data",
            "body",
            "response",
            "result",
        )

        for key in preferred_keys:
            if key not in value:
                continue

            found = find_user_recursively(
                value[key]
            )

            if found is not None:
                return found

        for child in value.values():
            found = find_user_recursively(child)

            if found is not None:
                return found

    elif isinstance(value, list):
        for child in value:
            found = find_user_recursively(child)

            if found is not None:
                return found

    return None


def find_media_items_recursively(
    value: Any,
) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        items = value.get("items")

        if isinstance(items, list):
            result = [
                item
                for item in items
                if isinstance(item, dict)
            ]

            if result:
                return result

        edges = value.get("edges")

        if isinstance(edges, list):
            result: list[dict[str, Any]] = []

            for edge in edges:
                if not isinstance(edge, dict):
                    continue

                node = edge.get("node")

                if isinstance(node, dict):
                    result.append(node)
                else:
                    result.append(edge)

            if result:
                return result

        preferred_keys = (
            "data",
            "body",
            "response",
            "result",
            "media",
        )

        for key in preferred_keys:
            if key not in value:
                continue

            found = find_media_items_recursively(
                value[key]
            )

            if found:
                return found

        for child in value.values():
            found = find_media_items_recursively(
                child
            )

            if found:
                return found

    return []


def find_exact_user_from_search(
    value: Any,
    username: str,
) -> dict[str, Any] | None:
    expected = username.strip().lower()

    if isinstance(value, dict):
        candidate_username = str(
            value.get("username") or ""
        ).strip().lower()

        if candidate_username == expected:
            if safe_int(
                first_non_empty(
                    value.get("pk"),
                    value.get("id"),
                    value.get("pk_id"),
                    value.get("user_id"),
                )
            ) > 0:
                return value

        for key in (
            "users",
            "data",
            "body",
            "response",
            "result",
            "items",
        ):
            if key in value:
                found = find_exact_user_from_search(
                    value[key],
                    username,
                )
                if found is not None:
                    return found

        for child in value.values():
            found = find_exact_user_from_search(
                child,
                username,
            )
            if found is not None:
                return found

    elif isinstance(value, list):
        for child in value:
            found = find_exact_user_from_search(
                child,
                username,
            )
            if found is not None:
                return found

    return None


def extract_numeric_user_id(
    user: dict[str, Any],
) -> int:
    return safe_int(
        first_non_empty(
            user.get("pk"),
            user.get("id"),
            user.get("pk_id"),
            user.get("user_id"),
        )
    )


# =========================================================
# Profile extraction
# =========================================================

def extract_followers_count(
    user: dict[str, Any],
) -> int:
    edge = user.get("edge_followed_by")

    if isinstance(edge, dict):
        return safe_int(edge.get("count"))

    return safe_int(
        first_non_empty(
            user.get("followers_count"),
            user.get("follower_count"),
            user.get("followers"),
        )
    )


def extract_following_count(
    user: dict[str, Any],
) -> int:
    edge = user.get("edge_follow")

    if isinstance(edge, dict):
        return safe_int(edge.get("count"))

    return safe_int(
        first_non_empty(
            user.get("following_count"),
            user.get("following"),
        )
    )


def extract_profile_media_count(
    user: dict[str, Any],
) -> int:
    timeline = user.get(
        "edge_owner_to_timeline_media"
    )

    if isinstance(timeline, dict):
        return safe_int(timeline.get("count"))

    return safe_int(
        first_non_empty(
            user.get("media_count"),
            user.get("post_count"),
            user.get("posts_count"),
        )
    )


# =========================================================
# Media extraction
# =========================================================

def extract_caption(
    item: dict[str, Any],
) -> str:
    caption = item.get("caption")

    if isinstance(caption, str):
        return caption.strip()

    if isinstance(caption, dict):
        return str(
            caption.get("text")
            or ""
        ).strip()

    edge_caption = item.get(
        "edge_media_to_caption"
    )

    if isinstance(edge_caption, dict):
        edges = edge_caption.get("edges")

        if isinstance(edges, list) and edges:
            first = edges[0]

            if isinstance(first, dict):
                node = first.get("node")

                if isinstance(node, dict):
                    return str(
                        node.get("text")
                        or ""
                    ).strip()

    return ""


def extract_like_count(
    item: dict[str, Any],
) -> int:
    direct = first_non_empty(
        item.get("like_count"),
        item.get("likes_count"),
    )

    if direct is not None:
        return safe_int(direct)

    for key in (
        "edge_liked_by",
        "edge_media_preview_like",
    ):
        value = item.get(key)

        if isinstance(value, dict):
            return safe_int(value.get("count"))

    return 0


def extract_comment_count(
    item: dict[str, Any],
) -> int:
    direct = first_non_empty(
        item.get("comment_count"),
        item.get("comments_count"),
    )

    if direct is not None:
        return safe_int(direct)

    for key in (
        "edge_media_to_comment",
        "edge_media_to_parent_comment",
    ):
        value = item.get(key)

        if isinstance(value, dict):
            return safe_int(value.get("count"))

    return 0


def extract_view_count(
    item: dict[str, Any],
) -> int:
    for key in (
        "view_count",
        "play_count",
        "video_view_count",
        "video_play_count",
        "ig_play_count",
        "clips_play_count",
    ):
        value = safe_int(item.get(key))

        if value > 0:
            return value

    return 0


def extract_timestamp(
    item: dict[str, Any],
) -> int:
    for key in (
        "taken_at",
        "taken_at_timestamp",
        "timestamp",
        "device_timestamp",
    ):
        value = safe_int(item.get(key))

        if value <= 0:
            continue

        while value > 10_000_000_000:
            value //= 1000

        return value

    return 0


def extract_media_type(
    item: dict[str, Any],
) -> str:
    product_type = str(
        item.get("product_type")
        or ""
    ).lower()

    typename = str(
        item.get("__typename")
        or ""
    ).lower()

    media_type = safe_int(
        item.get("media_type")
    )

    if (
        product_type in (
            "clips",
            "reels",
            "reel",
        )
        or "video" in typename
        or media_type == 2
    ):
        return "reel"

    if (
        media_type == 8
        or "sidecar" in typename
        or item.get("carousel_media")
    ):
        return "carousel"

    return "image"


def extract_thumbnail_url(
    item: dict[str, Any],
) -> str | None:
    value = first_non_empty(
        item.get("thumbnail_url"),
        item.get("display_url"),
        item.get("image_versions2"),
    )

    if isinstance(value, str):
        return value

    image_versions = item.get(
        "image_versions2"
    )

    if isinstance(image_versions, dict):
        candidates = image_versions.get(
            "candidates"
        )

        if (
            isinstance(candidates, list)
            and candidates
            and isinstance(candidates[0], dict)
        ):
            url = candidates[0].get("url")

            if isinstance(url, str):
                return url

    return None


def create_media_summary(
    item: dict[str, Any],
) -> InstagramMediaSummary:
    timestamp = extract_timestamp(item)

    published_at = None

    if timestamp > 0:
        published_at = datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        ).isoformat()

    code = first_non_empty(
        item.get("code"),
        item.get("shortcode"),
    )

    permalink = (
        f"https://www.instagram.com/p/{code}/"
        if code
        else None
    )

    return InstagramMediaSummary(
        id=str(
            first_non_empty(
                item.get("id"),
                item.get("pk"),
            )
            or ""
        ),
        code=str(code) if code else None,
        media_type=extract_media_type(item),
        caption=extract_caption(item),
        like_count=extract_like_count(item),
        comment_count=extract_comment_count(item),
        view_count=extract_view_count(item),
        published_at=published_at,
        thumbnail_url=extract_thumbnail_url(item),
        permalink=permalink,
    )


# =========================================================
# Analytics
# =========================================================

def calculate_posting_consistency(
    media: list[InstagramMediaSummary],
) -> int:
    timestamps: list[float] = []

    for item in media:
        if not item.published_at:
            continue

        try:
            parsed = datetime.fromisoformat(
                item.published_at
            )

            timestamps.append(
                parsed.timestamp()
            )

        except ValueError:
            continue

    timestamps.sort()

    if len(timestamps) < 2:
        return 0

    intervals = [
        (
            current - previous
        ) / 86_400
        for previous, current in zip(
            timestamps,
            timestamps[1:],
        )
        if current >= previous
    ]

    if not intervals:
        return 0

    average = sum(intervals) / len(intervals)

    variance = sum(
        (interval - average) ** 2
        for interval in intervals
    ) / len(intervals)

    standard_deviation = math.sqrt(variance)

    score = 100 - standard_deviation * 14

    return round(
        clamp(score, 0, 100)
    )


def calculate_posts_per_week(
    media: list[InstagramMediaSummary],
) -> float:
    dates: list[datetime] = []

    for item in media:
        if not item.published_at:
            continue

        try:
            dates.append(
                datetime.fromisoformat(
                    item.published_at
                )
            )

        except ValueError:
            continue

    if len(dates) < 2:
        return 0.0

    newest = max(dates)
    oldest = min(dates)

    days = max(
        (newest - oldest).total_seconds()
        / 86_400,
        1,
    )

    weeks = days / 7

    return round(
        len(dates) / max(weeks, 1),
        2,
    )


def calculate_suggested_hour(
    media: list[InstagramMediaSummary],
    followers: int,
    account_timezone: str | None = None,
) -> int | None:
    timezone_info = resolve_account_timezone(account_timezone)
    hourly_scores: dict[
        int,
        list[float],
    ] = defaultdict(list)

    for item in media:
        if not item.published_at:
            continue

        try:
            published_at = datetime.fromisoformat(
                item.published_at
            )

        except ValueError:
            continue

        score = (
            item.like_count
            + item.comment_count * 2.5
            + item.view_count * 0.02
        )

        if followers > 0:
            score = score / followers * 100

        localized = published_at.astimezone(timezone_info)
        hourly_scores[localized.hour].append(score)

    if not hourly_scores:
        return None

    return max(
        hourly_scores,
        key=lambda hour: (
            sum(hourly_scores[hour])
            / len(hourly_scores[hour])
        ),
    )


def calculate_best_content_type(
    media: list[InstagramMediaSummary],
    followers: int,
) -> str | None:
    type_scores: dict[
        str,
        list[float],
    ] = defaultdict(list)

    for item in media:
        score = (
            item.like_count
            + item.comment_count * 2.5
            + item.view_count * 0.02
        )

        if followers > 0:
            score = score / followers * 100

        type_scores[
            item.media_type
        ].append(score)

    if not type_scores:
        return None

    return max(
        type_scores,
        key=lambda media_type: (
            sum(type_scores[media_type])
            / len(type_scores[media_type])
        ),
    )


def calculate_analytics(
    media: list[InstagramMediaSummary],
    followers: int,
    account_timezone: str | None = None,
) -> InstagramAnalyticsResponse:
    count = len(media)

    if count == 0:
        return InstagramAnalyticsResponse(
            analyzed_media_count=0,
            average_likes=0,
            average_comments=0,
            average_views=0,
            estimated_engagement_rate=0,
            posting_consistency_score=0,
            caption_usage_score=0,
            public_performance_score=0,
            posts_per_week=0,
        )

    average_likes = (
        sum(item.like_count for item in media)
        / count
    )

    average_comments = (
        sum(item.comment_count for item in media)
        / count
    )

    view_values = [
        item.view_count
        for item in media
        if item.view_count > 0
    ]

    average_views = (
        sum(view_values) / len(view_values)
        if view_values
        else 0
    )

    engagement_rate = 0.0

    if followers > 0:
        engagement_rate = (
            (
                average_likes
                + average_comments
            )
            / followers
        ) * 100

    caption_items = sum(
        1
        for item in media
        if item.caption.strip()
    )

    caption_usage_score = round(
        caption_items / count * 100
    )

    consistency_score = (
        calculate_posting_consistency(media)
    )

    engagement_score = clamp(
        engagement_rate * 15,
        0,
        100,
    )

    view_score = 0.0

    if followers > 0 and average_views > 0:
        view_score = clamp(
            average_views
            / followers
            * 100,
            0,
            100,
        )

    performance_score = round(
        engagement_score * 0.50
        + consistency_score * 0.20
        + caption_usage_score * 0.15
        + view_score * 0.15
    )

    suggested_hour = calculate_suggested_hour(
        media=media,
        followers=followers,
        account_timezone=account_timezone,
    )

    timezone_name = account_timezone or "UTC"

    return InstagramAnalyticsResponse(
        analyzed_media_count=count,
        average_likes=round(
            average_likes,
            2,
        ),
        average_comments=round(
            average_comments,
            2,
        ),
        average_views=round(
            average_views,
            2,
        ),
        estimated_engagement_rate=round(
            engagement_rate,
            3,
        ),
        posting_consistency_score=(
            consistency_score
        ),
        caption_usage_score=caption_usage_score,
        public_performance_score=performance_score,
        posts_per_week=calculate_posts_per_week(
            media
        ),
        suggested_publish_hour=(
            suggested_hour
        ),
        suggested_publish_time=(
            f"{suggested_hour:02d}:00 ({timezone_name})"
            if suggested_hour is not None
            else None
        ),
        suggested_publish_timezone=(timezone_name if suggested_hour is not None else None),
        suggested_publish_explanation=(
            f"زمان پیشنهادی بر اساس ساعت محلی حساب {timezone_name} محاسبه شده است."
            if suggested_hour is not None and account_timezone
            else "منطقه زمانی حساب مشخص نیست؛ زمان پیشنهادی به وقت UTC است."
            if suggested_hour is not None
            else None
        ),
        best_content_type=(
            calculate_best_content_type(
                media=media,
                followers=followers,
            )
        ),
    )


# =========================================================
# Suggestions
# =========================================================

def build_suggestions(
    profile: InstagramProfileResponse,
    analytics: InstagramAnalyticsResponse,
) -> list[InstagramSuggestion]:
    suggestions: list[InstagramSuggestion] = []

    if not profile.biography.strip():
        suggestions.append(
            InstagramSuggestion(
                title="بیو پیج را کامل کن",
                description=(
                    "موضوع فعالیت، مزیت اصلی و یک "
                    "دعوت به اقدام مشخص را در بیو "
                    "قرار بده."
                ),
                priority="high",
            )
        )

    elif len(profile.biography.strip()) < 40:
        suggestions.append(
            InstagramSuggestion(
                title="بیو را واضح‌تر بنویس",
                description=(
                    "بیو کوتاه است. توضیح بده چه "
                    "ارزشی ارائه می‌کنی و مخاطب "
                    "چه اقدامی انجام دهد."
                ),
                priority="medium",
            )
        )

    if (
        analytics.estimated_engagement_rate
        < 1
    ):
        suggestions.append(
            InstagramSuggestion(
                title="تعامل پیج را افزایش بده",
                description=(
                    "از سؤال، CTA، محتوای آموزشی "
                    "قابل ذخیره و ریلزهای کوتاه "
                    "استفاده کن."
                ),
                priority="high",
            )
        )

    elif (
        analytics.estimated_engagement_rate
        < 3
    ):
        suggestions.append(
            InstagramSuggestion(
                title="دعوت به اقدام قوی‌تر بساز",
                description=(
                    "در پایان کپشن از مخاطب بخواه "
                    "نظر بدهد، ذخیره کند یا محتوا "
                    "را برای دیگران بفرستد."
                ),
                priority="medium",
            )
        )

    if (
        analytics.posting_consistency_score
        < 55
    ):
        suggestions.append(
            InstagramSuggestion(
                title="انتشار را منظم‌تر کن",
                description=(
                    "فاصله انتشار محتواها نامنظم "
                    "است. چند روز و ساعت ثابت در "
                    "هفته انتخاب کن."
                ),
                priority="high",
            )
        )

    if analytics.caption_usage_score < 70:
        suggestions.append(
            InstagramSuggestion(
                title="برای همه محتواها کپشن بنویس",
                description=(
                    "بعضی محتواهای بررسی‌شده کپشن "
                    "ندارند. کپشن مناسب می‌تواند "
                    "تعامل و درک محتوا را بیشتر کند."
                ),
                priority="medium",
            )
        )

    if analytics.suggested_publish_time:
        suggestions.append(
            InstagramSuggestion(
                title="زمان پیشنهادی انتشار",
                description=(
                    "در میان محتواهای عمومی "
                    "بررسی‌شده، انتشار نزدیک ساعت "
                    f"{analytics.suggested_publish_time} "
                    "عملکرد بهتری داشته است. "
                    f"{analytics.suggested_publish_explanation or ''}"
                ),
                priority="medium",
            )
        )

    if analytics.best_content_type:
        type_names = {
            "reel": "ریلز",
            "carousel": "پست اسلایدی",
            "image": "پست تصویری",
        }

        readable_type = type_names.get(
            analytics.best_content_type,
            analytics.best_content_type,
        )

        suggestions.append(
            InstagramSuggestion(
                title="فرمت محتوای برتر",
                description=(
                    f"در محتواهای اخیر، {readable_type} "
                    "عملکرد عمومی بهتری داشته است."
                ),
                priority="medium",
            )
        )

    if not suggestions:
        suggestions.append(
            InstagramSuggestion(
                title="عملکرد عمومی مناسب است",
                description=(
                    "ساختار پیج مناسب است. موضوعات "
                    "جدید را آزمایش و نتایج هر فرمت "
                    "محتوا را مقایسه کن."
                ),
                priority="low",
            )
        )

    return suggestions[:6]


# =========================================================
# Advanced audit
# =========================================================

def _contains_any(value: str, words: tuple[str, ...]) -> bool:
    normalized = value.lower()
    return any(word in normalized for word in words)


def build_advanced_audit(
    profile: InstagramProfileResponse,
    analytics: InstagramAnalyticsResponse,
    media: list[InstagramMediaSummary],
) -> tuple[
    InstagramAuditScores,
    list[InstagramAuditInsight],
    list[InstagramAuditInsight],
    InstagramBioAnalysis,
    InstagramContentAnalysis,
    InstagramPostingPlan,
    list[InstagramGrowthAction],
]:
    biography = profile.biography.strip()
    bio_length = len(biography)

    has_value = bio_length >= 35 and _contains_any(
        biography,
        ("آموزش", "فروش", "کمک", "خدمات", "تخصص", "طراحی", "تولید", "مشاوره", "ارسال"),
    )
    has_cta = _contains_any(
        biography,
        ("دایرکت", "پیام", "سفارش", "خرید", "تماس", "لینک", "رزرو", "ثبت نام", "بزن"),
    )
    has_contact = bool(
        re.search(r"(@|https?://|www\.|\.com|\.ir|\+?\d{8,})", biography, flags=re.IGNORECASE)
    )

    bio_score = 20
    bio_score += 25 if bio_length >= 35 else round(bio_length / 35 * 25)
    bio_score += 25 if has_value else 0
    bio_score += 20 if has_cta else 0
    bio_score += 10 if has_contact else 0
    bio_score = round(clamp(bio_score, 0, 100))

    count = max(len(media), 1)
    reels_count = sum(1 for item in media if item.media_type == "reel")
    carousel_count = sum(1 for item in media if item.media_type == "carousel")
    image_count = sum(1 for item in media if item.media_type == "image")

    reels_ratio = round(reels_count / count * 100) if media else 0
    carousel_ratio = round(carousel_count / count * 100) if media else 0
    image_ratio = round(image_count / count * 100) if media else 0

    captions = [item.caption.strip() for item in media if item.caption.strip()]
    average_caption_length = (
        round(sum(len(caption) for caption in captions) / len(captions))
        if captions else 0
    )

    hashtag_posts = sum(
        1 for item in media if re.search(r"#[\w\u0600-\u06FF]+", item.caption)
    )
    hashtag_score = round(hashtag_posts / count * 100) if media else 0

    cta_posts = sum(
        1 for item in media
        if _contains_any(
            item.caption,
            ("نظر", "کامنت", "ذخیره", "ارسال", "دایرکت", "لینک", "سفارش", "فالو"),
        )
    )
    cta_score = round(cta_posts / count * 100) if media else 0

    engagement_score = round(
        clamp(analytics.estimated_engagement_rate * 18, 0, 100)
    )
    consistency_score = analytics.posting_consistency_score
    caption_score = round(
        analytics.caption_usage_score * 0.65 + cta_score * 0.35
    )
    reels_score = round(
        clamp(reels_ratio * 1.25 + (20 if analytics.best_content_type == "reel" else 0), 0, 100)
    )
    content_score = round(
        engagement_score * 0.35
        + caption_score * 0.20
        + consistency_score * 0.20
        + reels_score * 0.15
        + hashtag_score * 0.10
    )
    branding_score = round(
        bio_score * 0.55
        + (20 if profile.full_name.strip() else 0)
        + (15 if profile.profile_picture_url else 0)
        + (10 if profile.is_verified else 0)
    )
    branding_score = round(clamp(branding_score, 0, 100))

    overall_score = round(
        bio_score * 0.18
        + content_score * 0.27
        + branding_score * 0.15
        + engagement_score * 0.18
        + consistency_score * 0.10
        + caption_score * 0.06
        + hashtag_score * 0.03
        + reels_score * 0.03
    )

    audit = InstagramAuditScores(
        overall_score=overall_score,
        bio_score=bio_score,
        content_score=content_score,
        branding_score=branding_score,
        engagement_score=engagement_score,
        consistency_score=consistency_score,
        caption_score=caption_score,
        hashtag_score=hashtag_score,
        reels_score=reels_score,
    )

    score_items = [
        ("بیو و معرفی پیج", bio_score, "bio"),
        ("کیفیت محتوا", content_score, "content"),
        ("هویت و برندینگ", branding_score, "branding"),
        ("تعامل مخاطبان", engagement_score, "engagement"),
        ("نظم انتشار", consistency_score, "consistency"),
        ("کپشن و دعوت به اقدام", caption_score, "caption"),
        ("استفاده از هشتگ", hashtag_score, "hashtag"),
        ("عملکرد ریلز", reels_score, "reels"),
    ]

    strengths = [
        InstagramAuditInsight(
            title=title,
            description=f"این بخش با امتیاز {score} از ۱۰۰ جزو نقاط قوت پیج است.",
            score=score,
            category=category,
            priority="low",
        )
        for title, score, category in sorted(score_items, key=lambda item: item[1], reverse=True)
        if score >= 65
    ][:4]

    weaknesses = [
        InstagramAuditInsight(
            title=title,
            description=f"امتیاز این بخش {score} از ۱۰۰ است و باید در برنامه رشد اصلاح شود.",
            score=score,
            category=category,
            priority="high" if score < 35 else "medium",
        )
        for title, score, category in sorted(score_items, key=lambda item: item[1])
        if score < 65
    ][:4]

    recommended_bio = (
        f"{profile.full_name or profile.username} | تخصص و نتیجه‌ای که ارائه می‌کنی\n"
        "کمک می‌کنم مخاطب به نتیجه مشخص برسد\n"
        "برای مشاوره یا سفارش، دایرکت پیام بده"
    )

    bio_analysis = InstagramBioAnalysis(
        score=bio_score,
        character_count=bio_length,
        has_clear_value=has_value,
        has_call_to_action=has_cta,
        has_contact_hint=has_contact,
        recommended_bio=recommended_bio,
    )

    type_names = {
        "reel": "ریلز",
        "carousel": "پست اسلایدی",
        "image": "پست تصویری",
    }
    content_analysis = InstagramContentAnalysis(
        analyzed_media_count=len(media),
        reels_count=reels_count,
        carousel_count=carousel_count,
        image_count=image_count,
        reels_ratio=reels_ratio,
        carousel_ratio=carousel_ratio,
        image_ratio=image_ratio,
        average_caption_length=average_caption_length,
        hashtag_usage_score=hashtag_score,
        dominant_content_type=type_names.get(analytics.best_content_type or ""),
    )

    target_posts = 4 if analytics.posts_per_week < 3 else min(6, max(3, round(analytics.posts_per_week)))
    target_reels = max(2, round(target_posts * 0.5))
    target_carousels = max(1, round(target_posts * 0.3))
    target_images = max(0, target_posts - target_reels - target_carousels)

    posting_plan = InstagramPostingPlan(
        posts_per_week=target_posts,
        reels_per_week=target_reels,
        carousels_per_week=target_carousels,
        images_per_week=target_images,
        stories_per_day=5,
        suggested_publish_time=analytics.suggested_publish_time,
        content_mix="۵۰٪ ریلز، ۳۰٪ محتوای اسلایدی و ۲۰٪ محتوای تصویری",
    )

    growth_plan = [
        InstagramGrowthAction(
            day_range="روز ۱ تا ۷",
            title="اصلاح پایه پیج",
            description="بیو، تصویر پروفایل، CTA و سه موضوع اصلی محتوا را شفاف و یکدست کن.",
            priority="high",
        ),
        InstagramGrowthAction(
            day_range="روز ۸ تا ۱۴",
            title="افزایش نظم و کیفیت",
            description=f"طبق برنامه، هفته‌ای {target_posts} محتوا منتشر کن و نتیجه هر فرمت را ثبت کن.",
            priority="high",
        ),
        InstagramGrowthAction(
            day_range="روز ۱۵ تا ۲۱",
            title="تمرکز روی تعامل",
            description="در کپشن‌ها سؤال مشخص، دعوت به ذخیره و دعوت به ارسال برای دوستان قرار بده.",
            priority="medium",
        ),
        InstagramGrowthAction(
            day_range="روز ۲۲ تا ۳۰",
            title="بهینه‌سازی بر اساس داده",
            description="سه محتوای برتر را شناسایی کن و موضوع، هوک و فرمت موفق آن‌ها را تکرار کن.",
            priority="medium",
        ),
    ]

    return (
        audit,
        strengths,
        weaknesses,
        bio_analysis,
        content_analysis,
        posting_plan,
        growth_plan,
    )


# =========================================================
# BoxAPI HTTP
# =========================================================

async def boxapi_post(
    url: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not BOXAPI_TOKEN:
        raise HTTPException(
            status_code=500,
            detail=(
                "BOXAPI_TOKEN روی سرور "
                "تنظیم نشده است."
            ),
        )

    timeout = httpx.Timeout(
        connect=15,
        read=60,
        write=20,
        pool=20,
    )

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": (
                        f"Bearer {BOXAPI_TOKEN}"
                    ),
                    "Content-Type": (
                        "application/json"
                    ),
                    "Accept": "application/json",
                },
                json=payload,
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=(
                    "BoxAPI درخواست را نپذیرفت. "
                    f"HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                ),
            )

        data = response.json()

        if not isinstance(data, dict):
            raise HTTPException(
                status_code=502,
                detail=(
                    "پاسخ BoxAPI ساختار JSON "
                    "معتبری ندارد."
                ),
            )

        return data

    except HTTPException:
        raise

    except httpx.TimeoutException as error:
        raise HTTPException(
            status_code=504,
            detail=(
                "زمان دریافت اطلاعات "
                "اینستاگرام تمام شد."
            ),
        ) from error

    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "خطا در ارتباط با BoxAPI: "
                f"{error}"
            ),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "پاسخ BoxAPI فرمت JSON "
                "معتبر ندارد."
            ),
        ) from error


async def fetch_instagram_profile(
    username: str,
) -> dict[str, Any]:
    search_payload = await boxapi_post(
        url=BOXAPI_USER_SEARCH_URL,
        payload={
            "query": username,
        },
    )

    search_body = unwrap_boxapi_response(
        search_payload
    )

    matched_user = find_exact_user_from_search(
        search_body,
        username,
    )

    if matched_user is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "پیجی با این نام کاربری در نتایج "
                "BoxAPI پیدا نشد."
            ),
        )

    user_id = extract_numeric_user_id(
        matched_user
    )

    if user_id <= 0:
        raise HTTPException(
            status_code=502,
            detail=(
                "شناسه عددی پیج از نتیجه جستجوی "
                "BoxAPI دریافت نشد."
            ),
        )

    profile_payload = await boxapi_post(
        url=BOXAPI_PROFILE_URL,
        payload={
            "id": user_id,
        },
    )

    profile_body = unwrap_boxapi_response(
        profile_payload
    )

    user = find_user_recursively(
        profile_body
    )

    if user is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "BoxAPI پس از دریافت شناسه، "
                "اطلاعات کامل پیج را برنگرداند."
            ),
        )

    return user


# =========================================================
# Endpoint
# =========================================================

@router.post(
    "/analyze",
    response_model=InstagramAnalyzeResponse,
)
async def analyze_instagram_profile(
    request: InstagramAnalyzeRequest,
    authorization: str | None = Header(
        default=None
    ),
) -> InstagramAnalyzeResponse:
    verify_app_token(authorization)

    username = normalize_instagram_username(
        request.username
    )
    account_timezone = (
        request.account_timezone.strip()
        if request.account_timezone and request.account_timezone.strip()
        else None
    )
    resolve_account_timezone(account_timezone)

    fresh_cache = load_analysis_cache(
        username=username,
        allow_stale=False,
    )

    if (
        fresh_cache is not None
        and account_timezone is None
        and safe_int(fresh_cache.get("audit_version")) >= 6
    ):
        return InstagramAnalyzeResponse(
            **fresh_cache
        )

    try:
        user = await fetch_instagram_profile(
            username
        )

        profile = InstagramProfileResponse(
            id=str(
                first_non_empty(
                    user.get("id"),
                    user.get("pk"),
                )
                or ""
            ),
            username=str(
                first_non_empty(
                    user.get("username"),
                    username,
                )
            ),
            full_name=str(
                first_non_empty(
                    user.get("full_name"),
                    "",
                )
            ),
            biography=str(
                first_non_empty(
                    user.get("biography"),
                    user.get("bio"),
                    "",
                )
            ),
            profile_picture_url=str(
                first_non_empty(
                    (
                        user.get(
                            "hd_profile_pic_url_info"
                        )
                        or {}
                    ).get("url"),
                    user.get(
                        "profile_pic_url_hd"
                    ),
                    user.get(
                        "profile_pic_url"
                    ),
                    user.get(
                        "profile_picture_url"
                    ),
                    "",
                )
            ),
            followers_count=(
                extract_followers_count(user)
            ),
            following_count=(
                extract_following_count(user)
            ),
            media_count=(
                extract_profile_media_count(user)
            ),
            is_private=bool(
                user.get("is_private", False)
            ),
            is_verified=bool(
                user.get("is_verified", False)
            ),
        )

        if not profile.id:
            raise HTTPException(
                status_code=502,
                detail=(
                    "شناسه عددی پیج از BoxAPI "
                    "دریافت نشد."
                ),
            )

        if profile.is_private:
            raise HTTPException(
                status_code=422,
                detail=(
                    "این پیج خصوصی است و محتوای "
                    "آن قابل تحلیل نیست."
                ),
            )

        media_payload = await boxapi_post(
            url=BOXAPI_MEDIA_URL,
            payload={
                "id": safe_int(profile.id),
                "count": request.media_count,
            },
        )

        media_body = unwrap_boxapi_response(
            media_payload
        )

        raw_media_items = (
            find_media_items_recursively(
                media_body
            )
        )

        recent_media = [
            create_media_summary(item)
            for item in raw_media_items[
                :request.media_count
            ]
        ]

        analytics = calculate_analytics(
            media=recent_media,
            followers=profile.followers_count,
            account_timezone=account_timezone,
        )

        suggestions = build_suggestions(
            profile=profile,
            analytics=analytics,
        )

        (
            audit,
            strengths,
            weaknesses,
            bio_analysis,
            content_analysis,
            posting_plan,
            growth_plan,
        ) = build_advanced_audit(
            profile=profile,
            analytics=analytics,
            media=recent_media,
        )

        evidence_findings = build_evidence_findings(
            media=recent_media,
            engagement_rate=analytics.estimated_engagement_rate,
            consistency_score=analytics.posting_consistency_score,
            caption_score=analytics.caption_usage_score,
            posts_per_week=analytics.posts_per_week,
        )

        growth_manager = GrowthManager(
            GrowthContext(
                username=profile.username,
                full_name=profile.full_name,
                followers=profile.followers_count,
                following=profile.following_count,
                posts=profile.media_count,
                engagement_rate=analytics.estimated_engagement_rate,
                posting_consistency=analytics.posting_consistency_score,
                caption_score=analytics.caption_usage_score,
                best_time=analytics.suggested_publish_time or "نامشخص",
                best_content_type=analytics.best_content_type or "محتوا",
                bio=profile.biography,
                is_verified=profile.is_verified,
                recent_media=recent_media,
            )
        ).build()

        result = InstagramAnalyzeResponse(
            success=True,
            profile=profile,
            analytics=analytics,
            recent_media=recent_media,
            suggestions=suggestions,
            audit=audit,
            strengths=strengths,
            weaknesses=weaknesses,
            bio_analysis=bio_analysis,
            content_analysis=content_analysis,
            posting_plan=posting_plan,
            growth_plan=growth_plan,
            evidence_findings=evidence_findings,
            growth_manager=growth_manager.model_dump(mode="json"),
            audit_version=7,
            source="boxapi_public_analysis_v7",
            analyzed_at=datetime.now(
                timezone.utc
            ).isoformat(),
            message=None,
        )

        # The current cache is keyed by username only. Cache the UTC/default
        # representation, but never leak one account timezone into another.
        if account_timezone is None:
            save_analysis_cache(
                username=username,
                response_data=result.model_dump(
                    mode="json"
                ),
            )

        return result

    except HTTPException:
        stale_cache = load_analysis_cache(
            username=username,
            allow_stale=True,
        )

        if stale_cache is not None:
            return InstagramAnalyzeResponse(
                **stale_cache
            )

        raise

    except Exception as error:
        print(
            "INSTAGRAM ANALYZER ERROR:",
            repr(error),
            flush=True,
        )

        traceback.print_exc()

        return InstagramAnalyzeResponse(
            success=False,
            profile=None,
            analytics=None,
            recent_media=[],
            suggestions=[],
            audit=None,
            strengths=[],
            weaknesses=[],
            bio_analysis=None,
            content_analysis=None,
            posting_plan=None,
            growth_plan=[],
            evidence_findings=[],
            audit_version=6,
            source="error",
            analyzed_at=None,
            message=str(error),
        )

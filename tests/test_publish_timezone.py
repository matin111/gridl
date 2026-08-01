import pytest
from fastapi import HTTPException

from instagram_analyzer import (
    InstagramMediaSummary,
    calculate_analytics,
    resolve_account_timezone,
)


def media_at(timestamp: str) -> InstagramMediaSummary:
    return InstagramMediaSummary(
        id=timestamp,
        media_type="image",
        caption="caption",
        like_count=10,
        comment_count=1,
        view_count=0,
        published_at=timestamp,
    )


def test_unknown_account_timezone_is_explicitly_utc():
    analytics = calculate_analytics(
        media=[media_at("2026-01-01T12:00:00+00:00")],
        followers=100,
    )

    assert analytics.suggested_publish_hour == 12
    assert analytics.suggested_publish_time == "12:00 (UTC)"
    assert analytics.suggested_publish_timezone == "UTC"
    assert "UTC" in analytics.suggested_publish_explanation


def test_publish_hour_is_converted_to_account_timezone():
    analytics = calculate_analytics(
        media=[media_at("2026-01-01T12:00:00+00:00")],
        followers=100,
        account_timezone="Asia/Tehran",
    )

    assert analytics.suggested_publish_hour == 15
    assert analytics.suggested_publish_time == "15:00 (Asia/Tehran)"
    assert analytics.suggested_publish_timezone == "Asia/Tehran"
    assert "Asia/Tehran" in analytics.suggested_publish_explanation


def test_invalid_account_timezone_is_rejected():
    with pytest.raises(HTTPException) as error:
        resolve_account_timezone("Mars/Olympus")

    assert error.value.status_code == 422

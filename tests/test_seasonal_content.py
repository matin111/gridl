from datetime import date

from dashboard_api import (
    ContentDirectorV5,
    SeasonalContentDetector,
    _build_content_director,
    _clean_caption_topic,
    _select_content_topic,
)


def media(caption, *, likes=10, published_at="2024-12-20T12:00:00Z", hashtags=None):
    return {
        "caption": caption,
        "like_count": likes,
        "comment_count": 0,
        "view_count": 0,
        "published_at": published_at,
        "hashtags": hashtags or [],
    }


def test_old_yalda_caption_does_not_generate_yalda_recommendation():
    result = _select_content_topic(
        {"recent_media": [media("دوستان یلداتون مبارک #یلدا", likes=500)]},
        "ریلز",
        today=date(2026, 8, 1),
    )

    assert result.detection.event == "یلدا"
    assert result.detection.relevance == "expired"
    assert "بدون تکرار موضوع یلدا" in result.topic
    assert "یلداتون مبارک" not in result.topic


def test_yalda_near_valid_date_can_preserve_event():
    result = _select_content_topic(
        {"recent_media": [media("شب یلدا کنار شما هستیم", likes=500)]},
        "ریلز",
        today=date(2026, 12, 5),
    )

    assert result.detection.relevance == "relevant"
    assert result.topic == "یک محتوای احساسی و مشارکتی برای یلدا"


def test_old_nowruz_becomes_evergreen_reusable_pattern():
    result = _select_content_topic(
        {"recent_media": [media("عید نوروز و سال نو مبارک", likes=500)]},
        "پست تصویری",
        today=date(2026, 8, 1),
    )

    assert result.detection.event == "نوروز"
    assert result.detection.relevance == "expired"
    assert "الگوی موفق" in result.topic
    assert "مبارک" not in result.topic


def test_strongest_non_seasonal_wins_over_expired_seasonal_content():
    result = _select_content_topic(
        {"recent_media": [media("یلدا مبارک", likes=1000), media("سه راه ساده برای بهتر نوشتن", likes=10)]},
        "ریلز",
        today=date(2026, 8, 1),
    )

    assert "سه راه ساده" in result.topic
    assert not result.detection.is_seasonal


def test_nested_prefix_hashtags_mentions_urls_and_raw_caption_are_cleaned():
    raw = "سلام دوستان! بازطراحی موضوع موفق اخیر: بازطراحی موضوع موفق اخیر: نکته کاربردی 😊😊😊 @brand https://example.com #آموزش #آموزش"
    cleaned = _clean_caption_topic(raw)

    assert "بازطراحی موضوع موفق اخیر" not in cleaned
    assert "#" not in cleaned
    assert "@brand" not in cleaned
    assert "http" not in cleaned
    assert "😊" not in cleaned
    assert len(cleaned) <= 72
    assert cleaned != raw


def test_missing_timestamp_uses_conservative_behavior_for_undatable_event():
    detection = SeasonalContentDetector().detect("ماه رمضان مبارک", published_at=None, today=date(2026, 8, 1))

    assert detection.relevance == "unknown"
    assert "موضوع دقیق تکرار نشد" in detection.reason


def test_content_director_keeps_android_schema_and_adds_seasonal_signals():
    legacy_fields = set(ContentDirectorV5.model_fields) - {
        "is_seasonal", "seasonal_event", "seasonal_relevance", "seasonal_reason", "reusable_pattern"
    }
    result = _build_content_director(
        {
            "recent_media": [media("ماه رمضان مبارک", published_at=None, likes=50)],
            "analytics": {"analyzed_media_count": 5},
            "followers_count": 100,
        },
        best_content_type="ریلز",
        best_time="18:00",
        growth_score=50,
    )
    payload = result.model_dump()

    assert legacy_fields <= payload.keys()
    assert result.is_seasonal is True
    assert result.seasonal_relevance == "unknown"
    assert result.confidence_score < 80
    assert any("فقط الگوی احساسی" in signal for signal in result.source_signals)
    assert "ماه رمضان مبارک" not in result.topic

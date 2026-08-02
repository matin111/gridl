from __future__ import annotations

from copy import deepcopy

from growth.post_intelligence_adapter import (
    attach_post_intelligence,
    build_post_intelligence_payload,
    enriched_response_copy,
)


def media(post_id: str, caption: str, likes: int = 0, thumbnail: str | None = None):
    return {
        "id": post_id,
        "caption": caption,
        "like_count": likes,
        "comment_count": 0,
        "view_count": 0,
        "media_type": "reel",
        "thumbnail_url": thumbnail,
    }


def test_build_payload_creates_per_post_dossiers():
    payload = build_post_intelligence_payload([
        media("1", "چرا این اشتباه را انجام می‌دهی؟\n\nذخیره کن.", 100, "https://example.com/1.jpg"),
        media("2", "متن ساده", 10),
    ])
    assert payload["version"] == 11
    assert payload["analyzed_posts"] == 2
    assert payload["posts"][0]["visual"]["status"] == "pending"
    assert payload["posts"][1]["visual"]["status"] == "unavailable"


def test_attach_is_additive_and_sets_version_11():
    response = {
        "success": True,
        "audit_version": 10,
        "profile_audit": {"score": 70},
        "content_audit": {"score": 60},
        "ai_growth_coach": {"status": "ready"},
    }
    attach_post_intelligence(response, [media("1", "ذخیره کن", 5)])
    assert response["success"] is True
    assert response["profile_audit"] == {"score": 70}
    assert response["content_audit"] == {"score": 60}
    assert response["ai_growth_coach"] == {"status": "ready"}
    assert response["audit_version"] == 11
    assert response["post_intelligence"]["analyzed_posts"] == 1


def test_enriched_copy_does_not_mutate_cache_payload():
    original = {
        "success": True,
        "audit_version": 10,
        "recent_media": [media("1", "نظر بده", 9)],
    }
    before = deepcopy(original)
    result = enriched_response_copy(original, original["recent_media"])
    assert original == before
    assert "post_intelligence" not in original
    assert result["post_intelligence"]["analyzed_posts"] == 1
    assert result["audit_version"] == 11

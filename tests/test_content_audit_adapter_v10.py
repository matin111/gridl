from growth.content_audit_adapter import (
    attach_content_audit,
    build_content_audit_payload,
    enriched_response_copy,
)


def sample_media():
    return [
        {
            "id": "1",
            "media_type": "reel",
            "caption": "چرا VPN تو کند شده؟\n\nسه دلیل مهم را بررسی کن.\n\nنظرت را کامنت کن #VPN #WireGuard #OpenVPN",
            "like_count": 120,
            "comment_count": 15,
            "view_count": 2200,
            "published_at": "2026-08-01T18:00:00+00:00",
            "permalink": "https://instagram.com/p/1/",
        },
        {
            "id": "2",
            "media_type": "image",
            "caption": "اشتراک جدید موجود شد",
            "like_count": 25,
            "comment_count": 1,
            "view_count": 0,
        },
    ]


def test_build_payload_contains_per_post_and_page_summary():
    payload = build_content_audit_payload(sample_media())

    assert payload["analyzed_posts"] == 2
    assert len(payload["posts"]) == 2
    assert "averages" in payload
    assert "priority_issues" in payload
    assert payload["posts"][0]["post_id"] == "1"


def test_attach_is_additive_and_preserves_legacy_fields():
    response = {
        "success": True,
        "audit_version": 10,
        "profile_audit": {"score": 80},
        "growth_manager": {"growth_score": 45},
    }

    result = attach_content_audit(response, sample_media())

    assert result is response
    assert result["success"] is True
    assert result["profile_audit"] == {"score": 80}
    assert result["growth_manager"] == {"growth_score": 45}
    assert result["content_audit"]["analyzed_posts"] == 2


def test_enriched_copy_does_not_mutate_cached_response():
    cached = {
        "success": True,
        "recent_media": sample_media(),
    }

    enriched = enriched_response_copy(cached, cached["recent_media"])

    assert "content_audit" not in cached
    assert enriched["content_audit"]["analyzed_posts"] == 2

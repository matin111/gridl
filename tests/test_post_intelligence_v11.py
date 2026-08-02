from types import SimpleNamespace

from growth.post_intelligence import build_post_intelligence


def media(post_id: str, caption: str, *, likes: int, views: int, thumbnail: str | None = None):
    return SimpleNamespace(
        id=post_id,
        caption=caption,
        like_count=likes,
        comment_count=0,
        view_count=views,
        media_type="reel",
        permalink=f"https://instagram.com/p/{post_id}/",
        published_at="2026-08-01T18:00:00+00:00",
        thumbnail_url=thumbnail,
    )


def test_builds_one_dossier_per_post():
    result = build_post_intelligence([
        media("a", "چرا اتصال قطع می‌شود؟\n\nنظر بده. #vpn", likes=100, views=1000),
        media("b", "متن ساده", likes=10, views=100),
    ])

    assert result["version"] == 11
    assert result["analyzed_posts"] == 2
    assert len(result["posts"]) == 2
    assert result["posts"][0]["hook"]["type"] == "question"
    assert result["posts"][0]["caption"]["cta_present"] is True


def test_visual_analysis_is_not_fabricated_without_image():
    result = build_post_intelligence([
        media("a", "متن ساده", likes=10, views=100),
    ])
    visual = result["posts"][0]["visual"]

    assert visual["status"] == "unavailable"
    assert visual["cover_score"] is None
    assert visual["face_detected"] is None


def test_thumbnail_marks_post_ready_for_vision_not_already_analysed():
    result = build_post_intelligence([
        media("a", "متن ساده", likes=10, views=100, thumbnail="https://example.com/a.jpg"),
    ])
    visual = result["posts"][0]["visual"]

    assert visual["status"] == "pending"
    assert visual["reason"] == "thumbnail_ready_for_vision"
    assert result["visual_analysis_ready"] == 1


def test_performance_labels_are_relative_to_page_sample():
    result = build_post_intelligence([
        media("strong", "۳ نکته مهم\n\nذخیره کن.", likes=300, views=3000),
        media("mid", "متن متوسط", likes=100, views=1000),
        media("weak", "متن ضعیف", likes=5, views=50),
    ])
    labels = {post["post_id"]: post["performance"]["label"] for post in result["posts"]}

    assert labels["strong"] == "strong"
    assert labels["weak"] == "weak"


def test_evidence_sources_are_explicit():
    result = build_post_intelligence([
        media("a", "چرا؟\n\nکامنت کن. #vpn", likes=10, views=100),
    ])
    sources = {item["source"] for item in result["posts"][0]["evidence"]}

    assert "caption_first_line" in sources
    assert "caption_text" in sources
    assert "caption_hashtags" in sources

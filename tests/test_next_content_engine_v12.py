from growth.next_content_engine import build_next_content


def post(post_id, performance, media_type="reel", pillar="education", hook_type="question", actions=None):
    return {
        "post_id": post_id,
        "media_type": media_type,
        "content_pillar": pillar,
        "performance": {"score": performance, "label": "strong" if performance >= 70 else "weak"},
        "hook": {"type": hook_type, "text": "نمونه هوک"},
        "visual_review": {
            "status": "ready",
            "actions": actions or [],
        },
    }


def test_next_content_uses_page_format_pillar_hook_and_repeated_cover_evidence():
    payload = {
        "posts": [
            post("1", 90, actions=["کنتراست متن را بیشتر کن"]),
            post("2", 85, actions=["کنتراست متن را بیشتر کن"]),
            post("3", 30, media_type="image", pillar="sales", hook_type="statement"),
            post("4", 20, media_type="image", pillar="sales", hook_type="statement"),
        ]
    }
    result = build_next_content(
        post_intelligence=payload,
        daily_mission={
            "key": "content:cta",
            "title": "CTA مشخص اضافه کن",
            "instruction": "در پایان فقط یک سؤال روشن بپرس.",
        },
    )
    assert result["status"] == "ready"
    assert result["recommended_format"] == "reel"
    assert result["content_pillar"] == "education"
    assert result["goal"] == "increase_comments"
    assert result["hook_strategy"]["type"] == "question"
    assert result["cover_strategy"]["status"] == "page_evidence"
    assert "کنتراست متن را بیشتر کن" in result["cover_strategy"]["rules"]


def test_next_content_does_not_invent_hashtags_or_exact_publish_time():
    result = build_next_content(
        post_intelligence={"posts": [post("1", 50)]},
        daily_mission=None,
        analytics=None,
    )
    assert result["hashtag_strategy"]["hashtags"] == []
    assert result["hashtag_strategy"]["status"] == "requires_domain_topic"
    assert result["publish_time"]["time"] is None


def test_next_content_uses_publish_history_when_available():
    result = build_next_content(
        post_intelligence={"posts": [post("1", 80), post("2", 70)]},
        daily_mission=None,
        analytics={
            "suggested_publish_time": "20:00",
            "suggested_publish_timezone": "Asia/Tehran",
            "suggested_publish_explanation": "بر اساس پست‌های اخیر",
        },
    )
    assert result["publish_time"]["time"] == "20:00"
    assert result["publish_time"]["source"] == "page_publish_history"


def test_next_content_handles_empty_input():
    result = build_next_content(post_intelligence=None, daily_mission=None)
    assert result["status"] == "insufficient_data"
    assert result["recommended_format"] is None
    assert result["content_pillar"] is None

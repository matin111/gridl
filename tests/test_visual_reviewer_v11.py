from growth.visual_reviewer import attach_visual_reviews, build_visual_review


def test_visual_review_does_not_invent_pending_analysis():
    review = build_visual_review({"status": "pending", "reason": "thumbnail_ready_for_vision"})
    assert review["status"] == "pending"
    assert review["strengths"] == []
    assert review["actions"] == []


def test_visual_review_preserves_vision_feedback_and_evidence():
    review = build_visual_review(
        {
            "status": "completed",
            "cover_score": 82,
            "scroll_stop_score": 76,
            "text_readability": 88,
            "contrast_score": 79,
            "composition_score": 74,
            "brand_consistency_score": 65,
            "face_detected": False,
            "ocr_text": "اینترنت سریع و پایدار",
            "strengths": ["تیتر خواناست"],
            "weaknesses": ["نقطه کانونی می‌تواند واضح‌تر باشد"],
            "recommendations": ["سوژه اصلی را بزرگ‌تر نمایش بده"],
        }
    )
    assert review["status"] == "ready"
    assert review["cover_score"] == 82
    assert review["strengths"] == ["تیتر خواناست"]
    assert review["improvements"] == ["نقطه کانونی می‌تواند واضح‌تر باشد"]
    assert review["actions"] == ["سوژه اصلی را بزرگ‌تر نمایش بده"]
    assert any(item["metric"] == "cover_score" for item in review["evidence"])
    assert review["ocr_text"] == "اینترنت سریع و پایدار"


def test_attach_visual_reviews_keeps_post_payload():
    payload = {
        "posts": [
            {
                "post_id": "1",
                "hook": {"score": 80},
                "visual": {"status": "completed", "cover_score": 70},
            },
            {
                "post_id": "2",
                "visual": {"status": "pending"},
            },
        ]
    }
    result = attach_visual_reviews(payload)
    assert result is not None
    assert result["posts"][0]["hook"]["score"] == 80
    assert result["posts"][0]["visual_review"]["status"] == "ready"
    assert result["posts"][1]["visual_review"]["status"] == "pending"
    assert result["visual_reviews_ready"] == 1

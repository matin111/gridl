from growth.growth_director_adapter import build_growth_director_payload


def test_growth_director_payload_contains_next_content():
    result = build_growth_director_payload(
        profile_audit={"score": 70, "summary": "نمونه", "strengths": []},
        content_audit={"score": 60, "priority_issues": []},
        post_intelligence={
            "posts": [
                {
                    "post_id": "1",
                    "media_type": "reel",
                    "content_pillar": "education",
                    "performance": {"score": 80, "label": "strong"},
                    "hook": {"type": "question", "text": "نمونه"},
                    "visual_review": {"status": "ready", "actions": []},
                },
                {
                    "post_id": "2",
                    "media_type": "reel",
                    "content_pillar": "education",
                    "performance": {"score": 70, "label": "strong"},
                    "hook": {"type": "question", "text": "نمونه"},
                    "visual_review": {"status": "ready", "actions": []},
                },
            ]
        },
        ai_growth_coach={
            "today_action": {
                "key": "content:cta",
                "title": "CTA مشخص اضافه کن",
                "instruction": "یک سؤال روشن بپرس.",
                "why": "CTA ضعیف است",
                "priority_score": 75,
                "impact_score": 65,
                "confidence_score": 90,
                "estimated_minutes": 5,
                "evidence": [],
            },
            "next_priorities": [],
        },
        analytics={
            "suggested_publish_time": "20:00",
            "suggested_publish_timezone": "Asia/Tehran",
        },
    )
    next_content = result["next_content"]
    assert next_content["status"] == "ready"
    assert next_content["recommended_format"] == "reel"
    assert next_content["content_pillar"] == "education"
    assert next_content["goal"] == "increase_comments"
    assert next_content["publish_time"]["time"] == "20:00"

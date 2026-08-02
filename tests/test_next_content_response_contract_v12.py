from growth.growth_director_adapter import build_growth_director_payload


def test_next_content_exposes_stable_user_facing_fields():
    result = build_growth_director_payload(
        profile_audit={"score": 70, "summary": "خلاصه", "strengths": []},
        content_audit={"score": 65, "priority_issues": []},
        post_intelligence={
            "posts": [
                {
                    "post_id": "1",
                    "media_type": "carousel",
                    "content_pillar": "sales",
                    "performance": {"score": 80, "label": "strong"},
                    "hook": {"type": "statement"},
                    "visual_review": {"status": "ready", "actions": []},
                },
                {
                    "post_id": "2",
                    "media_type": "carousel",
                    "content_pillar": "sales",
                    "performance": {"score": 70, "label": "strong"},
                    "hook": {"type": "statement"},
                    "visual_review": {"status": "ready", "actions": []},
                },
            ]
        },
        ai_growth_coach={
            "today_action": {
                "key": "content:cta",
                "title": "CTA اضافه کن",
                "instruction": "یک سؤال روشن بپرس.",
                "why": "CTA کم است",
                "evidence": ["2 پست"],
                "priority_score": 70,
                "impact_score": 60,
                "confidence_score": 90,
                "estimated_minutes": 5,
            },
            "next_priorities": [],
        },
        analytics={
            "suggested_publish_time": "12:00 (Asia/Tehran)",
            "suggested_publish_timezone": "Asia/Tehran",
            "suggested_publish_explanation": "بر اساس تاریخچه",
        },
    )

    next_content = result["next_content"]
    assert next_content["scenario"] == next_content["scenario_blueprint"]
    assert next_content["cta"] == next_content["cta_strategy"]
    assert next_content["why_this_content"]
    assert next_content["confidence_score"] in {45, 70, 90}
    assert next_content["publish_timezone"] == "Asia/Tehran"
    assert next_content["evidence"]["evidence_signals"] >= 1

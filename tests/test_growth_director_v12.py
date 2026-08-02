from growth.growth_director import build_growth_director


def coach():
    return {
        "today_action": {
            "key": "content:cta",
            "title": "CTA مشخص اضافه کن",
            "instruction": "در پایان محتوای بعدی فقط یک اقدام روشن بخواه.",
            "why": "CTA در چند پست اخیر دیده نشد",
            "evidence": ["3 پست از 8 پست"],
            "priority_score": 80,
            "impact_score": 70,
            "confidence_score": 90,
            "estimated_minutes": 5,
            "success_metric": "نرخ کامنت را مقایسه کن",
        },
        "next_priorities": [],
    }


def test_growth_director_builds_one_daily_mission_and_health_score():
    result = build_growth_director(
        profile_audit={"score": 80, "summary": "پروفایل مناسب است", "strengths": [{"title": "نام کاربری"}]},
        content_audit={"score": 60, "priority_issues": []},
        post_intelligence={
            "posts": [
                {"performance": {"score": 50}, "visual": {"status": "completed", "cover_score": 70}},
                {"performance": {"score": 70}, "visual": {"status": "completed", "cover_score": 80}},
            ]
        },
        ai_growth_coach=coach(),
    )
    assert result["version"] == 12
    assert result["status"] == "ready"
    assert 0 <= result["health_score"] <= 100
    assert result["daily_mission"]["key"] == "content:cta"
    assert len(result["top_priorities"]) == 1
    assert result["executive_summary"]["main_bottleneck"] == "CTA مشخص اضافه کن"


def test_growth_director_does_not_invent_visual_risk_from_one_post():
    result = build_growth_director(
        profile_audit=None,
        content_audit=None,
        post_intelligence={
            "posts": [
                {"visual_review": {"status": "ready", "improvements": ["کنتراست پایین"]}},
            ]
        },
        ai_growth_coach=None,
    )
    assert result["risk_alerts"] == []


def test_growth_director_reports_repeated_visual_risk_with_evidence():
    posts = [
        {"visual_review": {"status": "ready", "improvements": ["کنتراست پایین"]}},
        {"visual_review": {"status": "ready", "improvements": ["کنتراست پایین"]}},
        {"visual_review": {"status": "ready", "improvements": ["متن زیاد"]}},
    ]
    result = build_growth_director(
        profile_audit=None,
        content_audit=None,
        post_intelligence={"posts": posts},
        ai_growth_coach=None,
    )
    assert len(result["risk_alerts"]) == 1
    assert result["risk_alerts"][0]["affected_posts"] == 2
    assert "2 پست از 3" in result["risk_alerts"][0]["evidence"]


def test_growth_director_handles_empty_input():
    result = build_growth_director(
        profile_audit=None,
        content_audit=None,
        post_intelligence=None,
        ai_growth_coach=None,
    )
    assert result["status"] == "insufficient_data"
    assert result["health_score"] == 0
    assert result["daily_mission"] is None

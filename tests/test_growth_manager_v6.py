from growth.growth_manager import GrowthContext, GrowthManager


def build_manager():
    return GrowthManager(
        GrowthContext(
            username="sample",
            full_name="Sample Brand",
            followers=800,
            following=200,
            posts=9,
            engagement_rate=1.5,
            posting_consistency=45,
            caption_score=60,
            best_time="18:00",
            best_content_type="reel",
            bio="آموزش کاربردی",
        )
    ).build()


def test_growth_manager_v6_contains_complete_coaching_payload():
    result = build_manager()

    assert result.executive_summary
    assert 0 <= result.growth_score <= 100
    assert result.bio.ready_bios
    assert result.profile.suggestions
    assert result.content_diagnosis.strongest_format == "reel"
    assert result.recommendations
    assert result.daily_missions == result.daily_tasks
    assert len(result.weekly_roadmap) == 4
    assert result.growth_forecast.confidence == "low"
    assert result.publish.caption


def test_growth_manager_serializes_legacy_and_v6_fields_together():
    payload = build_manager().model_dump(mode="json")

    legacy_fields = {"growth_score", "daily_focus", "daily_tasks", "bio", "profile", "highlights", "publish"}
    v6_fields = {"executive_summary", "content_diagnosis", "daily_missions", "weekly_roadmap", "growth_forecast"}
    assert legacy_fields | v6_fields <= payload.keys()

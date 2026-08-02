from growth.ai_growth_coach import build_ai_growth_coach
from growth.priority_engine import build_growth_priorities


def profile_issue(score: int = 20):
    return {
        "score": 40,
        "issues": [
            {
                "key": "biography",
                "title": "بیو و ارزش پیشنهادی",
                "severity": "critical",
                "score": score,
                "explanation": "بیو ارزش پیشنهادی و CTA روشن ندارد.",
                "recommendation": "بیو را با خدمت، مخاطب و CTA مشخص بازنویسی کن.",
                "confidence": "high",
                "evidence": [
                    {"field": "call_to_action", "observed": "تشخیص داده نشد"},
                    {"field": "value_proposition", "observed": "تشخیص داده نشد"},
                ],
            }
        ],
    }


def content_issue():
    return {
        "analyzed_posts": 10,
        "priority_issues": [
            {
                "issue": "CTA مشخصی برای کامنت، ذخیره، ارسال، خرید یا پیام وجود ندارد",
                "affected_posts": 7,
                "affected_percent": 70,
                "priority": "high",
            },
            {
                "issue": "شروع کپشن عمومی یا ضعیف است؛ سؤال، تضاد، هشدار یا نتیجه روشن ندارد",
                "affected_posts": 6,
                "affected_percent": 60,
                "priority": "high",
            },
        ],
    }


def test_priority_engine_ranks_observed_issues_and_limits_output():
    priorities = build_growth_priorities(
        profile_audit=profile_issue(),
        content_audit=content_issue(),
        limit=2,
    )
    assert len(priorities) == 2
    assert priorities[0]["score"] >= priorities[1]["score"]
    assert priorities[0]["evidence"]
    assert 0 <= priorities[0]["score"] <= 100


def test_growth_coach_returns_one_today_action_and_next_priorities():
    result = build_ai_growth_coach(
        profile_audit=profile_issue(),
        content_audit=content_issue(),
    )
    assert result["status"] == "ready"
    assert result["today_action"] is not None
    assert result["today_action"]["instruction"]
    assert result["today_action"]["evidence"]
    assert result["today_action"]["estimated_minutes"] in {5, 15, 30}
    assert len(result["next_priorities"]) <= 2


def test_completed_action_is_not_repeated():
    first = build_ai_growth_coach(
        profile_audit=profile_issue(),
        content_audit=content_issue(),
    )
    completed_key = first["today_action"]["key"]
    second = build_ai_growth_coach(
        profile_audit=profile_issue(),
        content_audit=content_issue(),
        completed_keys=[completed_key],
    )
    assert second["today_action"] is not None
    assert second["today_action"]["key"] != completed_key


def test_no_data_returns_honest_no_action_state():
    result = build_ai_growth_coach(
        profile_audit=None,
        content_audit=None,
    )
    assert result["status"] == "no_action"
    assert result["today_action"] is None


def test_coach_does_not_claim_guaranteed_growth_percentage():
    result = build_ai_growth_coach(
        profile_audit=profile_issue(),
        content_audit=content_issue(),
    )
    serialized = str(result)
    assert "تضمین" in serialized
    assert "+18٪" not in serialized

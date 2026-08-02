from growth.growth_coach_adapter import (
    attach_growth_coach,
    enriched_response_copy,
)


def profile_issue(key="biography"):
    return {
        "key": key,
        "title": "بیو و ارزش پیشنهادی",
        "severity": "high",
        "score": 30,
        "explanation": "بیو واضح نیست",
        "impact": "تبدیل بازدیدکننده را کاهش می‌دهد",
        "recommendation": "بیو را با ارزش پیشنهادی و CTA بازنویسی کن",
        "confidence": "high",
        "evidence": [{"field": "call_to_action", "observed": "ندارد", "expected": "یک اقدام مشخص"}],
    }


def base_response():
    return {
        "success": True,
        "audit_version": 10,
        "profile_audit": {
            "score": 50,
            "issues": [profile_issue()],
            "strengths": [],
            "unavailable_checks": [],
        },
        "content_audit": {
            "score": 60,
            "issues": [],
            "patterns": [],
            "posts": [],
        },
        "growth_manager": {"legacy": True},
    }


def test_attach_growth_coach_is_additive():
    response = base_response()
    attach_growth_coach(response)

    assert response["success"] is True
    assert response["growth_manager"] == {"legacy": True}
    assert response["ai_growth_coach"]["status"] == "ready"
    assert response["ai_growth_coach"]["today_action"]["key"] == "profile:biography"


def test_enriched_response_copy_does_not_mutate_cached_payload():
    cached = base_response()
    enriched = enriched_response_copy(cached)

    assert "ai_growth_coach" not in cached
    assert "ai_growth_coach" in enriched


def test_completed_action_is_not_repeated():
    response = base_response()
    attach_growth_coach(response, completed_keys=["profile:biography"])

    assert response["ai_growth_coach"]["status"] == "no_action"
    assert response["ai_growth_coach"]["today_action"] is None

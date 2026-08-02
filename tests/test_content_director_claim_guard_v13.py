from growth.content_director_v13 import _normalize_result


def test_content_director_sanitizes_unsupported_percentage_and_guarantee_claims():
    context = {
        "next_content": {
            "goal": "increase_comments",
            "recommended_format": "carousel",
            "publish_time": {"time": "12:00", "timezone": "Asia/Tehran"},
        },
        "growth_director": {},
    }
    result = _normalize_result(
        {
            "caption": "این سرویس امنیت شما را تضمین می‌کند.",
            "slides": [
                {"text": "سرعت تا ۲۰٪ بهبود پیدا کرد"},
            ],
            "measurement": {
                "goal": "افزایش حداقل ۳۰٪ کامنت‌ها",
            },
        },
        context,
    )

    serialized = str(result)
    assert "۲۰٪" not in serialized
    assert "۳۰٪" not in serialized
    assert "امنیت شما را تضمین می‌کند" not in serialized
    assert result["quality_warnings"]

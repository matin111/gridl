import pytest

from planner_api import (
    PlannerDay,
    PlannerProfileContext,
    PlannerRequest,
    build_planner_input,
    normalize_planner_days,
    planner_json_schema,
)


def vpn_days():
    topics = [
        "انتخاب پروتکل مناسب VPN",
        "مقایسه WireGuard و OpenVPN",
        "نظرسنجی سرعت یا قطعی اتصال",
        "رفع خطای احراز هویت VPN",
        "خرید IP اختصاصی برای ترید",
        "حریم خصوصی در وای‌فای عمومی",
        "بازآفرینی آموزش پروتکل برتر هفته",
    ]
    formats = ["ریلز آموزشی", "کاروسل مقایسه‌ای", "استوری تعاملی", "ریلز حل مسئله", "پست فروش", "کاروسل اعتمادسازی", "ریلز مرور هفتگی"]
    return [
        {
            "day": number,
            "label": f"روز {number}",
            "title": f"{formats[number - 1]}: {topic}",
            "description": f"یک محتوای مستقل درباره {topic} منتشر کن.",
            "goal": f"هدف مستقل {number}",
            "content_type": formats[number - 1],
            "topic": topic,
            "best_time": "۲۰:۳۰",
            "tool": "content_studio",
            "tool_title": "استودیوی محتوا",
            "action_title": "ساخت محتوای کامل",
            "prompt": f"محتوای کامل VPN درباره {topic} بساز",
            "hook": f"هوک اختصاصی VPN شماره {number}",
            "short_script": f"سناریوی کامل شماره {number}: مشکل، راه‌حل و جمع‌بندی.",
            "caption": f"کپشن نهایی و مستقل VPN شماره {number}",
            "cta": f"دعوت به اقدام اختصاصی {number}",
            "publish_time": "۲۰:۳۰",
            "engagement_task": f"به پاسخ‌های مرتبط با روز {number} جواب بده",
            "kpi": f"تعداد ذخیره روز {number}",
            "hashtags": ["#VPN", "#WireGuard", "#امنیت"],
            "priority": "high",
            "estimated_minutes": 35,
        }
        for number, topic in enumerate(topics, start=1)
    ]


def test_seven_unique_complete_domain_specific_days():
    days = normalize_planner_days(vpn_days(), 7)

    assert len(days) == 7
    assert len({day.topic for day in days}) == 7
    assert len({day.hook for day in days}) == 7
    assert len({day.caption for day in days}) == 7
    assert len({day.cta for day in days}) == 7
    for day in days:
        assert all(
            getattr(day, field)
            for field in (
                "goal", "content_type", "topic", "hook", "short_script",
                "caption", "cta", "publish_time", "engagement_task", "kpi",
            )
        )
        assert day.actions == ["copy_full_content", "create_content", "add_to_calendar"]
    combined = " ".join(day.topic + day.short_script for day in days)
    assert "VPN" in combined and "WireGuard" in combined and "OpenVPN" in combined


@pytest.mark.parametrize("bad_title", ["نوشتن هوک", "بهبود کپشن", "publish previous post"])
def test_rejects_days_that_are_only_fragments(bad_title):
    raw = vpn_days()
    raw[2]["title"] = bad_title
    with pytest.raises(RuntimeError, match="اقدام ناقص"):
        normalize_planner_days(raw, 7)


def test_existing_android_schema_fields_remain_compatible():
    legacy = {
        "day", "label", "title", "description", "goal", "content_type",
        "topic", "best_time", "tool", "tool_title", "action_title", "prompt",
        "cta", "hashtags", "priority", "estimated_minutes", "completed",
    }
    assert legacy <= set(PlannerDay.model_fields)
    required = set(planner_json_schema(7)["properties"]["days"]["items"]["required"])
    assert legacy - {"completed"} <= required


def test_prompt_uses_domain_products_content_dna_and_recent_performance():
    request = PlannerRequest(
        business_field="فروش VPN",
        target_audience="تریدرها",
        profile=PlannerProfileContext(
            detected_domain="VPN",
            products=["IP اختصاصی"],
            content_dna={"tone": "فنی", "top_pillar": "آموزش"},
            recent_performance=[{"topic": "WireGuard", "saves": 42}],
        ),
    )
    prompt = build_planner_input(request)
    for signal in ("VPN", "IP اختصاصی", "top_pillar", "WireGuard", "تریدرها"):
        assert signal in prompt
    assert "هرگز یک محتوا را بین چند روز تقسیم نکن" in prompt

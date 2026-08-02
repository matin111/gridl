from __future__ import annotations

from typing import Any, Iterable, Mapping

from growth.priority_engine import build_growth_priorities


def _minutes_for(priority: Mapping[str, Any]) -> int:
    ease = int(priority.get("ease", 60) or 60)
    if ease >= 85:
        return 5
    if ease >= 70:
        return 15
    return 30


def _success_metric(priority: Mapping[str, Any]) -> str:
    key = str(priority.get("key", ""))
    title = str(priority.get("title", ""))
    if "biography" in key or "بیو" in title:
        return "در تحلیل بعدی، امتیاز بیو و وجود CTA دوباره بررسی شود."
    if "CTA" in title or "دعوت به اقدام" in title:
        return "نرخ کامنت پست بعدی را با میانگین پست‌های اخیر مقایسه کن."
    if "هوک" in title or "شروع کپشن" in title:
        return "عملکرد پست بعدی را با پست‌های دارای شروع عمومی مقایسه کن."
    if "هشتگ" in title:
        return "تغییر Reach فقط در صورت دسترسی به Insights اندازه‌گیری شود."
    return "در تحلیل بعدی، امتیاز این بخش و شواهد مرتبط دوباره مقایسه شود."


def build_ai_growth_coach(
    *,
    profile_audit: Mapping[str, Any] | None,
    content_audit: Mapping[str, Any] | None,
    completed_keys: Iterable[str] = (),
) -> dict[str, Any]:
    priorities = build_growth_priorities(
        profile_audit=profile_audit,
        content_audit=content_audit,
        limit=3,
        completed_keys=completed_keys,
    )

    if not priorities:
        return {
            "status": "no_action",
            "headline": "در داده‌های فعلی اقدام بحرانی پیدا نشد",
            "today_action": None,
            "next_priorities": [],
            "limitations": [
                "این تصمیم فقط بر اساس داده‌های عمومی موجود ساخته شده است",
            ],
        }

    first = priorities[0]
    today_action = {
        "key": first["key"],
        "title": first["title"],
        "instruction": first["recommendation"],
        "why": first["problem"],
        "evidence": first["evidence"],
        "priority_score": first["score"],
        "impact_score": first["impact"],
        "confidence_score": first["confidence"],
        "estimated_minutes": _minutes_for(first),
        "success_metric": _success_metric(first),
        "actionable": True,
    }

    return {
        "status": "ready",
        "headline": "اگر امروز فقط یک کار انجام می‌دهی، این مورد را انجام بده",
        "today_action": today_action,
        "next_priorities": priorities[1:],
        "decision_basis": {
            "formula": "impact × confidence × ease × urgency",
            "profile_audit_available": bool(profile_audit),
            "content_audit_available": bool(content_audit),
        },
        "limitations": [
            "اعداد اثر، امتیاز اولویت هستند و تضمین رشد درصدی نیستند",
            "Retention، Save، Share و تبدیل پروفایل فقط با داده واقعی Insights قابل سنجش‌اند",
        ],
    }

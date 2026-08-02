from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any, Mapping


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _posts(post_intelligence: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not post_intelligence:
        return []
    value = post_intelligence.get("posts")
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _performance(post: Mapping[str, Any]) -> float:
    return _number((post.get("performance") or {}).get("score"))


def _best_supported_format(posts: list[Mapping[str, Any]]) -> tuple[str | None, dict[str, Any]]:
    groups: dict[str, list[float]] = defaultdict(list)
    for post in posts:
        media_type = str(post.get("media_type") or "").strip().lower()
        if media_type:
            groups[media_type].append(_performance(post))
    eligible = {key: values for key, values in groups.items() if len(values) >= 2}
    if not eligible:
        return None, {"status": "insufficient_evidence", "samples": {k: len(v) for k, v in groups.items()}}
    selected = max(eligible, key=lambda key: mean(eligible[key]))
    return selected, {
        "status": "supported",
        "average_performance": round(mean(eligible[selected]), 2),
        "sample_size": len(eligible[selected]),
        "samples": {k: len(v) for k, v in groups.items()},
    }


def _best_supported_pillar(posts: list[Mapping[str, Any]]) -> tuple[str | None, dict[str, Any]]:
    groups: dict[str, list[float]] = defaultdict(list)
    for post in posts:
        pillar = str(post.get("content_pillar") or "").strip().lower()
        if pillar and pillar != "general":
            groups[pillar].append(_performance(post))
    eligible = {key: values for key, values in groups.items() if len(values) >= 2}
    if not eligible:
        return None, {"status": "insufficient_evidence", "samples": {k: len(v) for k, v in groups.items()}}
    selected = max(eligible, key=lambda key: mean(eligible[key]))
    return selected, {
        "status": "supported",
        "average_performance": round(mean(eligible[selected]), 2),
        "sample_size": len(eligible[selected]),
        "samples": {k: len(v) for k, v in groups.items()},
    }


def _hook_strategy(posts: list[Mapping[str, Any]]) -> dict[str, Any]:
    strong = [post for post in posts if str((post.get("performance") or {}).get("label")) == "strong"]
    if len(strong) < 2:
        ranked = sorted(posts, key=_performance, reverse=True)[:3]
        strong = ranked if len(ranked) >= 2 else []
    hook_types = [
        str((post.get("hook") or {}).get("type") or "").strip()
        for post in strong
        if str((post.get("hook") or {}).get("type") or "").strip()
    ]
    if not hook_types:
        return {
            "type": "direct_result",
            "instruction": "نتیجه یا مسئله اصلی را در جمله اول بدون مقدمه بیان کن.",
            "source": "best_practice_fallback",
            "evidence_post_ids": [],
        }
    selected, count = Counter(hook_types).most_common(1)[0]
    evidence_ids = [
        str(post.get("post_id") or "")
        for post in strong
        if str((post.get("hook") or {}).get("type") or "").strip() == selected
    ]
    return {
        "type": selected,
        "instruction": "ساختار هوک پست‌های قوی‌تر همین پیج را حفظ کن، اما متن جدید و متناسب با موضوع بعدی بنویس.",
        "source": "page_performance" if count >= 2 else "limited_page_signal",
        "evidence_post_ids": evidence_ids,
    }


def _cta_strategy(daily_mission: Mapping[str, Any] | None) -> dict[str, Any]:
    mission = daily_mission or {}
    key = str(mission.get("key") or "").lower()
    title = str(mission.get("title") or "")
    instruction = str(mission.get("instruction") or mission.get("action") or "").strip()
    if "cta" in key or "CTA" in title or "دعوت" in title:
        return {
            "goal": "increase_comments",
            "instruction": instruction or "در پایان فقط یک اقدام روشن برای کامنت یا پیام درخواست کن.",
            "recommended_cta": "یک سؤال مشخص و ساده بپرس که مخاطب بتواند با یک پاسخ کوتاه جواب بدهد.",
            "source": "daily_mission",
        }
    return {
        "goal": "increase_saves",
        "instruction": "در پایان فقط یک اقدام مشخص و متناسب با ارزش محتوا درخواست کن.",
        "recommended_cta": "اگر این نکته برایت کاربردی بود، ذخیره‌اش کن.",
        "source": "safe_fallback",
    }


def _cover_strategy(post_intelligence: Mapping[str, Any] | None) -> dict[str, Any]:
    posts = _posts(post_intelligence)
    action_counts: Counter[str] = Counter()
    evidence: dict[str, list[str]] = defaultdict(list)
    analyzed = 0
    for post in posts:
        review = post.get("visual_review") or {}
        if review.get("status") != "ready":
            continue
        analyzed += 1
        for action in review.get("actions", []) or []:
            text = str(action).strip()
            if text:
                action_counts[text] += 1
                evidence[text].append(str(post.get("post_id") or ""))
    repeated = [item for item, count in action_counts.most_common() if count >= 2][:3]
    if repeated:
        return {
            "status": "page_evidence",
            "rules": repeated,
            "analyzed_covers": analyzed,
            "evidence": [
                {"rule": item, "affected_posts": action_counts[item], "post_ids": evidence[item]}
                for item in repeated
            ],
        }
    return {
        "status": "safe_defaults",
        "rules": [
            "تیتر کوتاه و خوانا برای نمایش موبایل استفاده کن.",
            "فقط یک نقطه کانونی اصلی داشته باش.",
            "متن و پس‌زمینه کنتراست کافی داشته باشند.",
        ],
        "analyzed_covers": analyzed,
        "evidence": [],
    }


def _publish_time(analytics: Mapping[str, Any] | None) -> dict[str, Any]:
    analytics = analytics or {}
    value = analytics.get("suggested_publish_time")
    timezone = analytics.get("suggested_publish_timezone") or "UTC"
    if value:
        return {
            "time": value,
            "timezone": timezone,
            "source": "page_publish_history",
            "explanation": analytics.get("suggested_publish_explanation"),
        }
    return {
        "time": None,
        "timezone": timezone,
        "source": "unavailable",
        "explanation": "برای پیشنهاد زمان انتشار، داده زمانی کافی در دسترس نیست.",
    }


def build_next_content(
    *,
    post_intelligence: Mapping[str, Any] | None,
    daily_mission: Mapping[str, Any] | None,
    analytics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    posts = _posts(post_intelligence)
    content_format, format_basis = _best_supported_format(posts)
    pillar, pillar_basis = _best_supported_pillar(posts)
    hook = _hook_strategy(posts)
    cta = _cta_strategy(daily_mission)
    cover = _cover_strategy(post_intelligence)

    evidence_count = sum(
        1
        for basis in (format_basis, pillar_basis)
        if basis.get("status") == "supported"
    ) + (1 if hook.get("source") == "page_performance" else 0) + (1 if cover.get("status") == "page_evidence" else 0)

    return {
        "version": "12.1",
        "status": "ready" if posts else "insufficient_data",
        "goal": cta["goal"],
        "recommended_format": content_format,
        "content_pillar": pillar,
        "topic_direction": (
            "یک موضوع تازه و کاربردی از حوزه واقعی پیج انتخاب کن که با ستون محتوایی پیشنهادی هماهنگ باشد."
            if pillar
            else "یک مسئله پرتکرار و واقعی مخاطبان همین پیج را انتخاب کن؛ موضوع نباید عمومی یا نامرتبط باشد."
        ),
        "hook_strategy": hook,
        "scenario_blueprint": [
            {"step": 1, "purpose": "توقف اسکرول", "instruction": hook["instruction"]},
            {"step": 2, "purpose": "تعریف مسئله", "instruction": "مشکل مخاطب را در یک جمله روشن و قابل لمس توضیح بده."},
            {"step": 3, "purpose": "ارائه ارزش", "instruction": "سه نکته کوتاه، مشخص و قابل اجرا ارائه کن."},
            {"step": 4, "purpose": "اثبات", "instruction": "یک مثال، مقایسه یا نتیجه واقعی نشان بده؛ ادعای بدون شواهد نساز."},
            {"step": 5, "purpose": "دعوت به اقدام", "instruction": cta["instruction"]},
        ],
        "cover_strategy": cover,
        "caption_strategy": {
            "structure": ["هوک کوتاه", "توضیح مسئله", "نکات عملی", "یک CTA روشن"],
            "instruction": "کپشن را متناسب با موضوع واقعی پیج بنویس و از متن‌های عمومی یا هشتگ‌های نامرتبط خودداری کن.",
        },
        "cta_strategy": cta,
        "hashtag_strategy": {
            "instruction": "یک مجموعه کوتاه از هشتگ‌های تخصصی همان موضوع و حوزه پیج بساز؛ هشتگ عمومی نامرتبط اضافه نکن.",
            "hashtags": [],
            "status": "requires_domain_topic",
        },
        "publish_time": _publish_time(analytics),
        "why_this": {
            "summary": "این بریف از مأموریت روز، عملکرد پست‌های قبلی و بررسی واقعی کاورها ساخته شده است.",
            "format_basis": format_basis,
            "pillar_basis": pillar_basis,
            "evidence_signals": evidence_count,
        },
        "confidence": "high" if evidence_count >= 3 else "medium" if evidence_count >= 1 else "low",
        "limitations": [
            "تا زمانی که موضوع دقیق و حوزه پیج به مولد متن ارسال نشود، متن نهایی کپشن و هشتگ تولید نمی‌شود.",
            "این خروجی یک بریف محتوایی مبتنی بر شواهد است و تضمین عملکرد آینده نیست.",
        ],
    }

from __future__ import annotations

import json
import os
import re
from typing import Any, Mapping

import httpx
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_CONTENT_MODEL = os.getenv("OPENAI_CONTENT_MODEL", os.getenv("OPENAI_TEXT_MODEL", "gpt-4.1-mini")).strip()
CONTENT_DIRECTOR_TIMEOUT = float(os.getenv("CONTENT_DIRECTOR_TIMEOUT", "60"))


_PERCENT_CLAIM_RE = re.compile(
    r"(?:حداقل\s*)?[۰-۹0-9]+(?:[٫.,][۰-۹0-9]+)?\s*٪(?:\s*(?:افزایش|بهبود|کاهش))?",
    re.IGNORECASE,
)
_GUARANTEE_REPLACEMENTS = {
    "امنیت شما را تضمین می‌کند": "برای افزایش امنیت اتصال طراحی شده است",
    "امنیت شما را تضمین می کند": "برای افزایش امنیت اتصال طراحی شده است",
    "امنیت تضمین شد": "تنظیمات امنیتی تقویت شد",
    "تضمین می‌کند": "می‌تواند کمک‌کننده باشد",
    "تضمین می کند": "می‌تواند کمک‌کننده باشد",
    "تضمینی": "قطعی",
    "تضمین": "اطمینان قطعی",
}


def _compact_posts(post_intelligence: Mapping[str, Any] | None, limit: int = 6) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    posts = (post_intelligence or {}).get("posts") or []
    for post in posts[:limit]:
        if not isinstance(post, Mapping):
            continue
        result.append({
            "post_id": post.get("post_id"),
            "media_type": post.get("media_type"),
            "content_pillar": post.get("content_pillar"),
            "hook": post.get("hook"),
            "performance": post.get("performance"),
            "visual_review": post.get("visual_review"),
        })
    return result


def build_content_director_context(
    *,
    profile: Mapping[str, Any] | None,
    analytics: Mapping[str, Any] | None,
    growth_director: Mapping[str, Any] | None,
    post_intelligence: Mapping[str, Any] | None,
    content_audit: Mapping[str, Any] | None,
) -> dict[str, Any]:
    profile = profile or {}
    analytics = analytics or {}
    growth_director = growth_director or {}
    next_content = growth_director.get("next_content") or {}
    return {
        "profile": {
            "username": profile.get("username"),
            "full_name": profile.get("full_name"),
            "biography": profile.get("biography"),
            "followers_count": profile.get("followers_count"),
        },
        "analytics": {
            "best_content_type": analytics.get("best_content_type"),
            "suggested_publish_time": analytics.get("suggested_publish_time"),
            "suggested_publish_timezone": analytics.get("suggested_publish_timezone"),
            "average_likes": analytics.get("average_likes"),
            "average_comments": analytics.get("average_comments"),
            "average_views": analytics.get("average_views"),
        },
        "growth_director": {
            "health_score": growth_director.get("health_score"),
            "growth_stage": growth_director.get("growth_stage"),
            "daily_mission": growth_director.get("daily_mission"),
            "top_priorities": growth_director.get("top_priorities"),
            "risk_alerts": growth_director.get("risk_alerts"),
        },
        "next_content": next_content,
        "content_audit": {
            "score": (content_audit or {}).get("score"),
            "content_mix": (content_audit or {}).get("content_mix"),
            "priority_issues": (content_audit or {}).get("priority_issues"),
        },
        "representative_posts": _compact_posts(post_intelligence),
    }


def _fallback_payload(context: Mapping[str, Any], reason: str) -> dict[str, Any]:
    next_content = context.get("next_content") or {}
    publish_time = next_content.get("publish_time") or {}
    return {
        "version": 13,
        "status": "brief_only",
        "provider": None,
        "model": None,
        "content_goal": next_content.get("goal"),
        "content_type": next_content.get("recommended_format"),
        "topic": None,
        "title": None,
        "hook": None,
        "scenario": next_content.get("scenario") or next_content.get("scenario_blueprint") or [],
        "slides": [],
        "caption": None,
        "cta": next_content.get("cta") or next_content.get("cta_strategy"),
        "hashtags": [],
        "first_comment": None,
        "cover": next_content.get("cover_strategy"),
        "publish_plan": publish_time,
        "measurement": {
            "primary_metric": next_content.get("goal"),
            "how_to_measure": ((context.get("growth_director") or {}).get("daily_mission") or {}).get("success_metric"),
        },
        "evidence": next_content.get("evidence") or next_content.get("why_this"),
        "limitations": [reason, "محتوای نهایی فقط پس از دریافت خروجی معتبر مدل آماده انتشار است."],
    }


def _extract_output_text(payload: Mapping[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return str(payload["output_text"])
    for item in payload.get("output", []) or []:
        if not isinstance(item, Mapping):
            continue
        for content in item.get("content", []) or []:
            if isinstance(content, Mapping) and isinstance(content.get("text"), str):
                return str(content["text"])
    return ""


def _sanitize_text(value: str, warnings: list[str]) -> str:
    text = value
    if _PERCENT_CLAIM_RE.search(text):
        text = _PERCENT_CLAIM_RE.sub("بهبود احتمالی", text)
        warnings.append("ادعای درصدی بدون شواهد حذف شد")
    for source, replacement in _GUARANTEE_REPLACEMENTS.items():
        if source in text:
            text = text.replace(source, replacement)
            warnings.append("عبارت تضمینی بدون شواهد تعدیل شد")
    return text


def _sanitize_generated(value: Any, warnings: list[str]) -> Any:
    if isinstance(value, str):
        return _sanitize_text(value, warnings)
    if isinstance(value, list):
        return [_sanitize_generated(item, warnings) for item in value]
    if isinstance(value, Mapping):
        return {key: _sanitize_generated(item, warnings) for key, item in value.items()}
    return value


def _normalize_result(data: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    next_content = context.get("next_content") or {}
    publish_time = next_content.get("publish_time") or {}
    warnings: list[str] = []
    result = dict(_sanitize_generated(dict(data), warnings))
    result.update({
        "version": 13,
        "status": "ready",
        "provider": "openai",
        "model": OPENAI_CONTENT_MODEL,
        "content_goal": result.get("content_goal") or next_content.get("goal"),
        "content_type": result.get("content_type") or next_content.get("recommended_format"),
        "publish_plan": result.get("publish_plan") or publish_time,
        "evidence": result.get("evidence") or next_content.get("evidence") or next_content.get("why_this"),
    })
    result.setdefault("slides", [])
    result.setdefault("scenario", [])
    result.setdefault("hashtags", [])
    result.setdefault("limitations", ["این پیشنهاد تضمین رشد نیست و باید با نتیجه واقعی انتشار ارزیابی شود."])
    result["quality_warnings"] = list(dict.fromkeys(warnings))
    return result


async def generate_content_director(
    *,
    profile: Mapping[str, Any] | None,
    analytics: Mapping[str, Any] | None,
    growth_director: Mapping[str, Any] | None,
    post_intelligence: Mapping[str, Any] | None,
    content_audit: Mapping[str, Any] | None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    context = build_content_director_context(
        profile=profile,
        analytics=analytics,
        growth_director=growth_director,
        post_intelligence=post_intelligence,
        content_audit=content_audit,
    )

    if not OPENAI_API_KEY:
        return _fallback_payload(context, "OPENAI_API_KEY تنظیم نشده است.")

    instructions = (
        "تو کارگردان محتوای حرفه‌ای اینستاگرام هستی. فقط یک محتوای منسجم، اختصاصی و آماده انتشار تولید کن. "
        "خروجی باید فارسی، طبیعی، غیرعمومی و دقیقاً متناسب با حوزه واقعی پیج باشد. "
        "هیچ درصد رشد، افزایش سرعت، بهبود فروش، نتیجه قطعی، تضمین امنیت یا ادعای عددی نساز مگر آن عدد صریحاً در context به‌عنوان شاهد معتبر آمده باشد. "
        "برای measurement فقط روش مقایسه با میانگین اخیر را بنویس و هدف درصدی تعیین نکن. "
        "درباره امنیت سایبری از واژه‌هایی مانند تضمین، کاملاً امن یا بدون نشت استفاده نکن؛ نتیجه به سرویس، تنظیمات، دستگاه و شبکه وابسته است. "
        "از هشتگ عمومی نامرتبط و تکرار متن‌های نمونه خودداری کن. "
        "اگر فرمت carousel است، 6 تا 8 اسلاید کامل بده. اگر reel است، سناریوی زمان‌بندی‌شده بده. "
        "خروجی فقط JSON معتبر باشد با کلیدهای: content_goal, content_type, topic, title, hook, scenario, slides, caption, cta, hashtags, first_comment, cover, publish_plan, measurement, evidence, limitations."
    )
    body = {
        "model": OPENAI_CONTENT_MODEL,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": instructions}]},
            {"role": "user", "content": [{"type": "input_text", "text": json.dumps(context, ensure_ascii=False)}]},
        ],
        "temperature": 0.7,
    }

    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=CONTENT_DIRECTOR_TIMEOUT)
    try:
        response = await http_client.post(
            f"{OPENAI_BASE_URL}/responses",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json=body,
        )
        response.raise_for_status()
        payload = response.json()
        text = _extract_output_text(payload).strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lstrip().startswith("json"):
                text = text.lstrip()[4:].lstrip()
        data = json.loads(text)
        if not isinstance(data, Mapping):
            raise ValueError("Content Director response is not a JSON object")
        return _normalize_result(data, context)
    except Exception as error:
        return _fallback_payload(context, f"تولید محتوای نهایی ناموفق بود: {type(error).__name__}")
    finally:
        if owns_client:
            await http_client.aclose()

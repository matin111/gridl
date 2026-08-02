from __future__ import annotations

from typing import Any, Mapping


_FACE_TERMS = ("چهره", "انسانی", "صورت")


def _score_label(score: int | None) -> str:
    if score is None:
        return "نامشخص"
    if score >= 85:
        return "عالی"
    if score >= 70:
        return "خوب"
    if score >= 55:
        return "متوسط"
    return "نیازمند بهبود"


def _safe_list(value: Any, limit: int = 5) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text[:300])
        if len(result) >= limit:
            break
    return result


def _remove_generic_face_advice(items: list[str], face_detected: Any) -> list[str]:
    """Absence of a face is neutral unless page-level evidence proves otherwise."""
    if face_detected is not False:
        return items
    return [item for item in items if not any(term in item for term in _FACE_TERMS)]


def build_visual_review(visual: Mapping[str, Any] | None) -> dict[str, Any]:
    if not visual:
        return {
            "status": "unavailable",
            "headline": "تحلیل تصویری در دسترس نیست",
            "summary": "برای این پست تصویر قابل تحلیل دریافت نشد.",
            "strengths": [],
            "improvements": [],
            "actions": [],
            "evidence": [],
        }

    status = str(visual.get("status") or "unavailable")
    if status != "completed":
        reason = str(visual.get("reason") or "visual_analysis_not_completed")
        return {
            "status": status,
            "headline": "تحلیل تصویری کامل نشده است",
            "summary": "امتیاز تصویری فقط پس از بررسی واقعی کاور نمایش داده می‌شود.",
            "strengths": [],
            "improvements": [],
            "actions": [],
            "evidence": [{"metric": "status", "value": status, "source": reason}],
        }

    cover = visual.get("cover_score")
    scroll = visual.get("scroll_stop_score")
    readability = visual.get("text_readability")
    contrast = visual.get("contrast_score")
    composition = visual.get("composition_score")
    brand = visual.get("brand_consistency_score")
    face = visual.get("face_detected")
    ocr_text = str(visual.get("ocr_text") or "").strip()

    evidence: list[dict[str, Any]] = []
    for metric, value in (
        ("cover_score", cover),
        ("scroll_stop_score", scroll),
        ("text_readability", readability),
        ("contrast_score", contrast),
        ("composition_score", composition),
        ("brand_consistency_score", brand),
        ("face_detected", face),
    ):
        if value is not None:
            evidence.append({"metric": metric, "value": value, "source": "openai_vision"})
    if ocr_text:
        evidence.append({"metric": "ocr_text", "value": ocr_text[:300], "source": "openai_vision"})

    strengths = _safe_list(visual.get("strengths"))
    improvements = _remove_generic_face_advice(_safe_list(visual.get("weaknesses")), face)
    actions = _remove_generic_face_advice(_safe_list(visual.get("recommendations")), face)

    if not strengths:
        if isinstance(readability, (int, float)) and readability >= 75:
            strengths.append("متن روی کاور برای نمایش موبایل خواناست")
        if isinstance(contrast, (int, float)) and contrast >= 75:
            strengths.append("کنتراست عناصر اصلی مناسب است")
        if isinstance(composition, (int, float)) and composition >= 75:
            strengths.append("ترکیب‌بندی تصویر منظم و قابل دنبال‌کردن است")

    if not improvements:
        if isinstance(readability, (int, float)) and readability < 60:
            improvements.append("خوانایی متن روی کاور پایین است")
        if isinstance(contrast, (int, float)) and contrast < 60:
            improvements.append("کنتراست سوژه و پس‌زمینه کافی نیست")
        if isinstance(composition, (int, float)) and composition < 60:
            improvements.append("نقطه کانونی و سلسله‌مراتب بصری واضح نیست")
        if isinstance(brand, (int, float)) and brand < 55:
            improvements.append("نشانه‌های هویت بصری برند ضعیف یا ناهماهنگ هستند")

    if not actions:
        if isinstance(readability, (int, float)) and readability < 60:
            actions.append("اندازه تیتر را بزرگ‌تر و تعداد کلمات روی کاور را کمتر کن")
        if isinstance(contrast, (int, float)) and contrast < 60:
            actions.append("برای تیتر یا سوژه از رنگ متضادتر استفاده کن")
        if isinstance(composition, (int, float)) and composition < 60:
            actions.append("یک نقطه کانونی اصلی انتخاب و عناصر فرعی را حذف کن")

    summary_parts: list[str] = []
    if isinstance(cover, (int, float)):
        summary_parts.append(f"کیفیت کلی کاور {_score_label(int(cover))} است")
    if isinstance(scroll, (int, float)):
        summary_parts.append(f"قدرت توقف اسکرول {_score_label(int(scroll))} ارزیابی شد")
    # Face presence is retained in evidence but is not presented as good or bad.
    if face is True:
        summary_parts.append("عنصر انسانی در تصویر دیده می‌شود")

    return {
        "status": "ready",
        "headline": "بررسی حرفه‌ای کاور",
        "summary": "؛ ".join(summary_parts) + ("." if summary_parts else ""),
        "cover_score": cover,
        "scroll_stop_score": scroll,
        "strengths": strengths,
        "improvements": improvements,
        "actions": actions,
        "evidence": evidence,
        "ocr_text": ocr_text or None,
    }


def attach_visual_reviews(post_intelligence: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if post_intelligence is None:
        return None
    result = dict(post_intelligence)
    posts = result.get("posts")
    if not isinstance(posts, list):
        return result

    reviewed: list[dict[str, Any]] = []
    for post in posts:
        if not isinstance(post, Mapping):
            continue
        item = dict(post)
        item["visual_review"] = build_visual_review(item.get("visual"))
        reviewed.append(item)
    result["posts"] = reviewed
    result["visual_reviews_ready"] = sum(
        1 for post in reviewed if (post.get("visual_review") or {}).get("status") == "ready"
    )
    return result

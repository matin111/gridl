from __future__ import annotations

from statistics import median
from typing import Any, Iterable, Mapping

from growth.content_audit import audit_post


def _read(item: object | Mapping[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _performance_label(score: float, page_median: float) -> str:
    if page_median <= 0:
        return "unknown"
    ratio = score / page_median
    if ratio >= 1.5:
        return "strong"
    if ratio <= 0.65:
        return "weak"
    return "average"


def _observed_evidence(audit: Mapping[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    evidence.append({
        "metric": "hook_score",
        "value": audit.get("hook_score", 0),
        "source": "caption_first_line",
    })
    evidence.append({
        "metric": "caption_score",
        "value": audit.get("caption_score", 0),
        "source": "caption_text",
    })
    evidence.append({
        "metric": "hashtag_score",
        "value": audit.get("hashtag_score", 0),
        "source": "caption_hashtags",
    })
    evidence.append({
        "metric": "cta_present",
        "value": bool(audit.get("cta_present")),
        "source": "caption_text",
    })
    return evidence


def build_post_intelligence(media: Iterable[object | Mapping[str, Any]]) -> dict[str, Any]:
    """Build a factual per-post dossier from data currently available.

    Visual claims are intentionally marked unavailable until an image has been
    fetched and analysed by a vision model. This prevents caption-only analysis
    from pretending to know cover quality, faces, OCR, contrast, or composition.
    """
    raw_items = list(media)
    audited = [audit_post(item) for item in raw_items]
    performances = [float(item.get("performance_score", 0) or 0) for item in audited]
    page_median = median(performances) if performances else 0.0

    posts: list[dict[str, Any]] = []
    for raw, audit in zip(raw_items, audited):
        thumbnail_url = str(_read(raw, "thumbnail_url", "") or "")
        performance_score = float(audit.get("performance_score", 0) or 0)
        posts.append({
            "post_id": audit.get("post_id", ""),
            "permalink": audit.get("permalink"),
            "thumbnail_url": thumbnail_url or None,
            "published_at": audit.get("published_at"),
            "media_type": audit.get("media_type", "unknown"),
            "content_pillar": audit.get("content_pillar", "general"),
            "hook": {
                "text": audit.get("hook_text", ""),
                "type": audit.get("hook_type", "statement"),
                "score": audit.get("hook_score", 0),
            },
            "caption": {
                "score": audit.get("caption_score", 0),
                "cta_present": bool(audit.get("cta_present")),
                "hashtags": list(audit.get("hashtags", []) or []),
                "hashtag_score": audit.get("hashtag_score", 0),
            },
            "performance": {
                "score": round(performance_score, 2),
                "page_median": round(page_median, 2),
                "label": _performance_label(performance_score, page_median),
            },
            "visual": {
                "status": "pending" if thumbnail_url else "unavailable",
                "cover_score": None,
                "scroll_stop_score": None,
                "ocr_text": None,
                "face_detected": None,
                "text_readability": None,
                "contrast_score": None,
                "composition_score": None,
                "reason": (
                    "thumbnail_ready_for_vision"
                    if thumbnail_url
                    else "thumbnail_url_not_available"
                ),
            },
            "strengths": list(audit.get("strengths", []) or []),
            "weaknesses": list(audit.get("issues", []) or []),
            "evidence": _observed_evidence(audit),
            "limitations": list(audit.get("limitations", []) or []),
        })

    return {
        "version": 11,
        "analyzed_posts": len(posts),
        "page_median_performance": round(page_median, 2),
        "posts": posts,
        "visual_analysis_ready": sum(1 for post in posts if post["visual"]["status"] == "pending"),
        "limitations": [
            "Cover, face, OCR, colour, contrast and composition require actual image analysis.",
            "Public likes, comments and views do not include saves, shares, reach or retention.",
            "Performance labels are relative to the analysed posts of the same page.",
        ],
    }

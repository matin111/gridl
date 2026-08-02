from __future__ import annotations

from statistics import mean
from typing import Any, Mapping


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: Any) -> int:
    return max(0, min(round(_number(value)), 100))


def _stage(score: int) -> str:
    if score >= 85:
        return "optimized"
    if score >= 70:
        return "growing"
    if score >= 50:
        return "developing"
    return "foundation"


def _visual_score(post_intelligence: Mapping[str, Any] | None) -> tuple[int | None, int]:
    if not post_intelligence:
        return None, 0
    values: list[float] = []
    for post in post_intelligence.get("posts", []) or []:
        if not isinstance(post, Mapping):
            continue
        visual = post.get("visual") or {}
        if visual.get("status") != "completed":
            continue
        value = visual.get("cover_score")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return (round(mean(values)), len(values)) if values else (None, 0)


def _performance_score(post_intelligence: Mapping[str, Any] | None) -> int | None:
    if not post_intelligence:
        return None
    values: list[float] = []
    for post in post_intelligence.get("posts", []) or []:
        if not isinstance(post, Mapping):
            continue
        performance = post.get("performance") or {}
        value = performance.get("score")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return _clamp(mean(values)) if values else None


def _health_score(
    *,
    profile_audit: Mapping[str, Any] | None,
    content_audit: Mapping[str, Any] | None,
    post_intelligence: Mapping[str, Any] | None,
) -> tuple[int, dict[str, Any]]:
    components: list[tuple[str, int, float]] = []
    if profile_audit and profile_audit.get("score") is not None:
        components.append(("profile", _clamp(profile_audit.get("score")), 0.20))
    if content_audit and content_audit.get("score") is not None:
        components.append(("content", _clamp(content_audit.get("score")), 0.30))

    visual, visual_samples = _visual_score(post_intelligence)
    if visual is not None:
        components.append(("visual", visual, 0.20))

    performance = _performance_score(post_intelligence)
    if performance is not None:
        components.append(("performance", performance, 0.20))

    consistency = None
    if content_audit:
        consistency = content_audit.get("posting_consistency_score")
    if consistency is not None:
        components.append(("consistency", _clamp(consistency), 0.10))

    weight_total = sum(weight for _, _, weight in components)
    score = round(sum(value * weight for _, value, weight in components) / weight_total) if weight_total else 0
    return score, {
        "components": {name: value for name, value, _ in components},
        "normalized_weight_total": round(weight_total, 2),
        "visual_sample_size": visual_samples,
    }


def _priority_items(ai_growth_coach: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not ai_growth_coach:
        return []
    items: list[dict[str, Any]] = []
    today = ai_growth_coach.get("today_action")
    if isinstance(today, Mapping):
        items.append({
            "key": today.get("key"),
            "title": today.get("title"),
            "action": today.get("instruction"),
            "reason": today.get("why"),
            "evidence": list(today.get("evidence") or []),
            "impact_score": _clamp(today.get("impact_score")),
            "confidence_score": _clamp(today.get("confidence_score")),
            "priority_score": _clamp(today.get("priority_score")),
            "estimated_minutes": int(_number(today.get("estimated_minutes"), 15)),
            "success_metric": today.get("success_metric"),
        })
    for item in ai_growth_coach.get("next_priorities", []) or []:
        if not isinstance(item, Mapping):
            continue
        items.append({
            "key": item.get("key"),
            "title": item.get("title"),
            "action": item.get("recommendation"),
            "reason": item.get("problem"),
            "evidence": list(item.get("evidence") or []),
            "impact_score": _clamp(item.get("impact")),
            "confidence_score": _clamp(item.get("confidence")),
            "priority_score": _clamp(item.get("score")),
            "estimated_minutes": 15,
            "success_metric": None,
        })
    return items[:3]


def _visual_risks(post_intelligence: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not post_intelligence:
        return []
    counts: dict[str, int] = {}
    analyzed = 0
    for post in post_intelligence.get("posts", []) or []:
        if not isinstance(post, Mapping):
            continue
        review = post.get("visual_review") or {}
        if review.get("status") != "ready":
            continue
        analyzed += 1
        for problem in review.get("improvements", []) or []:
            text = str(problem).strip()
            if text:
                counts[text] = counts.get(text, 0) + 1
    if analyzed < 3:
        return []
    risks = []
    for problem, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True):
        if count < 2:
            continue
        risks.append({
            "type": "visual_repetition",
            "title": problem,
            "affected_posts": count,
            "analyzed_posts": analyzed,
            "evidence": f"این مورد در {count} پست از {analyzed} کاور تحلیل‌شده تکرار شده است",
        })
    return risks[:3]


def build_growth_director(
    *,
    profile_audit: Mapping[str, Any] | None,
    content_audit: Mapping[str, Any] | None,
    post_intelligence: Mapping[str, Any] | None,
    ai_growth_coach: Mapping[str, Any] | None,
) -> dict[str, Any]:
    health_score, health_basis = _health_score(
        profile_audit=profile_audit,
        content_audit=content_audit,
        post_intelligence=post_intelligence,
    )
    priorities = _priority_items(ai_growth_coach)
    mission = priorities[0] if priorities else None
    risks = _visual_risks(post_intelligence)

    profile_summary = str((profile_audit or {}).get("summary") or "").strip()
    content_issues = (content_audit or {}).get("priority_issues", []) or []
    main_bottleneck = mission.get("title") if mission else (
        content_issues[0].get("issue") if content_issues and isinstance(content_issues[0], Mapping) else None
    )

    strengths = (profile_audit or {}).get("strengths", []) or []
    main_strength = None
    if strengths and isinstance(strengths[0], Mapping):
        main_strength = strengths[0].get("title")

    confidence_values = [item["confidence_score"] for item in priorities if item.get("confidence_score")]
    confidence = round(mean(confidence_values)) if confidence_values else 0

    return {
        "version": 12,
        "status": "ready" if any((profile_audit, content_audit, post_intelligence, ai_growth_coach)) else "insufficient_data",
        "health_score": health_score,
        "growth_stage": _stage(health_score),
        "executive_summary": {
            "headline": "مهم‌ترین وضعیت و اقدام رشد پیج",
            "profile_summary": profile_summary or None,
            "main_strength": main_strength,
            "main_bottleneck": main_bottleneck,
            "summary": (
                f"امتیاز سلامت پیج {health_score} از ۱۰۰ است. "
                + (f"اولویت اصلی فعلی: {main_bottleneck}." if main_bottleneck else "برای تعیین اولویت اصلی داده بیشتری لازم است.")
            ),
        },
        "daily_mission": mission,
        "top_priorities": priorities,
        "risk_alerts": risks,
        "confidence_score": confidence,
        "decision_basis": {
            "health": health_basis,
            "profile_audit_available": bool(profile_audit),
            "content_audit_available": bool(content_audit),
            "post_intelligence_available": bool(post_intelligence),
            "growth_coach_available": bool(ai_growth_coach),
        },
        "limitations": [
            "امتیاز سلامت از داده‌های در دسترس نرمال‌سازی می‌شود و معیار رسمی اینستاگرام نیست",
            "اثر آینده تضمین نمی‌شود و باید در تحلیل‌های بعدی با داده واقعی مقایسه شود",
            "Reach، Saves، Shares و Retention فقط با دسترسی به Insights قابل سنجش‌اند",
        ],
    }

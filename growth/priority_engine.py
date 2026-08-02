from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class GrowthPriority:
    key: str
    title: str
    source: str
    problem: str
    evidence: tuple[str, ...]
    recommendation: str
    impact: int
    confidence: int
    ease: int
    urgency: int
    score: int

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = list(self.evidence)
        return data


def _clamp(value: int | float) -> int:
    return max(0, min(round(float(value)), 100))


def _priority_score(*, impact: int, confidence: int, ease: int, urgency: int) -> int:
    return _clamp(
        impact * 0.42
        + confidence * 0.28
        + ease * 0.18
        + urgency * 0.12
    )


def _confidence_value(value: str | int | float | None) -> int:
    if isinstance(value, (int, float)):
        return _clamp(value)
    return {
        "high": 92,
        "medium": 72,
        "low": 48,
    }.get(str(value or "").lower(), 60)


def _profile_priorities(profile_audit: Mapping[str, Any] | None) -> list[GrowthPriority]:
    if not profile_audit:
        return []

    result: list[GrowthPriority] = []
    for issue in profile_audit.get("issues", []) or []:
        issue_score = _clamp(issue.get("score", 50))
        impact = _clamp(100 - issue_score)
        confidence = _confidence_value(issue.get("confidence"))
        severity = str(issue.get("severity", "medium"))
        urgency = {
            "critical": 100,
            "high": 88,
            "medium": 68,
            "low": 42,
            "info": 20,
        }.get(severity, 60)
        key = str(issue.get("key", "profile"))
        ease = 92 if key in {"biography", "display_name", "username"} else 75
        evidence = tuple(
            f"{item.get('field', 'field')}: {item.get('observed', '')}"
            for item in (issue.get("evidence", []) or [])
        )
        result.append(
            GrowthPriority(
                key=f"profile:{key}",
                title=str(issue.get("title", "اصلاح پروفایل")),
                source="profile_audit",
                problem=str(issue.get("explanation", "")),
                evidence=evidence,
                recommendation=str(issue.get("recommendation", "")),
                impact=impact,
                confidence=confidence,
                ease=ease,
                urgency=urgency,
                score=_priority_score(
                    impact=impact,
                    confidence=confidence,
                    ease=ease,
                    urgency=urgency,
                ),
            )
        )
    return result


def _content_category(problem: str) -> str:
    if "CTA" in problem or "دعوت به اقدام" in problem:
        return "cta"
    if "هوک" in problem or "شروع کپشن" in problem:
        return "hook"
    if "کپشن" in problem:
        return "caption"
    if "هشتگ" in problem:
        return "hashtag"
    return "general"


def _content_priorities(content_audit: Mapping[str, Any] | None) -> list[GrowthPriority]:
    if not content_audit:
        return []

    analyzed_posts = max(int(content_audit.get("analyzed_posts", 0) or 0), 0)
    confidence = 90 if analyzed_posts >= 12 else 78 if analyzed_posts >= 6 else 62
    category_best: dict[str, GrowthPriority] = {}

    category_weight = {
        "cta": 1.00,
        "hook": 0.96,
        "caption": 0.90,
        "general": 0.82,
        "hashtag": 0.62,
    }

    for issue in content_audit.get("priority_issues", []) or []:
        affected_percent = _clamp(issue.get("affected_percent", 0))
        affected_posts = int(issue.get("affected_posts", 0) or 0)
        problem = str(issue.get("issue", "مشکل محتوایی"))
        category = _content_category(problem)

        if analyzed_posts >= 5 and affected_percent < 20:
            continue

        base_impact = 35 + affected_percent * 0.65
        impact = _clamp(base_impact * category_weight[category])
        urgency = 88 if issue.get("priority") == "high" else 66
        if category == "hashtag":
            urgency = min(urgency, 48)
        ease = 90 if category in {"cta", "hook", "caption", "hashtag"} else 68

        candidate = GrowthPriority(
            key=f"content:{category}",
            title=problem,
            source="content_audit",
            problem=problem,
            evidence=(
                f"{affected_posts} پست از {analyzed_posts} پست درگیر این مشکل هستند",
                f"دامنه اثر مشاهده‌شده: {affected_percent}٪",
            ),
            recommendation=_content_recommendation(problem),
            impact=impact,
            confidence=confidence,
            ease=ease,
            urgency=urgency,
            score=_priority_score(
                impact=impact,
                confidence=confidence,
                ease=ease,
                urgency=urgency,
            ),
        )

        previous = category_best.get(category)
        if previous is None or (candidate.score, candidate.impact) > (previous.score, previous.impact):
            category_best[category] = candidate

    return list(category_best.values())


def _content_recommendation(problem: str) -> str:
    if "CTA" in problem or "دعوت به اقدام" in problem:
        return "در پایان محتوای بعدی فقط یک اقدام روشن مثل کامنت، ذخیره یا پیام درخواست کن."
    if "هوک" in problem or "شروع کپشن" in problem:
        return "شروع محتوای بعدی را با سؤال، تضاد، هشدار یا نمایش نتیجه بازنویسی کن."
    if "هشتگ" in problem:
        return "هشتگ‌های تکراری را حذف و مجموعه‌ای کوتاه از هشتگ‌های تخصصی همان موضوع استفاده کن."
    if "کپشن" in problem:
        return "کپشن را به هوک، ارزش اصلی و یک CTA مشخص تقسیم کن."
    return "این مشکل را در محتوای بعدی با یک تغییر کوچک و قابل اندازه‌گیری اصلاح کن."


def build_growth_priorities(
    *,
    profile_audit: Mapping[str, Any] | None,
    content_audit: Mapping[str, Any] | None,
    limit: int = 3,
    completed_keys: Iterable[str] = (),
) -> list[dict[str, Any]]:
    completed = set(completed_keys)
    candidates = [
        *_profile_priorities(profile_audit),
        *_content_priorities(content_audit),
    ]
    filtered = [item for item in candidates if item.key not in completed]
    ranked = sorted(filtered, key=lambda item: (item.score, item.impact, item.confidence), reverse=True)
    return [item.to_dict() for item in ranked[: max(1, limit)]]

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median
from typing import Literal


Confidence = Literal["low", "medium", "high"]
Direction = Literal["strength", "opportunity"]


@dataclass(frozen=True, slots=True)
class Evidence:
    metric: str
    observed: float
    benchmark: float
    unit: str
    sample_size: int


@dataclass(frozen=True, slots=True)
class Finding:
    key: str
    direction: Direction
    title: str
    explanation: str
    confidence: Confidence
    evidence: tuple[Evidence, ...]
    action: str

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["evidence"] = [asdict(item) for item in self.evidence]
        return result


def _confidence(sample_size: int) -> Confidence:
    if sample_size >= 12:
        return "high"
    if sample_size >= 6:
        return "medium"
    return "low"


def _finding(
    *,
    key: str,
    direction: Direction,
    title: str,
    explanation: str,
    action: str,
    evidence: tuple[Evidence, ...],
) -> Finding:
    return Finding(
        key=key,
        direction=direction,
        title=title,
        explanation=explanation,
        confidence=_confidence(min(item.sample_size for item in evidence)),
        evidence=evidence,
        action=action,
    )


def build_evidence_findings(
    *,
    media: list[object],
    engagement_rate: float,
    consistency_score: int,
    caption_score: int,
    posts_per_week: float,
) -> list[dict[str, object]]:
    """Explain recommendations using only observable profile/media facts.

    Benchmarks are deliberately intra-profile (the median of the supplied media)
    or explicit product thresholds. This prevents a small public sample from being
    presented as proof of reach, saves, demographics, or algorithmic outcomes.
    """
    sample_size = len(media)
    if not sample_size:
        return []

    findings: list[Finding] = []
    engagement_direction: Direction = (
        "strength" if engagement_rate >= 3 else "opportunity"
    )
    findings.append(
        _finding(
            key="engagement",
            direction=engagement_direction,
            title="نرخ تعامل عمومی" if engagement_direction == "strength" else "فرصت بهبود تعامل",
            explanation=(
                "میانگین لایک و کامنت پست‌های بررسی‌شده نسبت به تعداد دنبال‌کننده سنجیده شد."
            ),
            action=(
                "الگوی موضوع و شروع پست‌های پربازده را تکرار کن."
                if engagement_direction == "strength"
                else "در سه پست بعدی یک سؤال مشخص و دعوت به نظر دادن را آزمایش کن."
            ),
            evidence=(Evidence("engagement_rate", engagement_rate, 3.0, "percent", sample_size),),
        )
    )

    if consistency_score < 65 or posts_per_week < 3:
        findings.append(
            _finding(
                key="publishing_cadence",
                direction="opportunity",
                title="ریتم انتشار قابل بهبود است",
                explanation="فاصله زمانی پست‌های موجود و تعداد انتشار هفتگی از هدف محصول پایین‌تر است.",
                action="برای دو هفته سه زمان ثابت انتشار انتخاب و نتیجه را دوباره اندازه‌گیری کن.",
                evidence=(
                    Evidence("consistency_score", consistency_score, 65, "score", sample_size),
                    Evidence("posts_per_week", posts_per_week, 3, "posts/week", sample_size),
                ),
            )
        )

    if caption_score < 80:
        findings.append(
            _finding(
                key="caption_coverage",
                direction="opportunity",
                title="پوشش کپشن کامل نیست",
                explanation="بخشی از محتوای نمونه کپشن قابل تحلیل ندارد.",
                action="برای هر پست یک هوک، نکته اصلی و CTA قابل اندازه‌گیری بنویس.",
                evidence=(Evidence("caption_usage_score", caption_score, 80, "score", sample_size),),
            )
        )

    scores_by_type: dict[str, list[float]] = {}
    for item in media:
        media_type = str(getattr(item, "media_type", "unknown"))
        score = float(getattr(item, "like_count", 0)) + 2.5 * float(
            getattr(item, "comment_count", 0)
        ) + 0.02 * float(getattr(item, "view_count", 0))
        scores_by_type.setdefault(media_type, []).append(score)

    eligible = {key: values for key, values in scores_by_type.items() if len(values) >= 2}
    if len(eligible) >= 2:
        ranked = sorted(
            ((median(values), key, len(values)) for key, values in eligible.items()),
            reverse=True,
        )
        best_score, best_type, best_count = ranked[0]
        baseline = median(score for score, _, _ in ranked)
        findings.append(
            _finding(
                key="content_format",
                direction="strength",
                title=f"فرمت {best_type} در این نمونه بهتر عمل کرده است",
                explanation="امتیاز تعامل هر فرمت با میانه همان فرمت مقایسه شد تا پست‌های پرت اثر کمتری داشته باشند.",
                action=f"دو محتوای {best_type} دیگر منتشر کن و پیش از تعمیم نتیجه دوباره مقایسه کن.",
                evidence=(Evidence("median_weighted_interactions", best_score, baseline, "interactions", best_count),),
            )
        )

    return [finding.to_dict() for finding in findings]

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from statistics import median
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class PostEvidence:
    post_id: str
    content_type: str
    engagement: int
    engagement_rate: float
    published_at: str | None
    publish_hour: int | None
    caption_length: int
    hashtag_count: int


@dataclass(frozen=True, slots=True)
class EvidenceSet:
    posts: tuple[PostEvidence, ...]
    sample_size: int
    confidence: float
    baseline_engagement: float
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "posts": [asdict(post) for post in self.posts],
            "sample_size": self.sample_size,
            "confidence": self.confidence,
            "baseline_engagement": self.baseline_engagement,
            "limitations": list(self.limitations),
        }


class EvidenceEngine:
    """Turn public post metrics into normalized evidence without inventing data."""

    def collect(self, media: Iterable[Any], followers: int) -> EvidenceSet:
        posts: list[PostEvidence] = []
        limitations = ["Public metrics do not include saves, shares, or reach."]
        denominator = max(0, followers)

        for item in media:
            likes = self._number(item, "like_count")
            comments = self._number(item, "comment_count")
            engagement = likes + comments
            published_at = self._value(item, "published_at")
            caption = str(self._value(item, "caption") or "")
            posts.append(PostEvidence(
                post_id=str(self._value(item, "id") or ""),
                content_type=str(self._value(item, "media_type") or "unknown").lower(),
                engagement=engagement,
                engagement_rate=round((engagement / denominator * 100), 4) if denominator else 0.0,
                published_at=published_at,
                publish_hour=self._hour(published_at),
                caption_length=len(caption.strip()),
                hashtag_count=caption.count("#"),
            ))

        if denominator == 0:
            limitations.append("Follower count was unavailable, so post engagement rates are zero.")
        if len(posts) < 8:
            limitations.append("The post sample is small; findings should be treated as directional.")
        if not any(post.published_at for post in posts):
            limitations.append("Publish timestamps were unavailable.")

        values = [post.engagement for post in posts]
        confidence = min(0.9, 0.25 + 0.045 * len(posts))
        if denominator == 0:
            confidence -= 0.1
        return EvidenceSet(
            posts=tuple(posts),
            sample_size=len(posts),
            confidence=round(max(0.1, confidence), 2),
            baseline_engagement=round(float(median(values)), 2) if values else 0.0,
            limitations=tuple(limitations),
        )

    @staticmethod
    def group_performance(evidence: EvidenceSet, field: str) -> dict[str, dict[str, float]]:
        groups: dict[str, list[int]] = defaultdict(list)
        for post in evidence.posts:
            value = getattr(post, field)
            if value is not None:
                groups[str(value)].append(post.engagement)
        return {
            key: {"sample_size": len(values), "average_engagement": round(sum(values) / len(values), 2)}
            for key, values in groups.items()
        }

    @staticmethod
    def _value(item: Any, name: str) -> Any:
        return item.get(name) if isinstance(item, dict) else getattr(item, name, None)

    @classmethod
    def _number(cls, item: Any, name: str) -> int:
        try:
            return max(0, int(cls._value(item, name) or 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _hour(value: str | None) -> int | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).hour
        except (TypeError, ValueError):
            return None

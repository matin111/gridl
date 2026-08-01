from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from growth.evidence_engine import EvidenceEngine, EvidenceSet, PostEvidence


class ReasoningEngine:
    """Build traceable insights whose strength is bounded by observed evidence."""

    def analyze(self, evidence: EvidenceSet) -> dict[str, Any]:
        patterns = self._patterns(evidence)
        posts = self._post_intelligence(evidence)
        dna = self._content_dna(evidence, patterns)
        strategy = self._strategy(patterns, dna)
        predictions = self._predictions(evidence, strategy)
        memory = self._learning_memory(evidence, patterns)
        return {
            "evidence": evidence.to_dict(),
            "patterns": patterns,
            "post_intelligence": posts,
            "content_dna": dna,
            "connected_growth_strategy": strategy,
            "predictions": predictions,
            "learning_memory": memory,
            "executive_report": self._executive_report(evidence, patterns, strategy),
        }

    def _patterns(self, evidence: EvidenceSet) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for dimension in ("content_type", "publish_hour"):
            groups = EvidenceEngine.group_performance(evidence, dimension)
            eligible = [(key, data) for key, data in groups.items() if data["sample_size"] >= 2]
            if len(eligible) < 2:
                continue
            winner, winner_data = max(eligible, key=lambda item: item[1]["average_engagement"])
            other_values = [data["average_engagement"] for key, data in eligible if key != winner]
            comparison = sum(other_values) / len(other_values)
            lift = ((winner_data["average_engagement"] / comparison) - 1) * 100 if comparison else 0
            if lift >= 10:
                candidates.append({
                    "dimension": dimension,
                    "signal": winner,
                    "observed_lift_percent": round(lift, 1),
                    "supporting_posts": winner_data["sample_size"],
                    "confidence": self._label(evidence.confidence, winner_data["sample_size"]),
                    "basis": "average public likes + comments versus other observed groups",
                })
        return candidates

    @staticmethod
    def _post_intelligence(evidence: EvidenceSet) -> list[dict[str, Any]]:
        baseline = evidence.baseline_engagement
        result = []
        for post in evidence.posts:
            relative = ((post.engagement / baseline) - 1) * 100 if baseline else 0
            result.append({
                "post_id": post.post_id,
                "content_type": post.content_type,
                "engagement": post.engagement,
                "engagement_rate": post.engagement_rate,
                "relative_to_median_percent": round(relative, 1),
                "performance_band": "above_baseline" if relative >= 15 else "below_baseline" if relative <= -15 else "near_baseline",
                "observable_factors": ReasoningEngine._factors(post),
            })
        return result

    @staticmethod
    def _content_dna(evidence: EvidenceSet, patterns: list[dict[str, Any]]) -> dict[str, Any]:
        types = Counter(post.content_type for post in evidence.posts)
        captioned = [post.caption_length for post in evidence.posts if post.caption_length]
        return {
            "dominant_format": types.most_common(1)[0][0] if types else None,
            "format_mix": dict(types),
            "median_caption_length": sorted(captioned)[len(captioned) // 2] if captioned else 0,
            "repeatable_signals": [f"{item['dimension']}={item['signal']}" for item in patterns],
            "confidence": ReasoningEngine._label(evidence.confidence, evidence.sample_size),
        }

    @staticmethod
    def _strategy(patterns: list[dict[str, Any]], dna: dict[str, Any]) -> list[dict[str, Any]]:
        actions = []
        for pattern in patterns[:2]:
            actions.append({
                "action": f"Test more posts with {pattern['dimension']}={pattern['signal']}",
                "reason": f"Observed {pattern['observed_lift_percent']}% lift in this sample.",
                "measurement": "Compare median likes + comments after at least 3 test posts.",
                "priority": "high" if pattern["confidence"] == "high" else "medium",
            })
        if not actions:
            actions.append({
                "action": f"Run a controlled 3-post test using {dna['dominant_format'] or 'one consistent format'}.",
                "reason": "Current evidence does not support a reliable performance pattern.",
                "measurement": "Hold topic and publish window stable; compare public engagement.",
                "priority": "medium",
            })
        actions.append({
            "action": "Review results weekly and retain only repeatable signals.",
            "reason": "Connected strategy must learn from outcomes rather than one-off winners.",
            "measurement": "Record hypothesis, action, outcome, and decision in learning memory.",
            "priority": "medium",
        })
        return actions

    @staticmethod
    def _predictions(evidence: EvidenceSet, strategy: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{
            "prediction": "The first strategy experiment may improve public engagement if the observed signal repeats.",
            "expected_range_percent": [-10, 20] if evidence.sample_size < 8 else [-5, 25],
            "confidence": "low" if evidence.sample_size < 8 else "medium",
            "assumptions": ["Audience composition remains similar", "Content quality is comparable", "No reach data is available"],
            "validation": strategy[0]["measurement"],
        }]

    @staticmethod
    def _learning_memory(evidence: EvidenceSet, patterns: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "evidence_fingerprint": {
                "sample_size": evidence.sample_size,
                "post_ids": [post.post_id for post in evidence.posts],
                "baseline_engagement": evidence.baseline_engagement,
            },
            "hypotheses": [{"statement": f"{p['dimension']}={p['signal']} can outperform the current baseline", "status": "observed_not_proven", "supporting_posts": p["supporting_posts"]} for p in patterns],
            "experiments": [],
            "outcomes": [],
        }

    @staticmethod
    def _executive_report(evidence: EvidenceSet, patterns: list[dict[str, Any]], strategy: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "headline": f"Analyzed {evidence.sample_size} public posts with {ReasoningEngine._label(evidence.confidence, evidence.sample_size)} confidence.",
            "key_findings": [f"{p['dimension']}={p['signal']} showed a {p['observed_lift_percent']}% observed lift." for p in patterns] or ["No repeatable performance pattern cleared the evidence threshold."],
            "next_best_action": strategy[0]["action"],
            "decision_note": "Treat findings as testable hypotheses, not causal conclusions.",
            "limitations": list(evidence.limitations),
        }

    @staticmethod
    def _factors(post: PostEvidence) -> list[str]:
        return [post.content_type, f"caption_length:{post.caption_length}", f"hashtags:{post.hashtag_count}"] + ([f"hour:{post.publish_hour}"] if post.publish_hour is not None else [])

    @staticmethod
    def _label(confidence: float, support: int) -> str:
        if confidence >= 0.7 and support >= 8:
            return "high"
        if confidence >= 0.5 and support >= 4:
            return "medium"
        return "low"

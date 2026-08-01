from dataclasses import dataclass

from growth.evidence_engine import build_evidence_findings


@dataclass
class Media:
    media_type: str
    like_count: int
    comment_count: int
    view_count: int = 0


def test_empty_sample_produces_no_claims():
    assert build_evidence_findings(
        media=[],
        engagement_rate=0,
        consistency_score=0,
        caption_score=0,
        posts_per_week=0,
    ) == []


def test_findings_include_observations_and_low_sample_confidence():
    result = build_evidence_findings(
        media=[Media("image", 10, 1), Media("image", 20, 2), Media("reel", 50, 4)],
        engagement_rate=1.2,
        consistency_score=40,
        caption_score=60,
        posts_per_week=1.5,
    )

    assert [item["key"] for item in result] == [
        "engagement",
        "publishing_cadence",
        "caption_coverage",
    ]
    assert all(item["confidence"] == "low" for item in result)
    assert result[0]["evidence"][0] == {
        "metric": "engagement_rate",
        "observed": 1.2,
        "benchmark": 3.0,
        "unit": "percent",
        "sample_size": 3,
    }


def test_format_claim_requires_two_samples_per_compared_type():
    media = [
        Media("image", 10, 0),
        Media("image", 20, 0),
        Media("reel", 50, 0),
        Media("reel", 100, 0),
        Media("carousel", 1000, 0),
        Media("image", 30, 0),
    ]
    result = build_evidence_findings(
        media=media,
        engagement_rate=4,
        consistency_score=90,
        caption_score=100,
        posts_per_week=4,
    )

    format_finding = next(item for item in result if item["key"] == "content_format")
    assert "reel" in format_finding["title"]
    assert format_finding["evidence"][0]["sample_size"] == 2
    assert format_finding["confidence"] == "low"

from growth.evidence_engine import EvidenceEngine
from growth.reasoning_engine import ReasoningEngine


def _post(index: int, media_type: str, engagement: int, hour: int = 10) -> dict:
    return {
        "id": str(index),
        "media_type": media_type,
        "like_count": engagement - 2,
        "comment_count": 2,
        "caption": "A useful caption #test",
        "published_at": f"2026-07-{index + 1:02d}T{hour:02d}:00:00+00:00",
    }


def test_evidence_is_normalized_and_records_limitations():
    evidence = EvidenceEngine().collect([_post(0, "reel", 10)], followers=0)

    assert evidence.sample_size == 1
    assert evidence.posts[0].engagement == 10
    assert evidence.posts[0].engagement_rate == 0
    assert any("Follower count" in limitation for limitation in evidence.limitations)
    assert any("directional" in limitation for limitation in evidence.limitations)


def test_reasoning_discovers_supported_format_pattern():
    media = [
        *[_post(index, "reel", 100 + index) for index in range(4)],
        *[_post(index + 4, "image", 40 + index) for index in range(4)],
    ]
    report = ReasoningEngine().analyze(EvidenceEngine().collect(media, followers=1000))

    content_pattern = next(item for item in report["patterns"] if item["dimension"] == "content_type")
    assert content_pattern["signal"] == "reel"
    assert content_pattern["supporting_posts"] == 4
    assert report["content_dna"]["dominant_format"] == "reel"
    assert report["connected_growth_strategy"]
    assert report["predictions"][0]["confidence"] == "medium"
    assert report["learning_memory"]["schema_version"] == 1
    assert "causal conclusions" in report["executive_report"]["decision_note"]


def test_small_sample_does_not_claim_a_pattern():
    report = ReasoningEngine().analyze(
        EvidenceEngine().collect([_post(0, "reel", 100), _post(1, "image", 5)], 100)
    )

    assert report["patterns"] == []
    assert report["predictions"][0]["confidence"] == "low"
    assert report["executive_report"]["key_findings"] == [
        "No repeatable performance pattern cleared the evidence threshold."
    ]

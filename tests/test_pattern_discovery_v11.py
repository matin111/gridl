from growth.pattern_discovery_v11 import discover_visual_patterns


def post(post_id, performance, **visual):
    return {
        "post_id": post_id,
        "performance": {"score": performance},
        "visual": {"status": "completed", **visual},
    }


def test_pattern_discovery_requires_enough_evidence():
    payload = {
        "posts": [
            post("1", 90, cover_score=80, face_detected=True),
            post("2", 20, cover_score=40, face_detected=False),
            post("3", 15, cover_score=35, face_detected=False),
        ]
    }
    result = discover_visual_patterns(payload)
    assert result["status"] == "insufficient_evidence"
    assert result["patterns"] == []
    assert result["minimum_required_posts"] == 6


def test_pattern_discovery_finds_cover_score_relationship():
    payload = {
        "posts": [
            post("h1", 100, cover_score=92),
            post("h2", 90, cover_score=88),
            post("h3", 85, cover_score=84),
            post("l1", 20, cover_score=46),
            post("l2", 15, cover_score=42),
            post("l3", 10, cover_score=38),
        ]
    }
    result = discover_visual_patterns(payload)
    pattern = next(item for item in result["patterns"] if item["key"] == "visual:cover_score")
    assert pattern["direction"] == "positive"
    assert pattern["sample_size"] == 6
    assert set(pattern["evidence_post_ids"]) == {"h1", "h2", "h3"}
    assert "تضمین" in pattern["limitation"]


def test_pattern_discovery_compares_face_groups_without_causal_claim():
    payload = {
        "posts": [
            post("f1", 85, face_detected=True),
            post("f2", 80, face_detected=True),
            post("f3", 75, face_detected=True),
            post("n1", 35, face_detected=False),
            post("n2", 30, face_detected=False),
            post("n3", 25, face_detected=False),
        ]
    }
    result = discover_visual_patterns(payload)
    pattern = next(item for item in result["patterns"] if item["key"] == "visual:face_detected")
    assert pattern["better_group"] == "yes"
    assert pattern["group_sizes"] == {"yes": 3, "no": 3}
    assert pattern["sample_size"] == 6
    assert "همبستگی" in pattern["limitation"]


def test_pending_visual_posts_are_ignored():
    payload = {
        "posts": [
            post("h1", 100, cover_score=90),
            post("h2", 90, cover_score=86),
            post("l1", 20, cover_score=45),
            post("l2", 15, cover_score=40),
            {
                "post_id": "pending",
                "performance": {"score": 1000},
                "visual": {"status": "pending", "cover_score": 100},
            },
        ]
    }
    result = discover_visual_patterns(payload)
    assert result["analyzed_visual_posts"] == 4
    assert result["status"] == "insufficient_evidence"

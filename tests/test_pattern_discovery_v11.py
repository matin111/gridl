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


def test_pattern_discovery_finds_cover_score_relationship():
    payload = {
        "posts": [
            post("h1", 100, cover_score=90),
            post("h2", 90, cover_score=86),
            post("l1", 20, cover_score=45),
            post("l2", 15, cover_score=40),
        ]
    }
    result = discover_visual_patterns(payload)
    pattern = next(item for item in result["patterns"] if item["key"] == "visual:cover_score")
    assert pattern["direction"] == "positive"
    assert pattern["sample_size"] == 4
    assert set(pattern["evidence_post_ids"]) == {"h1", "h2"}
    assert "تضمین" in pattern["limitation"]


def test_pattern_discovery_compares_face_groups_without_causal_claim():
    payload = {
        "posts": [
            post("f1", 80, face_detected=True),
            post("f2", 70, face_detected=True),
            post("n1", 30, face_detected=False),
            post("n2", 25, face_detected=False),
        ]
    }
    result = discover_visual_patterns(payload)
    pattern = next(item for item in result["patterns"] if item["key"] == "visual:face_detected")
    assert pattern["better_group"] == "yes"
    assert pattern["group_sizes"] == {"yes": 2, "no": 2}
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

from types import SimpleNamespace

from growth.profile_audit_adapter import (
    attach_profile_audit,
    build_profile_audit_payload,
    enriched_response_copy,
)


def profile():
    return SimpleNamespace(
        username="matinvpn",
        full_name="Matin VPN | آی پی ثابت",
        biography="فروش VPN و IP ثابت برای تریدرها؛ برای سفارش دایرکت بده.",
        profile_picture_url="https://example.com/avatar.jpg",
    )


def test_build_payload_contains_evidence_and_actions():
    payload = build_profile_audit_payload(profile())

    assert 0 <= payload["score"] <= 100
    assert "summary" in payload
    assert payload["strengths"] or payload["issues"]

    every_item = payload["strengths"] + payload["issues"]
    for item in every_item:
        assert item["evidence"]
        assert item["recommendation"]
        assert item["impact"]
        assert item["confidence"] in {"low", "medium", "high"}


def test_attach_is_additive_and_preserves_legacy_fields():
    response = {
        "success": True,
        "audit_version": 7,
        "growth_manager": {"score": 45},
    }

    returned = attach_profile_audit(response, profile())

    assert returned is response
    assert response["success"] is True
    assert response["audit_version"] == 7
    assert response["growth_manager"] == {"score": 45}
    assert response["profile_audit"]["score"] > 0


def test_copy_helper_does_not_mutate_cached_response():
    cached = {"success": True, "nested": {"value": 1}}

    enriched = enriched_response_copy(cached, profile())
    enriched["nested"]["value"] = 2

    assert "profile_audit" not in cached
    assert cached["nested"]["value"] == 1
    assert enriched["profile_audit"]["summary"]

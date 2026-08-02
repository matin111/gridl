from growth.profile_audit import audit_profile


def _issue(result: dict, key: str) -> dict:
    for item in result["issues"] + result["strengths"]:
        if item["key"] == key:
            return item
    raise AssertionError(f"missing audit item: {key}")


def test_complete_profile_scores_high_and_keeps_evidence() -> None:
    result = audit_profile(
        {
            "username": "matinvpn",
            "full_name": "Matin VPN | آی‌پی ثابت",
            "biography": (
                "فروش VPN و آی‌پی ثابت برای بازی و ترید؛ "
                "برای مشاوره و سفارش در دایرکت پیام بده"
            ),
            "profile_picture_url": "https://example.com/avatar.jpg",
            "external_url": "https://example.com",
            "category": "Internet service provider",
            "contact": "Telegram: @matinvpn",
        }
    )

    assert result["score"] >= 80
    assert result["unavailable_checks"] == []
    assert _issue(result, "biography")["evidence"]
    assert _issue(result, "biography")["confidence"] == "high"


def test_empty_bio_returns_actionable_problem() -> None:
    result = audit_profile(
        {
            "username": "shop_test",
            "full_name": "فروشگاه تست",
            "biography": "",
            "profile_picture_url": "https://example.com/avatar.jpg",
        }
    )

    bio = _issue(result, "biography")
    assert bio["score"] < 50
    assert bio["severity"] in {"critical", "high"}
    assert "سه خط" in bio["recommendation"]
    assert any(item["field"] == "call_to_action" for item in bio["evidence"])


def test_missing_optional_api_fields_are_not_fabricated_failures() -> None:
    result = audit_profile(
        {
            "username": "creator",
            "full_name": "Creator",
            "biography": "آموزش تولید محتوا؛ برای مشاوره پیام بده",
            "profile_picture_url": "https://example.com/avatar.jpg",
        }
    )

    assert set(result["unavailable_checks"]) == {
        "external_url",
        "category",
        "contact",
    }
    all_items = result["issues"] + result["strengths"]
    assert not any(item["key"] in {"external_link", "category", "contact"} for item in all_items)


def test_works_with_object_payload_and_camel_case_fields() -> None:
    class Profile:
        username = "doctor_page"
        fullName = "دکتر نمونه | پوست و مو"
        biography = "خدمات تخصصی پوست و مو؛ برای رزرو و مشاوره پیام بده"
        profilePictureUrl = "https://example.com/avatar.jpg"
        externalUrl = "https://example.com/book"

    result = audit_profile(Profile())

    assert result["score"] > 0
    assert _issue(result, "display_name")["score"] == 100
    assert _issue(result, "profile_picture")["score"] == 100
    assert _issue(result, "external_link")["score"] == 100


def test_summary_names_the_lowest_scoring_profile_problem() -> None:
    result = audit_profile(
        {
            "username": "x",
            "full_name": "",
            "biography": "",
            "profile_picture_url": "",
        }
    )

    lowest = result["issues"][0]
    assert lowest["title"] in result["summary"]

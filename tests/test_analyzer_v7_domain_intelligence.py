from types import SimpleNamespace

import pytest

from growth.domain_intelligence import DOMAIN_PROFILES, DomainDetector, cluster_posts
from growth.growth_manager import GrowthContext, GrowthManager


CASES = {
    "VPN": ("فروش VPN با WireGuard و OpenVPN و IP ثابت", "vpn_center", "WireGuard برای گیم و Netflix VPN"),
    "Restaurant": ("رستوران و غذای تازه؛ رزرو میز", "fresh_restaurant", "منوی آخر هفته و غذای ویژه سرآشپز"),
    "Clothing": ("فروشگاه لباس و مانتو؛ راهنمای سایز", "style_clothing", "سه روش ست کردن مانتو"),
    "AI": ("آموزش هوش مصنوعی و ChatGPT", "ai_academy", "پرامپت بهتر برای ابزار هوش مصنوعی"),
    "Marketing": ("استراتژی بازاریابی و تولید محتوا", "marketing_lab", "قیف فروش و رشد اینستاگرام"),
}


def manager(domain):
    bio, username, caption = CASES[domain]
    media = [SimpleNamespace(caption=caption, like_count=100, comment_count=12,
                             view_count=900, published_at="2026-07-30T18:00:00Z")]
    return GrowthManager(GrowthContext(
        username=username, full_name=bio, followers=1000, following=100, posts=20,
        engagement_rate=4, posting_consistency=80, caption_score=85,
        best_time="19:00", best_content_type="reel", bio=bio, recent_media=media,
    ))


@pytest.mark.parametrize("expected", CASES)
def test_domain_detector_and_entities(expected):
    engine = manager(expected)
    assert engine.domain.domain == expected
    assert engine.domain.confidence >= .5
    assert engine.domain.entities["audience"]


def test_vpn_extracts_protocols_and_never_receives_marketing_tags():
    result = DomainDetector().detect(
        biography="VPN، IP ثابت و Dedicated IP",
        captions=["WireGuard OpenVPN Cisco V2Ray Outline Gaming VPN Netflix VPN"],
    )
    technologies = result.entities["technologies"]
    assert {"WireGuard", "OpenVPN", "Cisco", "V2Ray", "Outline", "Dedicated IP"} <= set(technologies)
    tags = manager("VPN")._ready_to_publish().hashtags
    assert "#VPN" in tags
    assert "#رشد_اینستاگرام" not in tags
    assert "#بازاریابی_محتوا" not in tags


def test_domain_profiles_cover_at_least_twenty_categories():
    assert len(DOMAIN_PROFILES) >= 20
    for profile in DOMAIN_PROFILES.values():
        assert profile.audience and profile.problems and profile.questions
        assert profile.objections and profile.terminology and profile.evergreen_topics


def test_regression_categories_produce_different_editorial_values():
    values = [manager(domain)._ready_to_publish() for domain in CASES]
    assert len({tuple(item.hashtags) for item in values}) == len(CASES)
    assert len({item.caption for item in values}) == len(CASES)
    assert len({manager(domain).domain_profile.evergreen_topics[0] for domain in CASES}) == len(CASES)
    assert len({item.cta for item in values}) == len(CASES)


def test_post_clusters_have_per_cluster_success_scores():
    posts = [
        SimpleNamespace(caption="آموزش و راهنمای اتصال", like_count=10, comment_count=5, view_count=100),
        SimpleNamespace(caption="تخفیف فروش آخر هفته", like_count=20, comment_count=2, view_count=200),
    ]
    scores = cluster_posts(posts)
    assert scores == {"Tutorials": 30.0, "Offers": 44.0}

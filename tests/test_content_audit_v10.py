from types import SimpleNamespace

from growth.content_audit import audit_content, audit_post


def media(
    post_id: str,
    caption: str,
    *,
    likes: int = 0,
    comments: int = 0,
    views: int = 0,
    media_type: str = "reel",
):
    return SimpleNamespace(
        id=post_id,
        caption=caption,
        like_count=likes,
        comment_count=comments,
        view_count=views,
        media_type=media_type,
        permalink=f"https://instagram.com/p/{post_id}/",
        published_at="2026-08-01T18:00:00+00:00",
    )


def test_question_hook_and_cta_are_detected():
    result = audit_post(
        media(
            "1",
            "چرا VPN تو مدام قطع می‌شود؟\n\nسه دلیل اصلی را بررسی کن.\n\nنوع دستگاهت را کامنت کن. #VPN #امنیت_اینترنت #WireGuard",
            likes=120,
            comments=15,
            views=1800,
        )
    )

    assert result["hook_type"] == "question"
    assert result["hook_score"] >= 70
    assert result["cta_present"] is True
    assert result["caption_score"] >= 70
    assert result["hashtag_score"] >= 70


def test_empty_caption_is_reported_without_fabricating_visual_analysis():
    result = audit_post(media("2", "", likes=5))

    assert result["hook_score"] == 0
    assert result["caption_score"] == 0
    assert result["cta_present"] is False
    assert any("کپشن" in issue for issue in result["issues"])
    assert any("کاور" in limitation for limitation in result["limitations"])


def test_duplicate_and_excessive_hashtags_reduce_score():
    caption = "یک متن معمولی\n" + " ".join(["#عمومی"] * 22)
    result = audit_post(media("3", caption))

    assert result["hashtag_score"] < 50
    assert any("تکراری" in issue or "زیاد" in issue for issue in result["issues"])


def test_content_audit_ranks_posts_and_builds_priority_issues():
    posts = [
        media(
            "strong-1",
            "۳ روش برای کاهش پینگ VPN\n\nراهنمای مرحله‌ای اتصال.\n\nذخیره کن. #VPN #کاهش_پینگ #WireGuard",
            likes=220,
            comments=25,
            views=3000,
        ),
        media(
            "strong-2",
            "چرا OpenVPN کندتر از WireGuard است؟\n\nمقایسه کامل را بخوان.\n\nنظرت را کامنت کن. #VPN #OpenVPN #WireGuard",
            likes=180,
            comments=18,
            views=2500,
        ),
        media("weak-1", "سلام دوستان", likes=10, comments=0, views=100),
        media("weak-2", "پست جدید", likes=8, comments=0, views=80),
    ]

    result = audit_content(posts)

    assert result["analyzed_posts"] == 4
    assert result["best_posts"][0]["post_id"] == "strong-1"
    assert result["weakest_posts"][0]["post_id"] in {"weak-1", "weak-2"}
    assert result["priority_issues"]
    assert 0 <= result["score"] <= 100


def test_pattern_requires_at_least_two_strong_and_two_weak_samples():
    insufficient = audit_content(
        [
            media("a", "چرا این اتفاق می‌افتد؟\n\nذخیره کن.", likes=100),
            media("b", "متن ساده", likes=10),
            media("c", "متن ساده دیگر", likes=9),
        ]
    )
    assert insufficient["patterns"] == []

    enough = audit_content(
        [
            media("s1", "چرا این اتفاق می‌افتد؟\n\nذخیره کن.", likes=100),
            media("s2", "۳ نتیجه مهم را ببین!\n\nنظر بده.", likes=90),
            media("w1", "متن ساده", likes=10),
            media("w2", "متن معمولی", likes=8),
        ]
    )
    assert any(pattern["metric"] == "hook_score" for pattern in enough["patterns"])


def test_content_mix_is_based_on_observed_caption_language():
    result = audit_content(
        [
            media("e", "آموزش انتخاب پروتکل VPN"),
            media("s", "تخفیف خرید اشتراک VPN"),
            media("q", "تو کدام پروتکل را انتخاب می‌کنی؟"),
            media("g", "امروز درباره اتصال صحبت می‌کنیم"),
        ]
    )

    assert result["content_mix"] == {
        "education": 1,
        "sales": 1,
        "engagement": 1,
        "general": 1,
    }

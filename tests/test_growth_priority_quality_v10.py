from growth.priority_engine import build_growth_priorities


def test_content_priorities_collapse_duplicate_hashtag_issues():
    content = {
        "analyzed_posts": 12,
        "priority_issues": [
            {"issue": "هشتگی در کپشن تشخیص داده نشد", "affected_posts": 3, "affected_percent": 25, "priority": "medium"},
            {"issue": "1 هشتگ تکراری داخل کپشن دیده شد", "affected_posts": 3, "affected_percent": 25, "priority": "medium"},
            {"issue": "CTA مشخصی برای کامنت وجود ندارد", "affected_posts": 3, "affected_percent": 25, "priority": "medium"},
        ],
    }
    priorities = build_growth_priorities(profile_audit=None, content_audit=content, limit=5)
    keys = [item["key"] for item in priorities]
    assert keys.count("content:hashtag") == 1
    assert "content:cta" in keys


def test_cta_ranks_above_hashtag_for_same_observed_scope():
    content = {
        "analyzed_posts": 12,
        "priority_issues": [
            {"issue": "هشتگی در کپشن تشخیص داده نشد", "affected_posts": 3, "affected_percent": 25, "priority": "medium"},
            {"issue": "CTA مشخصی برای کامنت وجود ندارد", "affected_posts": 3, "affected_percent": 25, "priority": "medium"},
        ],
    }
    priorities = build_growth_priorities(profile_audit=None, content_audit=content, limit=3)
    assert priorities[0]["key"] == "content:cta"


def test_rare_issue_is_not_promoted_to_daily_action():
    content = {
        "analyzed_posts": 12,
        "priority_issues": [
            {"issue": "هشتگی در کپشن تشخیص داده نشد", "affected_posts": 1, "affected_percent": 8, "priority": "medium"},
        ],
    }
    priorities = build_growth_priorities(profile_audit=None, content_audit=content, limit=3)
    assert priorities == []

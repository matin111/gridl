from __future__ import annotations

from pathlib import Path


TARGET = Path(__file__).resolve().parents[1] / "instagram_analyzer.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")

    fresh_old = '''            fresh_cache["growth_director"] = build_growth_director_payload(
                profile_audit=fresh_cache.get("profile_audit"),
                content_audit=fresh_cache.get("content_audit"),
                post_intelligence=fresh_cache.get("post_intelligence"),
                ai_growth_coach=fresh_cache.get("ai_growth_coach"),
            )'''
    fresh_new = '''            fresh_cache["growth_director"] = build_growth_director_payload(
                profile_audit=fresh_cache.get("profile_audit"),
                content_audit=fresh_cache.get("content_audit"),
                post_intelligence=fresh_cache.get("post_intelligence"),
                ai_growth_coach=fresh_cache.get("ai_growth_coach"),
                analytics=fresh_cache.get("analytics"),
            )'''

    live_old = '''        growth_director = build_growth_director_payload(
            profile_audit=profile_audit,
            content_audit=content_audit,
            post_intelligence=post_intelligence,
            ai_growth_coach=ai_growth_coach,
        )'''
    live_new = '''        growth_director = build_growth_director_payload(
            profile_audit=profile_audit,
            content_audit=content_audit,
            post_intelligence=post_intelligence,
            ai_growth_coach=ai_growth_coach,
            analytics=analytics.model_dump(mode="json"),
        )'''

    stale_old = '''                stale_cache["growth_director"] = build_growth_director_payload(
                    profile_audit=stale_cache.get("profile_audit"),
                    content_audit=stale_cache.get("content_audit"),
                    post_intelligence=stale_cache.get("post_intelligence"),
                    ai_growth_coach=stale_cache.get("ai_growth_coach"),
                )'''
    stale_new = '''                stale_cache["growth_director"] = build_growth_director_payload(
                    profile_audit=stale_cache.get("profile_audit"),
                    content_audit=stale_cache.get("content_audit"),
                    post_intelligence=stale_cache.get("post_intelligence"),
                    ai_growth_coach=stale_cache.get("ai_growth_coach"),
                    analytics=stale_cache.get("analytics"),
                )'''

    text = replace_once(text, fresh_old, fresh_new, "fresh cache integration")
    text = replace_once(text, live_old, live_new, "live analysis integration")
    text = replace_once(text, stale_old, stale_new, "stale cache integration")

    TARGET.write_text(text, encoding="utf-8")
    print("Next Content V12.1 analytics integration applied to instagram_analyzer.py")


if __name__ == "__main__":
    main()

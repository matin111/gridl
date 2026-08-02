from __future__ import annotations

from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "instagram_analyzer.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from growth.content_audit_adapter import build_content_audit_payload\n",
        "from growth.content_audit_adapter import build_content_audit_payload\n"
        "from growth.growth_coach_adapter import build_growth_coach_payload\n",
        "import",
    )

    text = replace_once(
        text,
        "    # V10 evidence-based content audit; additive for Android compatibility.\n"
        "    content_audit: dict[str, Any] | None = None\n\n"
        "    audit_version: int = 10\n",
        "    # V10 evidence-based content audit; additive for Android compatibility.\n"
        "    content_audit: dict[str, Any] | None = None\n\n"
        "    # V10 decision layer: one action today plus the next priorities.\n"
        "    ai_growth_coach: dict[str, Any] | None = None\n\n"
        "    audit_version: int = 10\n",
        "response schema",
    )

    old_cache = '''        if (cached_profile and not fresh_cache.get("profile_audit")) or not fresh_cache.get("content_audit"):\n            fresh_cache = dict(fresh_cache)\n            if cached_profile and not fresh_cache.get("profile_audit"):\n                fresh_cache["profile_audit"] = build_profile_audit_payload(cached_profile)\n            if not fresh_cache.get("content_audit"):\n                fresh_cache["content_audit"] = build_content_audit_payload(cached_media)\n            fresh_cache["audit_version"] = 10\n        return InstagramAnalyzeResponse(**fresh_cache)\n'''
    new_cache = '''        if (\n            (cached_profile and not fresh_cache.get("profile_audit"))\n            or not fresh_cache.get("content_audit")\n            or not fresh_cache.get("ai_growth_coach")\n        ):\n            fresh_cache = dict(fresh_cache)\n            if cached_profile and not fresh_cache.get("profile_audit"):\n                fresh_cache["profile_audit"] = build_profile_audit_payload(cached_profile)\n            if not fresh_cache.get("content_audit"):\n                fresh_cache["content_audit"] = build_content_audit_payload(cached_media)\n            if not fresh_cache.get("ai_growth_coach"):\n                fresh_cache["ai_growth_coach"] = build_growth_coach_payload(\n                    profile_audit=fresh_cache.get("profile_audit"),\n                    content_audit=fresh_cache.get("content_audit"),\n                )\n            fresh_cache["audit_version"] = 10\n        return InstagramAnalyzeResponse(**fresh_cache)\n'''
    text = replace_once(text, old_cache, new_cache, "fresh cache")

    text = replace_once(
        text,
        "        profile_audit = build_profile_audit_payload(profile)\n"
        "        content_audit = build_content_audit_payload(recent_media)\n\n"
        "        result = InstagramAnalyzeResponse(\n",
        "        profile_audit = build_profile_audit_payload(profile)\n"
        "        content_audit = build_content_audit_payload(recent_media)\n"
        "        ai_growth_coach = build_growth_coach_payload(\n"
        "            profile_audit=profile_audit,\n"
        "            content_audit=content_audit,\n"
        "        )\n\n"
        "        result = InstagramAnalyzeResponse(\n",
        "coach build",
    )

    text = replace_once(
        text,
        "            profile_audit=profile_audit,\n"
        "            content_audit=content_audit,\n"
        "            audit_version=10,\n",
        "            profile_audit=profile_audit,\n"
        "            content_audit=content_audit,\n"
        "            ai_growth_coach=ai_growth_coach,\n"
        "            audit_version=10,\n",
        "success response",
    )

    old_stale = '''            if cached_profile and not stale_cache.get("profile_audit"):\n                stale_cache["profile_audit"] = build_profile_audit_payload(cached_profile)\n            if not stale_cache.get("content_audit"):\n                stale_cache["content_audit"] = build_content_audit_payload(cached_media)\n            stale_cache["audit_version"] = 10\n            return InstagramAnalyzeResponse(**stale_cache)\n'''
    new_stale = '''            if cached_profile and not stale_cache.get("profile_audit"):\n                stale_cache["profile_audit"] = build_profile_audit_payload(cached_profile)\n            if not stale_cache.get("content_audit"):\n                stale_cache["content_audit"] = build_content_audit_payload(cached_media)\n            if not stale_cache.get("ai_growth_coach"):\n                stale_cache["ai_growth_coach"] = build_growth_coach_payload(\n                    profile_audit=stale_cache.get("profile_audit"),\n                    content_audit=stale_cache.get("content_audit"),\n                )\n            stale_cache["audit_version"] = 10\n            return InstagramAnalyzeResponse(**stale_cache)\n'''
    text = replace_once(text, old_stale, new_stale, "stale cache")

    text = replace_once(
        text,
        "            profile_audit=None,\n"
        "            content_audit=None,\n"
        "            audit_version=10,\n",
        "            profile_audit=None,\n"
        "            content_audit=None,\n"
        "            ai_growth_coach=None,\n"
        "            audit_version=10,\n",
        "error response",
    )

    TARGET.write_text(text, encoding="utf-8")
    print("Growth Coach V10 integration applied to instagram_analyzer.py")


if __name__ == "__main__":
    main()

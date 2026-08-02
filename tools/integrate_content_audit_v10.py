from __future__ import annotations

from pathlib import Path

TARGET = Path("instagram_analyzer.py")


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return source.replace(old, new, 1)


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")

    if "from growth.content_audit_adapter import build_content_audit_payload" not in source:
        source = replace_once(
            source,
            "from growth.profile_audit_adapter import build_profile_audit_payload\n",
            "from growth.profile_audit_adapter import build_profile_audit_payload\n"
            "from growth.content_audit_adapter import build_content_audit_payload\n",
            "content audit import",
        )

    if "content_audit: dict[str, Any] | None = None" not in source:
        source = replace_once(
            source,
            "    # V10 evidence-based profile audit; additive for Android compatibility.\n"
            "    profile_audit: dict[str, Any] | None = None\n\n"
            "    audit_version: int = 10\n",
            "    # V10 evidence-based profile audit; additive for Android compatibility.\n"
            "    profile_audit: dict[str, Any] | None = None\n\n"
            "    # V10 evidence-based content audit; additive for Android compatibility.\n"
            "    content_audit: dict[str, Any] | None = None\n\n"
            "    audit_version: int = 10\n",
            "response schema",
        )

    if '"content_audit": None' not in source:
        source = replace_once(
            source,
            '            "profile_audit": None,\n        }\n',
            '            "profile_audit": None,\n            "content_audit": None,\n        }\n',
            "empty content director context",
        )

    if '"content_audit": analysis.content_audit' not in source:
        source = replace_once(
            source,
            '        "profile_audit": analysis.profile_audit,\n',
            '        "profile_audit": analysis.profile_audit,\n'
            '        "content_audit": analysis.content_audit,\n',
            "content director context",
        )

    old_fresh = (
        '        cached_profile = fresh_cache.get("profile")\n'
        '        if cached_profile and not fresh_cache.get("profile_audit"):\n'
        '            fresh_cache = dict(fresh_cache)\n'
        '            fresh_cache["profile_audit"] = build_profile_audit_payload(cached_profile)\n'
        '            fresh_cache["audit_version"] = 10\n'
        '        return InstagramAnalyzeResponse(**fresh_cache)\n'
    )
    new_fresh = (
        '        cached_profile = fresh_cache.get("profile")\n'
        '        cached_media = fresh_cache.get("recent_media") or []\n'
        '        if (cached_profile and not fresh_cache.get("profile_audit")) or not fresh_cache.get("content_audit"):\n'
        '            fresh_cache = dict(fresh_cache)\n'
        '            if cached_profile and not fresh_cache.get("profile_audit"):\n'
        '                fresh_cache["profile_audit"] = build_profile_audit_payload(cached_profile)\n'
        '            if not fresh_cache.get("content_audit"):\n'
        '                fresh_cache["content_audit"] = build_content_audit_payload(cached_media)\n'
        '            fresh_cache["audit_version"] = 10\n'
        '        return InstagramAnalyzeResponse(**fresh_cache)\n'
    )
    if old_fresh in source:
        source = replace_once(source, old_fresh, new_fresh, "fresh cache hydration")

    if "content_audit = build_content_audit_payload(recent_media)" not in source:
        source = replace_once(
            source,
            "        profile_audit = build_profile_audit_payload(profile)\n\n"
            "        result = InstagramAnalyzeResponse(\n",
            "        profile_audit = build_profile_audit_payload(profile)\n"
            "        content_audit = build_content_audit_payload(recent_media)\n\n"
            "        result = InstagramAnalyzeResponse(\n",
            "content audit build",
        )

    if "            content_audit=content_audit,\n" not in source:
        source = replace_once(
            source,
            "            profile_audit=profile_audit,\n"
            "            audit_version=10,\n",
            "            profile_audit=profile_audit,\n"
            "            content_audit=content_audit,\n"
            "            audit_version=10,\n",
            "success response",
        )

    old_stale = (
        '            cached_profile = stale_cache.get("profile")\n'
        '            if cached_profile and not stale_cache.get("profile_audit"):\n'
        '                stale_cache["profile_audit"] = build_profile_audit_payload(cached_profile)\n'
        '                stale_cache["audit_version"] = 10\n'
        '            return InstagramAnalyzeResponse(**stale_cache)\n'
    )
    new_stale = (
        '            cached_profile = stale_cache.get("profile")\n'
        '            cached_media = stale_cache.get("recent_media") or []\n'
        '            if cached_profile and not stale_cache.get("profile_audit"):\n'
        '                stale_cache["profile_audit"] = build_profile_audit_payload(cached_profile)\n'
        '            if not stale_cache.get("content_audit"):\n'
        '                stale_cache["content_audit"] = build_content_audit_payload(cached_media)\n'
        '            stale_cache["audit_version"] = 10\n'
        '            return InstagramAnalyzeResponse(**stale_cache)\n'
    )
    if old_stale in source:
        source = replace_once(source, old_stale, new_stale, "stale cache hydration")

    if "            content_audit=None,\n" not in source:
        source = replace_once(
            source,
            "            profile_audit=None,\n"
            "            audit_version=10,\n",
            "            profile_audit=None,\n"
            "            content_audit=None,\n"
            "            audit_version=10,\n",
            "error response",
        )

    TARGET.write_text(source, encoding="utf-8")
    print("Content Audit V10 integration applied to instagram_analyzer.py")


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "instagram_analyzer.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Integration marker not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from growth.growth_coach_adapter import build_growth_coach_payload\n",
        "from growth.growth_coach_adapter import build_growth_coach_payload\n"
        "from growth.post_intelligence_adapter import build_post_intelligence_payload\n",
        "adapter import",
    )

    text = replace_once(
        text,
        "    # V10 decision layer: one action today plus the next priorities.\n"
        "    ai_growth_coach: dict[str, Any] | None = None\n\n"
        "    audit_version: int = 10\n",
        "    # V10 decision layer: one action today plus the next priorities.\n"
        "    ai_growth_coach: dict[str, Any] | None = None\n\n"
        "    # V11 factual per-post dossiers; visual fields stay pending until Vision runs.\n"
        "    post_intelligence: dict[str, Any] | None = None\n\n"
        "    audit_version: int = 11\n",
        "response schema",
    )

    text = replace_once(
        text,
        "        if (cached_profile and not fresh_cache.get(\"profile_audit\")) or not fresh_cache.get(\"content_audit\") or not fresh_cache.get(\"ai_growth_coach\"):\n",
        "        if (cached_profile and not fresh_cache.get(\"profile_audit\")) or not fresh_cache.get(\"content_audit\") or not fresh_cache.get(\"ai_growth_coach\") or not fresh_cache.get(\"post_intelligence\"):\n",
        "fresh cache condition",
    )

    text = replace_once(
        text,
        "            if not fresh_cache.get(\"ai_growth_coach\"):\n"
        "                fresh_cache[\"ai_growth_coach\"] = build_growth_coach_payload(\n"
        "                    profile_audit=fresh_cache.get(\"profile_audit\"),\n"
        "                    content_audit=fresh_cache.get(\"content_audit\"),\n"
        "                )\n"
        "            fresh_cache[\"audit_version\"] = 10\n",
        "            if not fresh_cache.get(\"ai_growth_coach\"):\n"
        "                fresh_cache[\"ai_growth_coach\"] = build_growth_coach_payload(\n"
        "                    profile_audit=fresh_cache.get(\"profile_audit\"),\n"
        "                    content_audit=fresh_cache.get(\"content_audit\"),\n"
        "                )\n"
        "            if not fresh_cache.get(\"post_intelligence\"):\n"
        "                fresh_cache[\"post_intelligence\"] = build_post_intelligence_payload(cached_media)\n"
        "            fresh_cache[\"audit_version\"] = 11\n",
        "fresh cache enrichment",
    )

    text = replace_once(
        text,
        "        ai_growth_coach = build_growth_coach_payload(\n"
        "            profile_audit=profile_audit,\n"
        "            content_audit=content_audit,\n"
        "        )\n\n"
        "        result = InstagramAnalyzeResponse(\n",
        "        ai_growth_coach = build_growth_coach_payload(\n"
        "            profile_audit=profile_audit,\n"
        "            content_audit=content_audit,\n"
        "        )\n"
        "        post_intelligence = build_post_intelligence_payload(recent_media)\n\n"
        "        result = InstagramAnalyzeResponse(\n",
        "live payload build",
    )

    text = replace_once(
        text,
        "            ai_growth_coach=ai_growth_coach,\n"
        "            audit_version=10,\n"
        "            source=\"boxapi_public_analysis_v10\",\n",
        "            ai_growth_coach=ai_growth_coach,\n"
        "            post_intelligence=post_intelligence,\n"
        "            audit_version=11,\n"
        "            source=\"boxapi_public_analysis_v11\",\n",
        "live response",
    )

    text = replace_once(
        text,
        "            if not stale_cache.get(\"ai_growth_coach\"):\n"
        "                stale_cache[\"ai_growth_coach\"] = build_growth_coach_payload(\n"
        "                    profile_audit=stale_cache.get(\"profile_audit\"),\n"
        "                    content_audit=stale_cache.get(\"content_audit\"),\n"
        "                )\n"
        "            stale_cache[\"audit_version\"] = 10\n",
        "            if not stale_cache.get(\"ai_growth_coach\"):\n"
        "                stale_cache[\"ai_growth_coach\"] = build_growth_coach_payload(\n"
        "                    profile_audit=stale_cache.get(\"profile_audit\"),\n"
        "                    content_audit=stale_cache.get(\"content_audit\"),\n"
        "                )\n"
        "            if not stale_cache.get(\"post_intelligence\"):\n"
        "                stale_cache[\"post_intelligence\"] = build_post_intelligence_payload(cached_media)\n"
        "            stale_cache[\"audit_version\"] = 11\n",
        "stale cache enrichment",
    )

    text = replace_once(
        text,
        "            ai_growth_coach=None,\n"
        "            audit_version=10,\n",
        "            ai_growth_coach=None,\n"
        "            post_intelligence=None,\n"
        "            audit_version=11,\n",
        "error response",
    )

    TARGET.write_text(text, encoding="utf-8")
    print("Post Intelligence V11 integration applied to instagram_analyzer.py")


if __name__ == "__main__":
    main()

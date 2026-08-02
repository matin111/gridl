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
        "from growth.post_intelligence_adapter import build_post_intelligence_payload\n",
        "from growth.post_intelligence_adapter import build_post_intelligence_payload\n"
        "from growth.growth_director_adapter import build_growth_director_payload\n",
        "growth director import",
    )

    text = replace_once(
        text,
        "    # V11 factual per-post dossiers; visual fields remain pending until Vision runs.\n"
        "    post_intelligence: dict[str, Any] | None = None\n\n"
        "    audit_version: int = 11\n",
        "    # V11 factual per-post dossiers; visual fields remain pending until Vision runs.\n"
        "    post_intelligence: dict[str, Any] | None = None\n\n"
        "    # V12 central decision layer for dashboard, mission and priorities.\n"
        "    growth_director: dict[str, Any] | None = None\n\n"
        "    audit_version: int = 12\n",
        "response schema",
    )

    text = replace_once(
        text,
        "        if not fresh_cache.get(\"post_intelligence\"):\n"
        "            fresh_cache = dict(fresh_cache)\n"
        "            fresh_cache[\"post_intelligence\"] = build_post_intelligence_payload(cached_media)\n"
        "        fresh_cache[\"audit_version\"] = 11\n"
        "        return InstagramAnalyzeResponse(**fresh_cache)\n",
        "        if not fresh_cache.get(\"post_intelligence\"):\n"
        "            fresh_cache = dict(fresh_cache)\n"
        "            fresh_cache[\"post_intelligence\"] = build_post_intelligence_payload(cached_media)\n"
        "        if not fresh_cache.get(\"growth_director\"):\n"
        "            fresh_cache = dict(fresh_cache)\n"
        "            fresh_cache[\"growth_director\"] = build_growth_director_payload(\n"
        "                profile_audit=fresh_cache.get(\"profile_audit\"),\n"
        "                content_audit=fresh_cache.get(\"content_audit\"),\n"
        "                post_intelligence=fresh_cache.get(\"post_intelligence\"),\n"
        "                ai_growth_coach=fresh_cache.get(\"ai_growth_coach\"),\n"
        "            )\n"
        "        fresh_cache[\"audit_version\"] = 12\n"
        "        return InstagramAnalyzeResponse(**fresh_cache)\n",
        "fresh cache director",
    )

    text = replace_once(
        text,
        "        post_intelligence = build_post_intelligence_payload(recent_media)\n"
        "        post_intelligence = await enrich_post_intelligence_with_vision(post_intelligence)\n\n"
        "        result = InstagramAnalyzeResponse(\n",
        "        post_intelligence = build_post_intelligence_payload(recent_media)\n"
        "        post_intelligence = await enrich_post_intelligence_with_vision(post_intelligence)\n"
        "        growth_director = build_growth_director_payload(\n"
        "            profile_audit=profile_audit,\n"
        "            content_audit=content_audit,\n"
        "            post_intelligence=post_intelligence,\n"
        "            ai_growth_coach=ai_growth_coach,\n"
        "        )\n\n"
        "        result = InstagramAnalyzeResponse(\n",
        "live director build",
    )

    text = replace_once(
        text,
        "            ai_growth_coach=ai_growth_coach,\n"
        "            post_intelligence=post_intelligence,\n"
        "            audit_version=11,\n"
        "            source=\"boxapi_public_analysis_v11\",\n",
        "            ai_growth_coach=ai_growth_coach,\n"
        "            post_intelligence=post_intelligence,\n"
        "            growth_director=growth_director,\n"
        "            audit_version=12,\n"
        "            source=\"boxapi_public_analysis_v12\",\n",
        "live response",
    )

    text = replace_once(
        text,
        "            if not stale_cache.get(\"post_intelligence\"):\n"
        "                stale_cache[\"post_intelligence\"] = build_post_intelligence_payload(cached_media)\n"
        "            stale_cache[\"audit_version\"] = 11\n"
        "            return InstagramAnalyzeResponse(**stale_cache)\n",
        "            if not stale_cache.get(\"post_intelligence\"):\n"
        "                stale_cache[\"post_intelligence\"] = build_post_intelligence_payload(cached_media)\n"
        "            if not stale_cache.get(\"growth_director\"):\n"
        "                stale_cache[\"growth_director\"] = build_growth_director_payload(\n"
        "                    profile_audit=stale_cache.get(\"profile_audit\"),\n"
        "                    content_audit=stale_cache.get(\"content_audit\"),\n"
        "                    post_intelligence=stale_cache.get(\"post_intelligence\"),\n"
        "                    ai_growth_coach=stale_cache.get(\"ai_growth_coach\"),\n"
        "                )\n"
        "            stale_cache[\"audit_version\"] = 12\n"
        "            return InstagramAnalyzeResponse(**stale_cache)\n",
        "stale cache director",
    )

    text = replace_once(
        text,
        "            ai_growth_coach=None,\n"
        "            post_intelligence=None,\n"
        "            audit_version=11,\n",
        "            ai_growth_coach=None,\n"
        "            post_intelligence=None,\n"
        "            growth_director=None,\n"
        "            audit_version=12,\n",
        "error response",
    )

    TARGET.write_text(text, encoding="utf-8")
    print("Growth Director V12 integration applied to instagram_analyzer.py")


if __name__ == "__main__":
    main()

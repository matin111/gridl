from __future__ import annotations

from pathlib import Path


PATH = Path("instagram_analyzer.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Integration marker not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from growth.growth_director_adapter import build_growth_director_payload\n",
        "from growth.growth_director_adapter import build_growth_director_payload\n"
        "from growth.content_director_v13 import generate_content_director\n",
        "content director import",
    )

    text = replace_once(
        text,
        "    # V12 central decision layer for dashboard, mission and priorities.\n"
        "    growth_director: dict[str, Any] | None = None\n\n"
        "    audit_version: int = 12\n",
        "    # V12 central decision layer for dashboard, mission and priorities.\n"
        "    growth_director: dict[str, Any] | None = None\n\n"
        "    # V13 final OpenAI-generated, evidence-grounded content package.\n"
        "    content_director: dict[str, Any] | None = None\n\n"
        "    audit_version: int = 13\n",
        "response schema",
    )

    text = replace_once(
        text,
        "        fresh_cache[\"audit_version\"] = 12\n"
        "        return InstagramAnalyzeResponse(**fresh_cache)\n",
        "        if not fresh_cache.get(\"content_director\"):\n"
        "            fresh_cache = dict(fresh_cache)\n"
        "            fresh_cache[\"content_director\"] = await generate_content_director(\n"
        "                profile=fresh_cache.get(\"profile\"),\n"
        "                analytics=fresh_cache.get(\"analytics\"),\n"
        "                growth_director=fresh_cache.get(\"growth_director\"),\n"
        "                post_intelligence=fresh_cache.get(\"post_intelligence\"),\n"
        "                content_audit=fresh_cache.get(\"content_audit\"),\n"
        "            )\n"
        "        fresh_cache[\"audit_version\"] = 13\n"
        "        return InstagramAnalyzeResponse(**fresh_cache)\n",
        "fresh cache",
    )

    text = replace_once(
        text,
        "        growth_director = build_growth_director_payload(\n"
        "            profile_audit=profile_audit,\n"
        "            content_audit=content_audit,\n"
        "            post_intelligence=post_intelligence,\n"
        "            ai_growth_coach=ai_growth_coach,\n"
        "            analytics=analytics.model_dump(mode=\"json\"),\n"
        "        )\n\n"
        "        result = InstagramAnalyzeResponse(\n",
        "        growth_director = build_growth_director_payload(\n"
        "            profile_audit=profile_audit,\n"
        "            content_audit=content_audit,\n"
        "            post_intelligence=post_intelligence,\n"
        "            ai_growth_coach=ai_growth_coach,\n"
        "            analytics=analytics.model_dump(mode=\"json\"),\n"
        "        )\n"
        "        content_director = await generate_content_director(\n"
        "            profile=profile.model_dump(mode=\"json\"),\n"
        "            analytics=analytics.model_dump(mode=\"json\"),\n"
        "            growth_director=growth_director,\n"
        "            post_intelligence=post_intelligence,\n"
        "            content_audit=content_audit,\n"
        "        )\n\n"
        "        result = InstagramAnalyzeResponse(\n",
        "live generation",
    )

    text = replace_once(
        text,
        "            growth_director=growth_director,\n"
        "            audit_version=12,\n"
        "            source=\"boxapi_public_analysis_v12\",\n",
        "            growth_director=growth_director,\n"
        "            content_director=content_director,\n"
        "            audit_version=13,\n"
        "            source=\"boxapi_public_analysis_v13\",\n",
        "live response",
    )

    text = replace_once(
        text,
        "            stale_cache[\"audit_version\"] = 12\n"
        "            return InstagramAnalyzeResponse(**stale_cache)\n",
        "            if not stale_cache.get(\"content_director\"):\n"
        "                stale_cache[\"content_director\"] = await generate_content_director(\n"
        "                    profile=stale_cache.get(\"profile\"),\n"
        "                    analytics=stale_cache.get(\"analytics\"),\n"
        "                    growth_director=stale_cache.get(\"growth_director\"),\n"
        "                    post_intelligence=stale_cache.get(\"post_intelligence\"),\n"
        "                    content_audit=stale_cache.get(\"content_audit\"),\n"
        "                )\n"
        "            stale_cache[\"audit_version\"] = 13\n"
        "            return InstagramAnalyzeResponse(**stale_cache)\n",
        "stale cache",
    )

    text = replace_once(
        text,
        "            growth_director=None,\n"
        "            audit_version=12,\n",
        "            growth_director=None,\n"
        "            content_director=None,\n"
        "            audit_version=13,\n",
        "error response",
    )

    PATH.write_text(text, encoding="utf-8")
    print("Content Director V13 integration applied to instagram_analyzer.py")


if __name__ == "__main__":
    main()

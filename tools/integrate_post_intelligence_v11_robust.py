from __future__ import annotations

from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "instagram_analyzer.py"


def ensure_once(text: str, anchor: str, addition: str, label: str) -> str:
    if addition.strip() in text:
        return text
    if anchor not in text:
        raise SystemExit(f"Integration anchor not found: {label}")
    return text.replace(anchor, anchor + addition, 1)


def replace_required(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Integration anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")

    # Import. Safe when the previous integration script already inserted it.
    text = ensure_once(
        text,
        "from growth.growth_coach_adapter import build_growth_coach_payload\n",
        "from growth.post_intelligence_adapter import build_post_intelligence_payload\n",
        "adapter import",
    )

    # Response schema. Handle both untouched V10 and partially integrated files.
    if "post_intelligence: dict[str, Any] | None = None" not in text:
        schema_anchor = (
            "    # V10 decision layer: one action today plus the next priorities.\n"
            "    ai_growth_coach: dict[str, Any] | None = None\n"
        )
        text = ensure_once(
            text,
            schema_anchor,
            "\n    # V11 factual per-post dossiers; visual fields remain pending until Vision runs.\n"
            "    post_intelligence: dict[str, Any] | None = None\n",
            "response schema",
        )
    text = text.replace("    audit_version: int = 10\n", "    audit_version: int = 11\n", 1)

    # Fresh cache: enrich unconditionally before returning. This works even when
    # the old outer cache condition does not mention post_intelligence.
    fresh_return = "        return InstagramAnalyzeResponse(**fresh_cache)\n"
    fresh_insert = (
        "        if not fresh_cache.get(\"post_intelligence\"):\n"
        "            fresh_cache = dict(fresh_cache)\n"
        "            fresh_cache[\"post_intelligence\"] = build_post_intelligence_payload(cached_media)\n"
        "        fresh_cache[\"audit_version\"] = 11\n"
    )
    if fresh_insert.strip() not in text:
        if fresh_return not in text:
            raise SystemExit("Integration anchor not found: fresh cache return")
        text = text.replace(fresh_return, fresh_insert + fresh_return, 1)

    # Live payload build.
    live_anchor = (
        "        ai_growth_coach = build_growth_coach_payload(\n"
        "            profile_audit=profile_audit,\n"
        "            content_audit=content_audit,\n"
        "        )\n"
    )
    text = ensure_once(
        text,
        live_anchor,
        "        post_intelligence = build_post_intelligence_payload(recent_media)\n",
        "live payload build",
    )

    # Live response field and version/source.
    text = replace_required(
        text,
        "            ai_growth_coach=ai_growth_coach,\n            audit_version=10,\n            source=\"boxapi_public_analysis_v10\",\n",
        "            ai_growth_coach=ai_growth_coach,\n            post_intelligence=post_intelligence,\n            audit_version=11,\n            source=\"boxapi_public_analysis_v11\",\n",
        "live response",
    )

    # Stale cache: enrich unconditionally immediately before its return.
    stale_return = "            return InstagramAnalyzeResponse(**stale_cache)\n"
    stale_insert = (
        "            if not stale_cache.get(\"post_intelligence\"):\n"
        "                stale_cache[\"post_intelligence\"] = build_post_intelligence_payload(cached_media)\n"
        "            stale_cache[\"audit_version\"] = 11\n"
    )
    if stale_insert.strip() not in text:
        if stale_return not in text:
            raise SystemExit("Integration anchor not found: stale cache return")
        text = text.replace(stale_return, stale_insert + stale_return, 1)

    # Error response.
    text = replace_required(
        text,
        "            ai_growth_coach=None,\n            audit_version=10,\n",
        "            ai_growth_coach=None,\n            post_intelligence=None,\n            audit_version=11,\n",
        "error response",
    )

    TARGET.write_text(text, encoding="utf-8")
    print("Post Intelligence V11 robust integration applied to instagram_analyzer.py")


if __name__ == "__main__":
    main()

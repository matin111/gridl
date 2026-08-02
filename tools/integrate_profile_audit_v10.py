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

    source = replace_once(
        source,
        "from growth.evidence_engine import build_evidence_findings\n",
        "from growth.evidence_engine import build_evidence_findings\n"
        "from growth.profile_audit_adapter import build_profile_audit_payload\n",
        "profile audit import",
    )

    source = replace_once(
        source,
        "    # AI Growth Manager\n    growth_manager: dict[str, Any] | None = None\n\n    audit_version: int = 6\n",
        "    # AI Growth Manager\n    growth_manager: dict[str, Any] | None = None\n\n"
        "    # V10 evidence-based profile audit; additive for Android compatibility.\n"
        "    profile_audit: dict[str, Any] | None = None\n\n"
        "    audit_version: int = 10\n",
        "response schema",
    )

    source = replace_once(
        source,
        '            "evidence_findings": [],\n        }\n',
        '            "evidence_findings": [],\n            "profile_audit": None,\n        }\n',
        "empty content director context",
    )

    source = replace_once(
        source,
        '        "evidence_findings": analysis.evidence_findings,\n',
        '        "evidence_findings": analysis.evidence_findings,\n'
        '        "profile_audit": analysis.profile_audit,\n',
        "content director context",
    )

    source = replace_once(
        source,
        '        and safe_int(fresh_cache.get("audit_version")) >= 6\n    ):\n        return InstagramAnalyzeResponse(\n            **fresh_cache\n        )\n',
        '        and safe_int(fresh_cache.get("audit_version")) >= 7\n    ):\n'
        '        cached_profile = fresh_cache.get("profile")\n'
        '        if cached_profile and not fresh_cache.get("profile_audit"):\n'
        '            fresh_cache = dict(fresh_cache)\n'
        '            fresh_cache["profile_audit"] = build_profile_audit_payload(cached_profile)\n'
        '            fresh_cache["audit_version"] = 10\n'
        '        return InstagramAnalyzeResponse(**fresh_cache)\n',
        "fresh cache hydration",
    )

    source = replace_once(
        source,
        '        result = InstagramAnalyzeResponse(\n            success=True,\n',
        '        profile_audit = build_profile_audit_payload(profile)\n\n'
        '        result = InstagramAnalyzeResponse(\n            success=True,\n',
        "profile audit build",
    )

    source = replace_once(
        source,
        '            growth_manager=growth_manager.model_dump(mode="json"),\n            audit_version=7,\n            source="boxapi_public_analysis_v7",\n',
        '            growth_manager=growth_manager.model_dump(mode="json"),\n'
        '            profile_audit=profile_audit,\n'
        '            audit_version=10,\n'
        '            source="boxapi_public_analysis_v10",\n',
        "success response",
    )

    source = replace_once(
        source,
        '        if stale_cache is not None:\n            return InstagramAnalyzeResponse(\n                **stale_cache\n            )\n',
        '        if stale_cache is not None:\n'
        '            stale_cache = dict(stale_cache)\n'
        '            cached_profile = stale_cache.get("profile")\n'
        '            if cached_profile and not stale_cache.get("profile_audit"):\n'
        '                stale_cache["profile_audit"] = build_profile_audit_payload(cached_profile)\n'
        '                stale_cache["audit_version"] = 10\n'
        '            return InstagramAnalyzeResponse(**stale_cache)\n',
        "stale cache hydration",
    )

    source = replace_once(
        source,
        '            evidence_findings=[],\n            audit_version=6,\n            source="error",\n',
        '            evidence_findings=[],\n'
        '            profile_audit=None,\n'
        '            audit_version=10,\n'
        '            source="error",\n',
        "error response",
    )

    TARGET.write_text(source, encoding="utf-8")
    print("Profile Audit V10 integration applied to instagram_analyzer.py")


if __name__ == "__main__":
    main()

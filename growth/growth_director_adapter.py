from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, MutableMapping

from growth.growth_director import build_growth_director
from growth.next_content_engine import build_next_content


def _normalize_next_content(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """Expose stable user-facing names without removing the detailed V12.1 fields."""
    result = dict(payload or {})

    scenario = list(result.get("scenario_blueprint") or [])
    cta_strategy = dict(result.get("cta_strategy") or {})
    why = dict(result.get("why_this") or {})
    publish = dict(result.get("publish_time") or {})

    confidence_label = str(result.get("confidence") or "low")
    confidence_score = {
        "high": 90,
        "medium": 70,
        "low": 45,
    }.get(confidence_label, 45)

    # Stable aliases expected by the API/UI. Keep the original structured
    # fields too, so older and newer clients can coexist.
    result["scenario"] = scenario
    result["cta"] = cta_strategy
    result["why_this_content"] = why.get("summary")
    result["confidence_score"] = confidence_score
    result["publish_timezone"] = publish.get("timezone")
    result["evidence"] = {
        "format_basis": why.get("format_basis"),
        "pillar_basis": why.get("pillar_basis"),
        "evidence_signals": why.get("evidence_signals", 0),
        "hook_post_ids": list((result.get("hook_strategy") or {}).get("evidence_post_ids") or []),
        "cover_evidence": list((result.get("cover_strategy") or {}).get("evidence") or []),
    }
    return result


def build_growth_director_payload(
    *,
    profile_audit: Mapping[str, Any] | None,
    content_audit: Mapping[str, Any] | None,
    post_intelligence: Mapping[str, Any] | None,
    ai_growth_coach: Mapping[str, Any] | None,
    analytics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result = build_growth_director(
        profile_audit=profile_audit,
        content_audit=content_audit,
        post_intelligence=post_intelligence,
        ai_growth_coach=ai_growth_coach,
    )
    result["next_content"] = _normalize_next_content(
        build_next_content(
            post_intelligence=post_intelligence,
            daily_mission=result.get("daily_mission"),
            analytics=analytics,
        )
    )
    return result


def attach_growth_director(response: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    response["growth_director"] = build_growth_director_payload(
        profile_audit=response.get("profile_audit"),
        content_audit=response.get("content_audit"),
        post_intelligence=response.get("post_intelligence"),
        ai_growth_coach=response.get("ai_growth_coach"),
        analytics=response.get("analytics"),
    )
    return response


def enriched_response_copy(response: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(response))
    attach_growth_director(result)
    return result

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, MutableMapping

from growth.growth_director import build_growth_director


def build_growth_director_payload(
    *,
    profile_audit: Mapping[str, Any] | None,
    content_audit: Mapping[str, Any] | None,
    post_intelligence: Mapping[str, Any] | None,
    ai_growth_coach: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return build_growth_director(
        profile_audit=profile_audit,
        content_audit=content_audit,
        post_intelligence=post_intelligence,
        ai_growth_coach=ai_growth_coach,
    )


def attach_growth_director(response: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    response["growth_director"] = build_growth_director_payload(
        profile_audit=response.get("profile_audit"),
        content_audit=response.get("content_audit"),
        post_intelligence=response.get("post_intelligence"),
        ai_growth_coach=response.get("ai_growth_coach"),
    )
    return response


def enriched_response_copy(response: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(response))
    attach_growth_director(result)
    return result

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping, MutableMapping

from growth.ai_growth_coach import build_ai_growth_coach


def build_growth_coach_payload(
    *,
    profile_audit: Mapping[str, Any] | None,
    content_audit: Mapping[str, Any] | None,
    completed_keys: Iterable[str] = (),
) -> dict[str, Any]:
    """Build the additive V10 Growth Coach payload from existing audits."""
    return build_ai_growth_coach(
        profile_audit=profile_audit,
        content_audit=content_audit,
        completed_keys=completed_keys,
    )


def attach_growth_coach(
    response: MutableMapping[str, Any],
    *,
    completed_keys: Iterable[str] = (),
) -> MutableMapping[str, Any]:
    """Attach ai_growth_coach without removing or renaming legacy fields."""
    response["ai_growth_coach"] = build_growth_coach_payload(
        profile_audit=response.get("profile_audit"),
        content_audit=response.get("content_audit"),
        completed_keys=completed_keys,
    )
    return response


def enriched_response_copy(
    response: Mapping[str, Any],
    *,
    completed_keys: Iterable[str] = (),
) -> dict[str, Any]:
    result = deepcopy(dict(response))
    attach_growth_coach(result, completed_keys=completed_keys)
    return result

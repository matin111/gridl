from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, MutableMapping

from growth.profile_audit import audit_profile


def build_profile_audit_payload(profile: object | Mapping[str, Any]) -> dict[str, Any]:
    """Return the V10 profile audit payload for an API/model profile object."""
    return audit_profile(profile)


def attach_profile_audit(
    response: MutableMapping[str, Any],
    profile: object | Mapping[str, Any],
) -> MutableMapping[str, Any]:
    """Attach profile_audit without removing or renaming legacy response fields."""
    response["profile_audit"] = build_profile_audit_payload(profile)
    return response


def enriched_response_copy(
    response: Mapping[str, Any],
    profile: object | Mapping[str, Any],
) -> dict[str, Any]:
    """Pure helper useful for cache hydration and tests."""
    result = deepcopy(dict(response))
    attach_profile_audit(result, profile)
    return result

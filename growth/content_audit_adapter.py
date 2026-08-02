from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping, MutableMapping

from growth.content_audit import audit_content


def build_content_audit_payload(
    media: Iterable[object | Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the additive V10 content-audit payload from recent media."""
    return audit_content(media)


def attach_content_audit(
    response: MutableMapping[str, Any],
    media: Iterable[object | Mapping[str, Any]],
) -> MutableMapping[str, Any]:
    """Attach content_audit without removing or renaming legacy fields."""
    response["content_audit"] = build_content_audit_payload(media)
    return response


def enriched_response_copy(
    response: Mapping[str, Any],
    media: Iterable[object | Mapping[str, Any]],
) -> dict[str, Any]:
    result = deepcopy(dict(response))
    attach_content_audit(result, media)
    return result

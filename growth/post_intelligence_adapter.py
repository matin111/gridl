from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping, MutableMapping

from growth.post_intelligence import build_post_intelligence


def build_post_intelligence_payload(
    media: Iterable[object | Mapping[str, Any]],
) -> dict[str, Any]:
    return build_post_intelligence(media)


def attach_post_intelligence(
    response: MutableMapping[str, Any],
    media: Iterable[object | Mapping[str, Any]],
) -> MutableMapping[str, Any]:
    response["post_intelligence"] = build_post_intelligence_payload(media)
    response["audit_version"] = max(int(response.get("audit_version", 0) or 0), 11)
    return response


def enriched_response_copy(
    response: Mapping[str, Any],
    media: Iterable[object | Mapping[str, Any]],
) -> dict[str, Any]:
    result = deepcopy(dict(response))
    attach_post_intelligence(result, media)
    return result

from __future__ import annotations

import asyncio
import json
import os
import re
from copy import deepcopy
from typing import Any, Mapping

import httpx


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini").strip()
VISUAL_ANALYSIS_LIMIT = max(0, int(os.getenv("VISUAL_ANALYSIS_LIMIT", "4") or 4))
VISUAL_ANALYSIS_CONCURRENCY = max(1, int(os.getenv("VISUAL_ANALYSIS_CONCURRENCY", "2") or 2))

_SCORE_FIELDS = (
    "cover_score",
    "scroll_stop_score",
    "text_readability",
    "contrast_score",
    "composition_score",
    "brand_consistency_score",
)


def _clamp_score(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return max(0, min(round(float(value)), 100))
    except (TypeError, ValueError):
        return None


def _clean_strings(value: Any, limit: int = 5) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in result:
            result.append(text[:300])
        if len(result) >= limit:
            break
    return result


def _extract_json_text(text: str) -> Mapping[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("Vision response did not contain a JSON object")
        data = json.loads(match.group(0))
    if not isinstance(data, Mapping):
        raise ValueError("Vision response JSON must be an object")
    return data


def _response_output_text(payload: Mapping[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    chunks: list[str] = []
    for item in payload.get("output", []) or []:
        if not isinstance(item, Mapping):
            continue
        for part in item.get("content", []) or []:
            if not isinstance(part, Mapping):
                continue
            text = part.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks).strip()


def normalize_visual_result(raw: Mapping[str, Any], *, model: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "completed",
        "provider": "openai",
        "model": model,
        "cover_score": None,
        "scroll_stop_score": None,
        "ocr_text": None,
        "face_detected": None,
        "text_readability": None,
        "contrast_score": None,
        "composition_score": None,
        "brand_consistency_score": None,
        "main_subject": str(raw.get("main_subject") or "unknown")[:120],
        "text_amount": str(raw.get("text_amount") or "unknown")[:40],
        "strengths": _clean_strings(raw.get("strengths")),
        "weaknesses": _clean_strings(raw.get("weaknesses")),
        "recommendations": _clean_strings(raw.get("recommendations")),
        "reason": "image_analyzed_by_openai_vision",
    }
    for field in _SCORE_FIELDS:
        result[field] = _clamp_score(raw.get(field))
    ocr_text = raw.get("ocr_text")
    result["ocr_text"] = str(ocr_text).strip()[:1000] if ocr_text else None
    face = raw.get("face_detected")
    result["face_detected"] = face if isinstance(face, bool) else None
    return result


def _prompt(caption: str, media_type: str) -> str:
    return f"""You are auditing an Instagram {media_type} cover for a professional growth assistant.
Analyze only what is visibly present in the supplied image. Do not infer retention, reach, saves, shares, demographics, or business results from the image.
Caption context (may be incomplete): {caption[:800]}

Return one JSON object only with these exact keys:
cover_score, scroll_stop_score, ocr_text, face_detected, text_readability, contrast_score, composition_score, brand_consistency_score, main_subject, text_amount, strengths, weaknesses, recommendations.
Scores must be integers 0-100. face_detected must be true or false. text_amount must be one of none, low, medium, high. strengths, weaknesses, recommendations must be short Persian strings, maximum 5 items each.
Judge mobile-feed readability, clarity of focal subject, visual hierarchy, contrast, clutter, and consistency. Make no guaranteed performance claims."""


async def analyze_cover(
    *,
    image_url: str,
    caption: str = "",
    media_type: str = "post",
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    if not image_url.strip():
        return {"status": "unavailable", "reason": "thumbnail_url_not_available"}
    if not OPENAI_API_KEY:
        return {"status": "skipped", "reason": "openai_api_key_not_configured"}

    body = {
        "model": OPENAI_VISION_MODEL,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": _prompt(caption, media_type)},
                    {"type": "input_image", "image_url": image_url, "detail": "high"},
                ],
            }
        ],
        "temperature": 0.1,
        "max_output_tokens": 900,
    }
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=15, read=75, write=20, pool=20),
            follow_redirects=True,
        )
    try:
        response = await client.post(
            f"{OPENAI_BASE_URL}/responses",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        response.raise_for_status()
        payload = response.json()
        text = _response_output_text(payload)
        if not text:
            raise ValueError("OpenAI Vision returned no text output")
        return normalize_visual_result(_extract_json_text(text), model=OPENAI_VISION_MODEL)
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as error:
        return {
            "status": "failed",
            "reason": "vision_request_failed",
            "error": str(error)[:300],
        }
    finally:
        if owns_client:
            await client.aclose()


async def enrich_post_intelligence_with_vision(
    post_intelligence: Mapping[str, Any] | None,
    *,
    max_images: int | None = None,
) -> dict[str, Any] | None:
    if post_intelligence is None:
        return None
    result = deepcopy(dict(post_intelligence))
    posts = result.get("posts")
    if not isinstance(posts, list):
        return result

    limit = VISUAL_ANALYSIS_LIMIT if max_images is None else max(0, max_images)
    semaphore = asyncio.Semaphore(VISUAL_ANALYSIS_CONCURRENCY)
    selected: list[tuple[int, Mapping[str, Any]]] = []
    for index, post in enumerate(posts):
        if len(selected) >= limit:
            break
        if not isinstance(post, Mapping):
            continue
        visual = post.get("visual") or {}
        if visual.get("status") == "pending" and post.get("thumbnail_url"):
            selected.append((index, post))

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=15, read=75, write=20, pool=20),
        follow_redirects=True,
    ) as client:
        async def run(index: int, post: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
            async with semaphore:
                caption_info = post.get("caption") or {}
                hook_info = post.get("hook") or {}
                context = str(hook_info.get("text") or "")
                if caption_info.get("cta_present"):
                    context += "\nCTA exists in caption."
                visual = await analyze_cover(
                    image_url=str(post.get("thumbnail_url") or ""),
                    caption=context,
                    media_type=str(post.get("media_type") or "post"),
                    client=client,
                )
                return index, visual

        completed = await asyncio.gather(*(run(index, post) for index, post in selected))

    for index, visual in completed:
        posts[index] = dict(posts[index])
        posts[index]["visual"] = visual

    completed_count = sum(
        1 for post in posts
        if isinstance(post, Mapping) and (post.get("visual") or {}).get("status") == "completed"
    )
    result["visual_analysis_completed"] = completed_count
    result["visual_analysis_requested"] = len(selected)
    result["visual_provider"] = "openai" if selected else None
    return result

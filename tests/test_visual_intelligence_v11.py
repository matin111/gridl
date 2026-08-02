import json

import httpx
import pytest

from growth import visual_intelligence as vi


def test_normalize_visual_result_clamps_and_cleans():
    result = vi.normalize_visual_result(
        {
            "cover_score": 140,
            "scroll_stop_score": -5,
            "text_readability": "77",
            "contrast_score": 61.4,
            "composition_score": None,
            "brand_consistency_score": 58,
            "ocr_text": "  متن روی کاور  ",
            "face_detected": True,
            "main_subject": "person",
            "text_amount": "medium",
            "strengths": ["تیتر واضح", "تیتر واضح", "کنتراست مناسب"],
            "weaknesses": ["لوگو کوچک"],
            "recommendations": ["لوگو را بزرگ‌تر کن"],
        },
        model="vision-test",
    )
    assert result["status"] == "completed"
    assert result["cover_score"] == 100
    assert result["scroll_stop_score"] == 0
    assert result["text_readability"] == 77
    assert result["contrast_score"] == 61
    assert result["composition_score"] is None
    assert result["ocr_text"] == "متن روی کاور"
    assert result["face_detected"] is True
    assert result["strengths"] == ["تیتر واضح", "کنتراست مناسب"]


def test_extract_json_text_accepts_markdown_fence():
    parsed = vi._extract_json_text('```json\n{"cover_score": 80}\n```')
    assert parsed["cover_score"] == 80


@pytest.mark.asyncio
async def test_analyze_cover_returns_unavailable_without_url():
    result = await vi.analyze_cover(image_url="")
    assert result == {"status": "unavailable", "reason": "thumbnail_url_not_available"}


@pytest.mark.asyncio
async def test_analyze_cover_parses_openai_response(monkeypatch):
    monkeypatch.setattr(vi, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(vi, "OPENAI_BASE_URL", "https://api.test/v1")
    monkeypatch.setattr(vi, "OPENAI_VISION_MODEL", "vision-test")

    output = {
        "cover_score": 82,
        "scroll_stop_score": 76,
        "ocr_text": "سه اشتباه مهم",
        "face_detected": False,
        "text_readability": 88,
        "contrast_score": 79,
        "composition_score": 70,
        "brand_consistency_score": 66,
        "main_subject": "typography",
        "text_amount": "medium",
        "strengths": ["تیتر خواناست"],
        "weaknesses": ["سوژه انسانی ندارد"],
        "recommendations": ["نقطه تمرکز را واضح‌تر کن"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://api.test/v1/responses")
        body = json.loads(request.content)
        assert body["input"][0]["content"][1]["type"] == "input_image"
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": json.dumps(output, ensure_ascii=False)}
                        ]
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await vi.analyze_cover(
            image_url="https://example.com/cover.jpg",
            caption="نمونه کپشن",
            media_type="reel",
            client=client,
        )

    assert result["status"] == "completed"
    assert result["provider"] == "openai"
    assert result["cover_score"] == 82
    assert result["ocr_text"] == "سه اشتباه مهم"


@pytest.mark.asyncio
async def test_enrich_updates_only_selected_pending_posts(monkeypatch):
    async def fake_analyze_cover(**kwargs):
        return {
            "status": "completed",
            "provider": "openai",
            "model": "test",
            "cover_score": 75,
        }

    monkeypatch.setattr(vi, "analyze_cover", fake_analyze_cover)
    source = {
        "version": 11,
        "posts": [
            {
                "post_id": "1",
                "thumbnail_url": "https://example.com/1.jpg",
                "media_type": "reel",
                "hook": {"text": "هوک"},
                "caption": {"cta_present": True},
                "visual": {"status": "pending"},
            },
            {
                "post_id": "2",
                "thumbnail_url": "https://example.com/2.jpg",
                "media_type": "image",
                "hook": {"text": "هوک دوم"},
                "caption": {"cta_present": False},
                "visual": {"status": "pending"},
            },
        ],
    }
    result = await vi.enrich_post_intelligence_with_vision(source, max_images=1)
    assert result["posts"][0]["visual"]["status"] == "completed"
    assert result["posts"][1]["visual"]["status"] == "pending"
    assert result["visual_analysis_completed"] == 1
    assert result["visual_analysis_requested"] == 1

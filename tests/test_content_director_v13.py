import json

import pytest

import growth.content_director_v13 as module


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.request = None

    async def post(self, url, headers=None, json=None):
        self.request = {"url": url, "headers": headers, "json": json}
        return FakeResponse(self.payload)


def inputs():
    return {
        "profile": {"username": "matinvpn", "biography": "فروش سرویس VPN"},
        "analytics": {"suggested_publish_time": "12:00", "suggested_publish_timezone": "Asia/Tehran"},
        "growth_director": {
            "daily_mission": {"title": "CTA اضافه کن", "success_metric": "نرخ کامنت را مقایسه کن"},
            "next_content": {
                "goal": "increase_comments",
                "recommended_format": "carousel",
                "scenario": [{"step": 1, "instruction": "توقف اسکرول"}],
                "cta": {"recommended_cta": "نظر بده"},
                "publish_time": {"time": "12:00", "timezone": "Asia/Tehran"},
                "confidence_score": 90,
            },
        },
        "post_intelligence": {"posts": []},
        "content_audit": {"score": 70},
    }


def test_context_is_compact_and_keeps_real_page_data():
    data = inputs()
    context = module.build_content_director_context(**data)
    assert context["profile"]["username"] == "matinvpn"
    assert context["next_content"]["recommended_format"] == "carousel"
    assert context["analytics"]["suggested_publish_timezone"] == "Asia/Tehran"


@pytest.mark.asyncio
async def test_returns_brief_only_without_api_key(monkeypatch):
    monkeypatch.setattr(module, "OPENAI_API_KEY", "")
    result = await module.generate_content_director(**inputs())
    assert result["status"] == "brief_only"
    assert result["content_type"] == "carousel"
    assert result["cta"] is not None
    assert result["topic"] is None


@pytest.mark.asyncio
async def test_parses_openai_json_and_preserves_contract(monkeypatch):
    monkeypatch.setattr(module, "OPENAI_API_KEY", "test-key")
    generated = {
        "topic": "انتخاب پروتکل مناسب VPN",
        "title": "کدام پروتکل برای تو بهتر است؟",
        "hook": "اینترنتت کند نیست؛ پروتکلت اشتباه است.",
        "slides": [{"index": 1, "headline": "شروع", "body": "متن"}],
        "scenario": [],
        "caption": "کپشن آماده",
        "cta": "تو از کدام پروتکل استفاده می‌کنی؟",
        "hashtags": ["#VPN", "#CiscoVPN"],
        "first_comment": "پروتکلت را بنویس",
        "cover": {"headline": "پروتکل درست"},
        "measurement": {"primary_metric": "comments"},
    }
    payload = {"output_text": json.dumps(generated, ensure_ascii=False)}
    client = FakeClient(payload)
    result = await module.generate_content_director(**inputs(), client=client)
    assert result["status"] == "ready"
    assert result["provider"] == "openai"
    assert result["content_goal"] == "increase_comments"
    assert result["content_type"] == "carousel"
    assert result["topic"] == "انتخاب پروتکل مناسب VPN"
    assert result["publish_plan"]["timezone"] == "Asia/Tehran"
    assert client.request["url"].endswith("/responses")


@pytest.mark.asyncio
async def test_invalid_model_response_falls_back_without_breaking_analyzer(monkeypatch):
    monkeypatch.setattr(module, "OPENAI_API_KEY", "test-key")
    client = FakeClient({"output_text": "not-json"})
    result = await module.generate_content_director(**inputs(), client=client)
    assert result["status"] == "brief_only"
    assert result["content_type"] == "carousel"
    assert result["limitations"]

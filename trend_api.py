import json
import os
import traceback
from hashlib import sha256
from time import monotonic
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/v1/trends",
    tags=["Trends"],
)

APP_API_TOKEN = os.getenv("APP_API_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL",
    "https://api.openai.com/v1",
).rstrip("/")
OPENAI_FAST_MODEL = os.getenv(
    "OPENAI_FAST_MODEL",
    os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
).strip()

TREND_CACHE_TTL_SECONDS = int(
    os.getenv("TREND_CACHE_TTL_SECONDS", "900")
)

_trend_cache: dict[str, tuple[float, Any]] = {}


class TrendSearchRequest(BaseModel):
    query: str = Field(default="", max_length=300)
    platform: str = Field(default="اینستاگرام", max_length=50)
    category: str = Field(default="همه", max_length=50)
    count: int = Field(default=8, ge=3, le=12)
    force_refresh: bool = False


class TrendItemResponse(BaseModel):
    id: str
    platform: str
    category: str
    title: str
    format: str
    growth_percent: int
    score: int
    competition: str
    best_time: str
    description: str
    keywords: list[str]
    status: str
    opportunity_score: int
    remaining_days: int
    ai_reason: str


class TrendSearchResponse(BaseModel):
    success: bool
    items: list[TrendItemResponse] = []
    source: str = ""
    query: str = ""
    platform: str = ""
    message: str | None = None


def verify_app_token(authorization: str | None) -> None:
    if not APP_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="APP_API_TOKEN روی سرور تنظیم نشده است",
        )

    if authorization != f"Bearer {APP_API_TOKEN}":
        raise HTTPException(
            status_code=401,
            detail="دسترسی غیرمجاز",
        )


def _cache_key(request: TrendSearchRequest) -> str:
    raw = json.dumps(
        request.model_dump(exclude={"force_refresh"}),
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")

    return sha256(raw).hexdigest()


def _cache_get(key: str) -> Any | None:
    cached = _trend_cache.get(key)

    if cached is None:
        return None

    created_at, value = cached

    if monotonic() - created_at > TREND_CACHE_TTL_SECONDS:
        _trend_cache.pop(key, None)
        return None

    return value


def _cache_set(key: str, value: Any) -> None:
    if len(_trend_cache) >= 300:
        oldest_key = min(
            _trend_cache,
            key=lambda item_key: _trend_cache[item_key][0],
        )
        _trend_cache.pop(oldest_key, None)

    _trend_cache[key] = (
        monotonic(),
        value,
    )


def _extract_openai_text(data: dict[str, Any]) -> str:
    output_text = data.get("output_text")

    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    parts: list[str] = []

    for output_item in data.get("output", []):
        if not isinstance(output_item, dict):
            continue

        for content_item in output_item.get("content", []):
            if not isinstance(content_item, dict):
                continue

            text = content_item.get("text")

            if isinstance(text, str) and text.strip():
                parts.append(text.strip())

    return "\n".join(parts).strip()


def _trend_schema(count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "platform": {"type": "string"},
                        "category": {"type": "string"},
                        "title": {"type": "string"},
                        "format": {"type": "string"},
                        "growth_percent": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "score": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                        },
                        "competition": {
                            "type": "string",
                            "enum": ["کم", "متوسط", "زیاد"],
                        },
                        "best_time": {"type": "string"},
                        "description": {"type": "string"},
                        "keywords": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 10,
                            "items": {"type": "string"},
                        },
                        "status": {"type": "string"},
                        "opportunity_score": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 99,
                        },
                        "remaining_days": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 30,
                        },
                        "ai_reason": {"type": "string"},
                    },
                    "required": [
                        "id",
                        "platform",
                        "category",
                        "title",
                        "format",
                        "growth_percent",
                        "score",
                        "competition",
                        "best_time",
                        "description",
                        "keywords",
                        "status",
                        "opportunity_score",
                        "remaining_days",
                        "ai_reason",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    }


def _instructions() -> str:
    return """
تو موتور پیشنهاد ترند برای یک اپ حرفه‌ای تولید محتوا هستی.

وظیفه:
برای موضوع و پلتفرم کاربر، فرصت‌های محتوایی کاربردی و قابل اجرا پیشنهاد بده.

قوانین مهم:
- تمام متن‌ها فارسی و طبیعی باشند.
- فقط JSON مطابق Schema تولید کن.
- نتیجه‌ها باید با عبارت جستجوی کاربر مرتبط باشند.
- اگر عبارت کاربر یک موضوع عمومی مثل «تولید محتوا» است، زیرموضوع‌های مشخص و کاربردی پیشنهاد بده.
- اگر query خالی است، موضوع‌های عمومی پرتقاضا و مناسب همان پلتفرم پیشنهاد بده.
- عددها برآورد تحلیلی AI هستند؛ ادعای دسترسی زنده به آمار پلتفرم نکن.
- titleها تکراری نباشند.
- description باید روش اجرای کوتاه و روشن بدهد.
- ai_reason باید توضیح دهد چرا این ایده برای کاربر مناسب است.
- id فقط انگلیسی، عدد و خط تیره باشد.
- best_time به شکل فارسی مانند «۱۸ تا ۲۱» باشد.
- status یکی از این عبارت‌ها باشد:
  «در حال انفجار»، «رشد سریع»، «رو به رشد»، «فرصت پایدار».
- دسته‌بندی با پلتفرم سازگار باشد.
""".strip()


def _input_text(request: TrendSearchRequest) -> str:
    query = request.query.strip() or "موضوع‌های عمومی و پرتقاضای تولید محتوا"
    category = request.category.strip() or "همه"

    return f"""
عبارت جستجو:
{query}

پلتفرم:
{request.platform}

دسته‌بندی:
{category}

تعداد پیشنهاد:
{request.count}

پیشنهادها باید:
- مستقیماً برای ساخت محتوا قابل استفاده باشند.
- قالب مناسب پلتفرم داشته باشند.
- از کلی‌گویی دور باشند.
- برای هر مورد رشد، رقابت، فرصت، زمان انتشار و دلیل پیشنهاد ارائه کنند.
""".strip()


async def _request_openai(
    request: TrendSearchRequest,
) -> list[dict[str, Any]]:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY روی سرور تنظیم نشده است"
        )

    schema = _trend_schema(request.count)

    payload = {
        "model": OPENAI_FAST_MODEL,
        "instructions": _instructions(),
        "input": _input_text(request),
        "temperature": 0.72,
        "max_output_tokens": 4500,
        "store": False,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "trend_search_result",
                "schema": schema,
                "strict": True,
            }
        },
    }

    timeout = httpx.Timeout(
        connect=20.0,
        read=120.0,
        write=30.0,
        pool=20.0,
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{OPENAI_BASE_URL}/responses",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        detail = response.text[:1800]

        try:
            error_data = response.json()
            error_object = error_data.get("error")

            if isinstance(error_object, dict):
                detail = str(
                    error_object.get("message")
                    or detail
                )
        except ValueError:
            pass

        raise RuntimeError(
            f"OpenAI API error {response.status_code}: {detail}"
        )

    data = response.json()
    text = _extract_openai_text(data)

    if not text:
        raise RuntimeError(
            "پاسخ متنی معتبری از OpenAI دریافت نشد"
        )

    parsed = json.loads(text)
    items = parsed.get("items")

    if not isinstance(items, list):
        raise RuntimeError(
            "ساختار پاسخ ترند نامعتبر است"
        )

    return items


@router.post(
    "/search",
    response_model=TrendSearchResponse,
)
async def search_trends(
    request: TrendSearchRequest,
    authorization: str | None = Header(default=None),
) -> TrendSearchResponse:
    verify_app_token(authorization)

    key = _cache_key(request)

    if not request.force_refresh:
        cached = _cache_get(key)

        if isinstance(cached, list):
            return TrendSearchResponse(
                success=True,
                items=cached,
                source="openai_cache",
                query=request.query,
                platform=request.platform,
            )

    try:
        raw_items = await _request_openai(request)
        valid_items = [
            TrendItemResponse.model_validate(item)
            for item in raw_items
        ]

        _cache_set(
            key,
            [item.model_dump() for item in valid_items],
        )

        return TrendSearchResponse(
            success=True,
            items=valid_items,
            source="openai",
            query=request.query,
            platform=request.platform,
        )

    except Exception as error:
        print(
            "TREND API ERROR:",
            repr(error),
            flush=True,
        )
        traceback.print_exc()

        return TrendSearchResponse(
            success=False,
            items=[],
            source="error",
            query=request.query,
            platform=request.platform,
            message=str(error),
        )

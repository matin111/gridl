import traceback
import json
import os
import re
from hashlib import sha256
from time import monotonic
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


# =========================================================
# Environment
# =========================================================

load_dotenv()

APP_API_TOKEN = os.getenv("APP_API_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL",
    "https://api.openai.com/v1",
).rstrip("/")

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4.1-mini",
).strip()

OPENAI_FAST_MODEL = os.getenv(
    "OPENAI_FAST_MODEL",
    OPENAI_MODEL,
).strip()

OPENAI_TEXT_MODEL = os.getenv(
    "OPENAI_TEXT_MODEL",
    OPENAI_MODEL,
).strip()

CACHE_TTL_SECONDS = int(
    os.getenv("CACHE_TTL_SECONDS", "900")
)

CACHE_MAX_ITEMS = int(
    os.getenv("CACHE_MAX_ITEMS", "500")
)

_response_cache: dict[str, tuple[float, Any]] = {}


# =========================================================
# FastAPI
# =========================================================

from video_audio_routes import router as video_audio_router
from auth_routes import router as auth_router
app = FastAPI(

    title="AIStudioPro API",
    description="Structured OpenAI backend for AIStudioPro",
    version="8.0.0",
)

# AIStudioPro real video and speech routes
app.include_router(video_audio_router)
app.include_router(auth_router)
app.mount(
    "/generated",
    StaticFiles(directory="/root/aistudio-api/generated"),
    name="generated",
)


# =========================================================
# Schemas
# =========================================================

class HashtagRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=500)

    content_type: Literal[
        "آموزشی",
        "فروش",
        "سرگرمی",
        "برند",
    ] = "آموزشی"

    count: int = Field(default=10, ge=5, le=30)

    competition: Literal[
        "کم",
        "متوسط",
        "زیاد",
    ] = "متوسط"


class HashtagResponse(BaseModel):
    success: bool
    hashtags: list[str]
    source: str
    message: str | None = None


class AIRequest(BaseModel):
    tool: Literal[
        "hashtags",
        "caption",
        "content_ideas",
        "reel_script",
        "hooks",
        "image_prompt",
        "video_prompt",
        "cta",
        "comment_reply",
        "ad_copy",
        "content_calendar",
        "profile_analysis",
    ]

    topic: str = Field(
        min_length=2,
        max_length=4000,
    )

    platform: str = Field(
        default="اینستاگرام",
        max_length=100,
    )

    format: str = Field(
        default="پست",
        max_length=100,
    )

    content_type: str = Field(
        default="آموزشی",
        max_length=500,
    )

    tone: str = Field(
        default="حرفه‌ای",
        max_length=120,
    )

    count: int = Field(
        default=10,
        ge=1,
        le=30,
    )

    competition: str = Field(
        default="متوسط",
        max_length=50,
    )

    model_config = {
        "extra": "ignore",
    }


class AIResponse(BaseModel):
    success: bool
    tool: str
    data: Any | None = None

    # Backward compatibility for the current Android client.
    result: Any | None = None

    source: str
    message: str | None = None


# =========================================================
# Authentication
# =========================================================

def verify_app_token(
    authorization: str | None,
) -> None:
    if not APP_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="APP_API_TOKEN روی سرور تنظیم نشده است",
        )

    expected = f"Bearer {APP_API_TOKEN}"

    if authorization != expected:
        raise HTTPException(
            status_code=401,
            detail="دسترسی غیرمجاز",
        )


# =========================================================
# Cache
# =========================================================

def make_cache_key(*parts: str) -> str:
    raw = "\x1f".join(parts).encode("utf-8")
    return sha256(raw).hexdigest()


def cache_get(key: str) -> Any | None:
    item = _response_cache.get(key)

    if item is None:
        return None

    created_at, value = item

    if monotonic() - created_at > CACHE_TTL_SECONDS:
        _response_cache.pop(key, None)
        return None

    return value


def cache_set(key: str, value: Any) -> None:
    if CACHE_MAX_ITEMS <= 0:
        return

    if len(_response_cache) >= CACHE_MAX_ITEMS:
        oldest_key = min(
            _response_cache,
            key=lambda item_key: _response_cache[item_key][0],
        )
        _response_cache.pop(oldest_key, None)

    _response_cache[key] = (
        monotonic(),
        value,
    )


# =========================================================
# OpenAI helpers
# =========================================================

def extract_openai_text(data: dict[str, Any]) -> str:
    output_text = data.get("output_text")

    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = data.get("output")

    if not isinstance(output, list):
        return ""

    parts: list[str] = []

    for item in output:
        if not isinstance(item, dict):
            continue

        content = item.get("content")

        if not isinstance(content, list):
            continue

        for content_item in content:
            if not isinstance(content_item, dict):
                continue

            text = content_item.get("text")

            if isinstance(text, str) and text.strip():
                parts.append(text.strip())

    return "\n".join(parts).strip()


async def request_openai_json(
    *,
    model: str,
    instructions: str,
    input_text: str,
    schema_name: str,
    schema: dict[str, Any],
    temperature: float,
    max_output_tokens: int,
    use_cache: bool = True,
) -> tuple[Any, bool]:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY روی سرور تنظیم نشده است"
        )

    if not model:
        raise RuntimeError(
            "نام مدل OpenAI روی سرور تنظیم نشده است"
        )

    schema_json = json.dumps(
        schema,
        ensure_ascii=False,
        sort_keys=True,
    )

    cache_key = make_cache_key(
        model,
        instructions,
        input_text,
        schema_name,
        schema_json,
        str(temperature),
        str(max_output_tokens),
    )

    if use_cache:
        cached = cache_get(cache_key)

        if cached is not None:
            return cached, True

    url = f"{OPENAI_BASE_URL}/responses"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "model": model,
        "instructions": instructions,
        "input": input_text,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "store": False,
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
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
            url,
            headers=headers,
            json=payload,
        )

    if response.status_code >= 400:
        detail = response.text[:1800]

        try:
            error_data = response.json()
            error_object = error_data.get("error")

            if isinstance(error_object, dict):
                message = error_object.get("message")
                code = error_object.get("code")

                if isinstance(message, str):
                    detail = message

                if code:
                    detail = f"{detail} ({code})"

        except ValueError:
            pass

        raise RuntimeError(
            f"OpenAI API error {response.status_code}: {detail}"
        )

    try:
        response_data = response.json()

    except ValueError as error:
        raise RuntimeError(
            "پاسخ OpenAI فرمت JSON معتبر ندارد"
        ) from error

    text = extract_openai_text(response_data)

    if not text:
        raise RuntimeError(
            "پاسخ متنی معتبری از OpenAI دریافت نشد"
        )

    try:
        parsed = json.loads(text)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "خروجی ساختاریافته OpenAI قابل پردازش نیست"
        ) from error

    if use_cache:
        cache_set(cache_key, parsed)

    return parsed, False


# =========================================================
# JSON schemas
# =========================================================

def schema_for_tool(
    tool: str,
    count: int,
) -> tuple[str, dict[str, Any]]:
    if tool == "hashtags":
        return (
            "hashtags_result",
            {
                "type": "object",
                "properties": {
                    "hashtags": {
                        "type": "array",
                        "minItems": count,
                        "maxItems": count,
                        "items": {
                            "type": "string",
                        },
                    }
                },
                "required": ["hashtags"],
                "additionalProperties": False,
            },
        )

    if tool == "caption":
        return (
            "caption_result",
            {
                "type": "object",
                "properties": {
                    "hook": {"type": "string"},
                    "caption": {"type": "string"},
                    "cta": {"type": "string"},
                    "hashtags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "hook",
                    "caption",
                    "cta",
                    "hashtags",
                ],
                "additionalProperties": False,
            },
        )

    if tool == "ad_copy":
        return (
            "ad_copy_result",
            {
                "type": "object",
                "properties": {
                    "headline": {
                        "type": "string",
                    },
                    "primary_text": {
                        "type": "string",
                    },
                    "benefits": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 3,
                        "items": {
                            "type": "string",
                        },
                    },
                    "offer": {
                        "type": "string",
                    },
                    "cta": {
                        "type": "string",
                    },
                    "hashtags": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 8,
                        "items": {
                            "type": "string",
                        },
                    },
                },
                "required": [
                    "headline",
                    "primary_text",
                    "benefits",
                    "offer",
                    "cta",
                    "hashtags",
                ],
                "additionalProperties": False,
            },
        )

    if tool == "content_ideas":
        return (
            "content_ideas_result",
            {
                "type": "object",
                "properties": {
                    "ideas": {
                        "type": "array",
                        "minItems": count,
                        "maxItems": count,
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "format": {"type": "string"},
                                "description": {"type": "string"},
                                "hook": {"type": "string"},
                                "cta": {"type": "string"},
                            },
                            "required": [
                                "title",
                                "format",
                                "description",
                                "hook",
                                "cta",
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["ideas"],
                "additionalProperties": False,
            },
        )

    if tool == "reel_script":
        return (
            "reel_script_result",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "duration_seconds": {"type": "integer"},
                    "hook": {"type": "string"},
                    "scenes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "time": {"type": "string"},
                                "camera": {"type": "string"},
                                "voice": {"type": "string"},
                                "on_screen_text": {"type": "string"},
                                "b_roll": {"type": "string"},
                            },
                            "required": [
                                "time",
                                "camera",
                                "voice",
                                "on_screen_text",
                                "b_roll",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "cta": {"type": "string"},
                },
                "required": [
                    "title",
                    "duration_seconds",
                    "hook",
                    "scenes",
                    "cta",
                ],
                "additionalProperties": False,
            },
        )

    if tool == "hooks":
        return (
            "hooks_result",
            {
                "type": "object",
                "properties": {
                    "hooks": {
                        "type": "array",
                        "minItems": count,
                        "maxItems": count,
                        "items": {"type": "string"},
                    }
                },
                "required": ["hooks"],
                "additionalProperties": False,
            },
        )

    if tool == "image_prompt":
        return (
            "image_prompt_result",
            {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "negative_prompt": {"type": "string"},
                    "aspect_ratio": {"type": "string"},
                    "style": {"type": "string"},
                },
                "required": [
                    "prompt",
                    "negative_prompt",
                    "aspect_ratio",
                    "style",
                ],
                "additionalProperties": False,
            },
        )

    if tool == "video_prompt":
        return (
            "video_prompt_result",
            {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "negative_prompt": {"type": "string"},
                    "duration_seconds": {"type": "integer"},
                    "aspect_ratio": {"type": "string"},
                    "camera_motion": {"type": "string"},
                },
                "required": [
                    "prompt",
                    "negative_prompt",
                    "duration_seconds",
                    "aspect_ratio",
                    "camera_motion",
                ],
                "additionalProperties": False,
            },
        )

    if tool == "cta":
        return (
            "cta_result",
            {
                "type": "object",
                "properties": {
                    "ctas": {
                        "type": "array",
                        "minItems": count,
                        "maxItems": count,
                        "items": {"type": "string"},
                    }
                },
                "required": ["ctas"],
                "additionalProperties": False,
            },
        )

    if tool == "comment_reply":
        return (
            "comment_reply_result",
            {
                "type": "object",
                "properties": {
                    "reply": {"type": "string"},
                    "alternative_reply": {"type": "string"},
                },
                "required": [
                    "reply",
                    "alternative_reply",
                ],
                "additionalProperties": False,
            },
        )

    if tool == "ad_copy":
        return (
            "ad_copy_result",
            {
                "type": "object",
                "properties": {
                    "headline": {"type": "string"},
                    "body": {"type": "string"},
                    "benefit": {"type": "string"},
                    "trust_line": {"type": "string"},
                    "cta": {"type": "string"},
                },
                "required": [
                    "headline",
                    "body",
                    "benefit",
                    "trust_line",
                    "cta",
                ],
                "additionalProperties": False,
            },
        )

    if tool == "content_calendar":
        return (
            "content_calendar_result",
            {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "array",
                        "minItems": count,
                        "maxItems": count,
                        "items": {
                            "type": "object",
                            "properties": {
                                "day": {"type": "integer"},
                                "goal": {"type": "string"},
                                "title": {"type": "string"},
                                "format": {"type": "string"},
                                "hook": {"type": "string"},
                                "cta": {"type": "string"},
                                "execution": {"type": "string"},
                            },
                            "required": [
                                "day",
                                "goal",
                                "title",
                                "format",
                                "hook",
                                "cta",
                                "execution",
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["days"],
                "additionalProperties": False,
            },
        )

    if tool == "profile_analysis":
        return (
            "profile_analysis_result",
            {
                "type": "object",
                "properties": {
                    "strengths": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "weaknesses": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "positioning_problem": {"type": "string"},
                    "bio_suggestion": {"type": "string"},
                    "content_pillars": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "immediate_actions": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 3,
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "strengths",
                    "weaknesses",
                    "positioning_problem",
                    "bio_suggestion",
                    "content_pillars",
                    "immediate_actions",
                ],
                "additionalProperties": False,
            },
        )

    raise ValueError(
        f"ابزار پشتیبانی نمی‌شود: {tool}"
    )


# =========================================================
# Prompt builders
# =========================================================

def general_instructions(tool: str) -> str:
    roles = {
        "hashtags": "متخصص حرفه‌ای هشتگ‌گذاری فارسی",
        "caption": "نویسنده حرفه‌ای کپشن شبکه‌های اجتماعی",
        "content_ideas": "استراتژیست ایده‌پردازی محتوا",
        "reel_script": "سناریونویس حرفه‌ای ریلز",
        "hooks": "متخصص تولید هوک‌های جذاب",
        "image_prompt": "متخصص پرامپت‌نویسی تصویر",
        "video_prompt": "متخصص پرامپت‌نویسی ویدئو",
        "cta": "متخصص دعوت به اقدام",
        "comment_reply": "مدیر حرفه‌ای تعامل با مخاطب",
        "ad_copy": "کپی‌رایتر تبلیغاتی",
        "content_calendar": "استراتژیست تقویم محتوایی",
        "profile_analysis": "تحلیل‌گر حرفه‌ای پروفایل",
    }

    role = roles.get(
        tool,
        "دستیار حرفه‌ای تولید محتوا",
    )

    return f"""
تو یک {role} هستی.

قوانین:
- همه متن‌ها فارسی، روان، طبیعی و کاربردی باشند.
- خروجی دقیقاً مطابق ساختار JSON درخواستی باشد.
- هیچ توضیح خارج از JSON تولید نکن.
- از متن‌های کلی، تکراری و بی‌ربط خودداری کن.
- اطلاعات ساختگی یا ادعاهای غیرقابل‌اثبات تولید نکن.
""".strip()


def build_tool_input(request: AIRequest) -> str:
    base = f"""
موضوع:
{request.topic}

نوع محتوا:
{request.content_type}

لحن:
{request.tone}

تعداد:
{request.count}

سطح رقابت:
{request.competition}
""".strip()

    specific = {
        "hashtags": """
هشتگ‌ها باید مستقیماً به موضوع مرتبط باشند.
از هشتگ عمومی و نامرتبط استفاده نکن.
هر هشتگ با # شروع شود و فاصله داخل آن با زیرخط جایگزین شود.
""",
        "caption": """
یک کپشن آماده انتشار بساز.
هوک، متن اصلی، CTA و چند هشتگ مرتبط را جداگانه ارائه کن.
""",
        "content_ideas": """
ایده‌ها متنوع، قابل اجرا و مناسب شبکه‌های اجتماعی باشند.
برای هر ایده قالب، توضیح، هوک و CTA ارائه کن.
""",
        "reel_script": """
سناریو با موبایل قابل ضبط باشد.
صحنه‌ها، متن گویندگی، نوشته روی تصویر و B-Roll را دقیق بنویس.
""",
        "hooks": """
هوک‌ها کوتاه، متفاوت و مناسب سه ثانیه اول ریلز یا ابتدای کپشن باشند.
""",
        "image_prompt": """
یک پرامپت دقیق تصویری، Negative Prompt، نسبت تصویر و سبک پیشنهادی تولید کن.
""",
        "video_prompt": """
یک پرامپت سینمایی با حرکت دوربین، زمان، نسبت تصویر و Negative Prompt تولید کن.
""",
        "cta": """
CTAها طبیعی، کوتاه، متنوع و غیرکلیشه‌ای باشند.
""",
        "comment_reply": """
یک پاسخ اصلی و یک پاسخ جایگزین کوتاه، محترمانه و انسانی تولید کن.
""",
        "ad_copy": """
تیتر، بدنه، مزیت اصلی، جمله اعتمادساز و CTA را جداگانه تولید کن.
""",
        "content_calendar": """
برای هر روز هدف، عنوان، قالب، هوک، CTA و روش اجرای کوتاه ارائه کن.
""",
        "profile_analysis": """
نقاط قوت، ضعف، مشکل جایگاه، پیشنهاد بایو، ستون‌های محتوا و سه اقدام فوری ارائه کن.
""",
    }

    return f"{base}\n\n{specific[request.tool].strip()}"


# =========================================================
# AI generation
# =========================================================

def resolve_effective_tool(
    request: AIRequest,
) -> str:
    if request.tool != "caption":
        return request.tool

    output_format = request.format.strip()

    if "ریلز" in output_format:
        return "reel_script"

    if "تبلیغ" in output_format:
        return "ad_copy"

    return "caption"


def build_format_aware_input(
    request: AIRequest,
    effective_tool: str,
) -> str:
    topic = request.topic.strip()
    platform = (
        request.platform.strip()
        or "اینستاگرام"
    )
    output_format = (
        request.format.strip()
        or "پست"
    )
    content_type = (
        request.content_type.strip()
        or "آموزشی"
    )
    tone = (
        request.tone.strip()
        or "حرفه‌ای"
    )

    common = f"""
موضوع:
{topic}

پلتفرم:
{platform}

فرمت خروجی:
{output_format}

هدف محتوا:
{content_type}

لحن:
{tone}

قوانین:
- خروجی کاملاً فارسی و طبیعی باشد.
- فقط محتوای نهایی را بنویس.
- درباره فرایند تولید توضیح نده.
- از جمله‌های کلیشه‌ای و تکراری پرهیز کن.
- محتوا آماده استفاده مستقیم باشد.
""".strip()

    if effective_tool == "reel_script":
        return f"""
{common}

فقط یک سناریوی حرفه‌ای ریلز تولید کن.

ساختار:
- عنوان کوتاه
- مدت پیشنهادی ۱۵ تا ۳۰ ثانیه
- هوک قوی برای سه ثانیه اول
- حداقل سه صحنه

برای هر صحنه:
- زمان
- حرکت دوربین
- نریشن یا دیالوگ
- متن روی تصویر
- B-roll

در پایان یک CTA مناسب بنویس.

مقاله، کپشن طولانی یا متن تبلیغاتی تولید نکن.
""".strip()

    if effective_tool == "ad_copy":
        return f"""
{common}

فقط یک متن تبلیغاتی حرفه‌ای و فروش‌محور تولید کن.

ساختار:
- تیتر تبلیغاتی قوی
- نیاز یا مشکل مخاطب
- معرفی محصول یا پیشنهاد
- سه مزیت واقعی و مشخص
- پیشنهاد ویژه
- دعوت واضح به خرید، سفارش یا تماس

قوانین:
- حداکثر ۱۲۰ کلمه
- مقاله آموزشی ننویس
- سناریوی ریلز ننویس
- اغراق غیرواقعی نداشته باشد
- متن کاملاً آماده تبلیغ باشد
""".strip()

    if "متن" in output_format:
        return f"""
{common}

یک متن کامل و ساختاریافته تولید کن.

ساختار:
- عنوان روشن و جذاب
- مقدمه کوتاه
- بدنه کامل در چند پاراگراف
- سه تا پنج نکته کلیدی
- جمع‌بندی
- دعوت به اقدام کوتاه

قوانین:
- متن باید از پست شبکه اجتماعی طولانی‌تر باشد
- هشتگ تولید نکن
- سناریوی ویدیو تولید نکن
- متن شبیه مقاله کوتاه حرفه‌ای باشد
""".strip()

    return f"""
{common}

یک پست شبکه اجتماعی آماده انتشار تولید کن.

ساختار:
- عنوان کوتاه
- هوک توقف‌ساز
- متن اصلی در دو تا چهار پاراگراف کوتاه
- دعوت به اقدام
- پنج تا هشت هشتگ مرتبط

قوانین:
- مقاله طولانی ننویس
- سناریوی ویدیو تولید نکن
- متن باید برای انتشار مستقیم آماده باشد
""".strip()


def schema_for_caption_format(
    request: AIRequest,
) -> tuple[str, dict[str, Any]]:
    output_format = request.format.strip()

    if "متن" in output_format:
        return (
            "long_text_result",
            {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                    },
                    "introduction": {
                        "type": "string",
                    },
                    "body": {
                        "type": "string",
                    },
                    "key_points": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                    "conclusion": {
                        "type": "string",
                    },
                    "cta": {
                        "type": "string",
                    },
                },
                "required": [
                    "title",
                    "introduction",
                    "body",
                    "key_points",
                    "conclusion",
                    "cta",
                ],
                "additionalProperties": False,
            },
        )

    return (
        "social_post_result",
        {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                },
                "hook": {
                    "type": "string",
                },
                "body": {
                    "type": "string",
                },
                "cta": {
                    "type": "string",
                },
                "hashtags": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
            },
            "required": [
                "title",
                "hook",
                "body",
                "cta",
                "hashtags",
            ],
            "additionalProperties": False,
        },
    )


async def generate_tool_data(
    request: AIRequest,
) -> tuple[Any, bool]:
    effective_tool = resolve_effective_tool(
        request
    )

    if (
        request.tool == "caption"
        and effective_tool == "caption"
    ):
        schema_name, schema = (
            schema_for_caption_format(
                request
            )
        )
    else:
        schema_name, schema = schema_for_tool(
            effective_tool,
            request.count,
        )

    model = (
        OPENAI_FAST_MODEL
        if effective_tool in {
            "hashtags",
            "hooks",
            "cta",
            "comment_reply",
        }
        else OPENAI_TEXT_MODEL
    )

    max_tokens = {
        "hashtags": 700,
        "hooks": 900,
        "cta": 900,
        "comment_reply": 800,
        "caption": 2400,
        "content_ideas": 2800,
        "reel_script": 3200,
        "image_prompt": 1800,
        "video_prompt": 2200,
        "ad_copy": 1800,
        "content_calendar": 3600,
        "profile_analysis": 2800,
    }[effective_tool]

    return await request_openai_json(
        model=model,
        instructions=general_instructions(
            effective_tool
        ),
        input_text=build_format_aware_input(
            request=request,
            effective_tool=effective_tool,
        ),
        schema_name=schema_name,
        schema=schema,
        temperature=0.68,
        max_output_tokens=max_tokens,
        use_cache=True,
    )


# =========================================================
# Routes
# =========================================================

@app.get("/api-info")
async def root() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "AIStudioPro API",
        "provider": "openai",
        "output": "structured_json",
        "version": "8.0.0",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "AIStudioPro API",
        "provider": "openai",
        "fast_model": OPENAI_FAST_MODEL,
        "text_model": OPENAI_TEXT_MODEL,
        "output": "structured_json",
        "cache_ttl_seconds": str(
            CACHE_TTL_SECONDS
        ),
        "cache_items": str(
            len(_response_cache)
        ),
        "version": "8.0.0",
    }


@app.post("/admin/cache/clear")
async def clear_cache(
    authorization: str | None = Header(default=None),
) -> dict[str, int | str]:
    verify_app_token(authorization)

    cleared = len(_response_cache)
    _response_cache.clear()

    return {
        "status": "ok",
        "cleared_items": cleared,
    }


@app.post(
    "/v1/hashtags",
    response_model=HashtagResponse,
)
async def generate_hashtags(
    request: HashtagRequest,
    authorization: str | None = Header(default=None),
) -> HashtagResponse:
    verify_app_token(authorization)

    ai_request = AIRequest(
        tool="hashtags",
        topic=request.topic,
        content_type=request.content_type,
        tone="حرفه‌ای",
        count=request.count,
        competition=request.competition,
    )

    try:
        data, was_cached = await generate_tool_data(
            ai_request
        )

        hashtags = data.get("hashtags")

        if not isinstance(hashtags, list):
            raise RuntimeError(
                "ساختار هشتگ دریافتی نامعتبر است"
            )

        cleaned: list[str] = []

        for item in hashtags:
            if not isinstance(item, str):
                continue

            tag = item.strip()

            if not tag.startswith("#"):
                tag = f"#{tag}"

            tag = re.sub(r"\s+", "_", tag)

            if tag not in cleaned:
                cleaned.append(tag)

        if len(cleaned) != request.count:
            raise RuntimeError(
                "تعداد هشتگ دریافتی با تعداد درخواستی برابر نیست"
            )

        return HashtagResponse(
            success=True,
            hashtags=cleaned,
            source=(
                "openai_cache"
                if was_cached
                else "openai"
            ),
            message=None,
        )

    except Exception as error:
        print(
            "HASHTAG ERROR:",
            repr(error),
            flush=True,
        )

        return HashtagResponse(
            success=False,
            hashtags=[],
            source="error",
            message=str(error),
        )

def format_result_for_android(
    *,
    request: AIRequest,
    data: Any,
) -> Any:
    """
    خروجی آماده کپی برای اپ اندروید.
    عنوان‌های توضیحی مانند «هوک» و «متن اصلی»
    داخل خروجی نهایی نمایش داده نمی‌شوند.
    """
    effective_tool = resolve_effective_tool(
        request
    )

    if not isinstance(data, dict):
        return data

    def clean(value: Any) -> str:
        if value is None:
            return ""

        return str(value).strip()

    def add_unique(
        parts: list[str],
        value: Any,
    ) -> None:
        cleaned = clean(value)

        if cleaned and cleaned not in parts:
            parts.append(cleaned)

    # -----------------------------------------------------
    # ریلز
    # -----------------------------------------------------
    if effective_tool == "reel_script":
        parts: list[str] = []

        add_unique(
            parts,
            data.get("title"),
        )

        add_unique(
            parts,
            data.get("hook"),
        )

        scenes = data.get(
            "scenes",
            [],
        )

        if isinstance(scenes, list):
            for index, scene in enumerate(
                scenes,
                start=1,
            ):
                if not isinstance(
                    scene,
                    dict,
                ):
                    continue

                scene_lines: list[str] = [
                    f"صحنه {index}"
                ]

                time_value = clean(
                    scene.get("time")
                )

                camera = clean(
                    scene.get("camera")
                )

                voice = clean(
                    scene.get("voice")
                )

                on_screen_text = clean(
                    scene.get(
                        "on_screen_text"
                    )
                )

                b_roll = clean(
                    scene.get("b_roll")
                )

                if time_value:
                    scene_lines.append(
                        time_value
                    )

                if camera:
                    scene_lines.append(
                        camera
                    )

                if voice:
                    scene_lines.append(
                        voice
                    )

                if on_screen_text:
                    scene_lines.append(
                        on_screen_text
                    )

                if b_roll:
                    scene_lines.append(
                        b_roll
                    )

                parts.append(
                    "\n".join(scene_lines)
                )

        add_unique(
            parts,
            data.get("cta"),
        )

        return "\n\n".join(parts).strip()

    # -----------------------------------------------------
    # تبلیغ
    # -----------------------------------------------------
    if effective_tool == "ad_copy":
        parts: list[str] = []

        preferred_keys = [
            "headline",
            "title",
            "hook",
            "primary_text",
            "ad_copy",
            "body",
            "description",
            "problem",
            "solution",
            "offer",
            "cta",
        ]

        for key in preferred_keys:
            value = data.get(key)

            if isinstance(value, str):
                add_unique(
                    parts,
                    value,
                )

        benefits = data.get(
            "benefits",
            [],
        )

        if isinstance(benefits, list):
            clean_benefits = [
                clean(item)
                for item in benefits
                if clean(item)
            ]

            if clean_benefits:
                parts.append(
                    "\n".join(
                        f"• {item}"
                        for item in clean_benefits
                    )
                )

        hashtags = data.get(
            "hashtags",
            [],
        )

        if isinstance(hashtags, list):
            clean_hashtags = [
                clean(item)
                for item in hashtags
                if clean(item)
            ]

            if clean_hashtags:
                parts.append(
                    " ".join(clean_hashtags)
                )

        # دریافت فیلدهای احتمالی دیگر Schema
        ignored_keys = set(
            preferred_keys
            + [
                "benefits",
                "hashtags",
            ]
        )

        for key, value in data.items():
            if key in ignored_keys:
                continue

            if isinstance(value, str):
                add_unique(
                    parts,
                    value,
                )

            elif isinstance(value, list):
                items = [
                    clean(item)
                    for item in value
                    if clean(item)
                ]

                if items:
                    block = "\n".join(
                        f"• {item}"
                        for item in items
                    )

                    if block not in parts:
                        parts.append(block)

        return "\n\n".join(parts).strip()

    # -----------------------------------------------------
    # متن بلند
    # -----------------------------------------------------
    output_format = request.format.strip()

    if "متن" in output_format:
        parts: list[str] = []

        add_unique(
            parts,
            data.get("title"),
        )

        add_unique(
            parts,
            data.get("introduction"),
        )

        add_unique(
            parts,
            data.get("body"),
        )

        key_points = data.get(
            "key_points",
            [],
        )

        if isinstance(key_points, list):
            clean_points = [
                clean(item)
                for item in key_points
                if clean(item)
            ]

            if clean_points:
                parts.append(
                    "\n".join(
                        f"• {item}"
                        for item in clean_points
                    )
                )

        add_unique(
            parts,
            data.get("conclusion"),
        )

        add_unique(
            parts,
            data.get("cta"),
        )

        return "\n\n".join(parts).strip()

    # -----------------------------------------------------
    # پست شبکه اجتماعی
    # -----------------------------------------------------
    parts: list[str] = []

    add_unique(
        parts,
        data.get("title"),
    )

    add_unique(
        parts,
        data.get("hook"),
    )

    body = data.get(
        "body",
        data.get(
            "caption",
            "",
        ),
    )

    add_unique(
        parts,
        body,
    )

    add_unique(
        parts,
        data.get("cta"),
    )

    hashtags = data.get(
        "hashtags",
        [],
    )

    if isinstance(hashtags, list):
        clean_hashtags = [
            clean(item)
            for item in hashtags
            if clean(item)
        ]

        if clean_hashtags:
            parts.append(
                " ".join(clean_hashtags)
            )

    return "\n\n".join(parts).strip()


@app.post(
    "/v1/ai",
    response_model=AIResponse,
)
async def generate_ai_content(
    request: AIRequest,
    authorization: str | None = Header(default=None),
) -> AIResponse:
    verify_app_token(authorization)

    try:
        data, was_cached = await generate_tool_data(
            request
        )

        result = format_result_for_android(
            request=request,
            data=data,
        )

        return AIResponse(
            success=True,
            tool=request.tool,
            data=data,
            result=result,
            source=(
                "openai_cache"
                if was_cached
                else "openai"
            ),
            message=None,
        )

    except Exception as error:
        print(
            "AI CORE ERROR:",
            repr(error),
            flush=True,
        )
        traceback.print_exc()

        return AIResponse(
            success=False,
            tool=request.tool,
            data=None,
            result=None,
            source="error",
            message=str(error),
        )



# =========================================================
# AI Content Studio
# =========================================================

class ContentStudioGenerateRequest(BaseModel):
    platform: str = Field(min_length=2, max_length=100)
    contentType: str = Field(min_length=2, max_length=100)
    businessField: str = Field(min_length=2, max_length=300)
    topic: str = Field(min_length=2, max_length=1000)
    targetAudience: str = Field(min_length=2, max_length=500)
    goal: str = Field(min_length=2, max_length=120)
    tone: str = Field(min_length=2, max_length=120)
    contentLength: str = Field(default="متوسط", max_length=80)
    videoDuration: str = Field(default="۳۰ ثانیه", max_length=80)
    additionalDetails: str = Field(default="", max_length=2000)


def content_studio_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": (
                    "یک تیتر فارسی کوتاه، مشخص و جذاب؛ "
                    "حداکثر ۱۰ کلمه و بدون توضیح اضافه"
                ),
            },
            "mainIdea": {"type": "string"},
            "hook": {"type": "string"},
            "script": {"type": "string"},
            "shotList": {
                "type": "array",
                "minItems": 3,
                "maxItems": 8,
                "items": {"type": "string"},
            },
            "onScreenTexts": {
                "type": "array",
                "minItems": 3,
                "maxItems": 8,
                "items": {"type": "string"},
            },
            "caption": {"type": "string"},
            "callToAction": {"type": "string"},
            "hashtags": {
                "type": "array",
                "minItems": 5,
                "maxItems": 12,
                "items": {"type": "string"},
            },
            "coverSuggestion": {"type": "string"},
            "bestPublishTime": {"type": "string"},
            "musicSuggestion": {"type": "string"},
            "engagementTips": {
                "type": "array",
                "minItems": 3,
                "maxItems": 6,
                "items": {"type": "string"},
            },
        },
        "required": [
            "title",
            "mainIdea",
            "hook",
            "script",
            "shotList",
            "onScreenTexts",
            "caption",
            "callToAction",
            "hashtags",
            "coverSuggestion",
            "bestPublishTime",
            "musicSuggestion",
            "engagementTips",
        ],
        "additionalProperties": False,
    }


def build_content_studio_input(
    request: ContentStudioGenerateRequest,
) -> str:
    extra = (
        request.additionalDetails.strip()
        or "جزئیات تکمیلی ثبت نشده است."
    )

    return f"""
یک بسته محتوایی کامل و آماده اجرا تولید کن.

اطلاعات پروژه:
- پلتفرم: {request.platform}
- فرمت محتوا: {request.contentType}
- حوزه فعالیت: {request.businessField}
- موضوع اصلی: {request.topic}
- مخاطب هدف: {request.targetAudience}
- هدف: {request.goal}
- لحن: {request.tone}
- عمق خروجی: {request.contentLength}
- مدت ویدئو: {request.videoDuration}
- مزیت یا توضیحات تکمیلی: {extra}

قوانین حیاتی عنوان:
- title فقط یک تیتر نهایی باشد؛ نه پاراگراف، نه توضیح، نه استراتژی.
- حداکثر ۱۰ کلمه و ترجیحاً بین ۴ تا ۸ کلمه باشد.
- عنوان باید مشخص، طبیعی، مرتبط با موضوع و مناسب مخاطب باشد.
- از عبارت‌های کلیشه‌ای مانند «انتخابی که ارزش توجه دارد»،
  «این نکته را از دست نده» و «نگاهت را تغییر می‌دهد» استفاده نکن.
- عنوان نباید با «عنوان:» یا «تیتر:» شروع شود.
- از وعده غیرواقعی، آمار ساختگی و اغراق اثبات‌ناپذیر پرهیز کن.
- برای محتوای آموزشی از مسئله، نتیجه یا کنجکاوی واقعی استفاده کن.
- برای محتوای فروش، مزیت مشخص یا مسئله خرید را برجسته کن.
- برای محتوای وایرال، تیتر باید توقف‌ساز اما همچنان صادقانه باشد.

قوانین سایر بخش‌ها:
- hook باید مناسب ۳ ثانیه اول و با title متفاوت باشد.
- mainIdea توضیح کوتاه ایده مرکزی و زاویه محتوا باشد.
- script متناسب با فرمت انتخاب‌شده، مرحله‌بندی‌شده و قابل اجرا باشد.
- shotList شامل شات‌های واقعی و قابل ضبط با موبایل باشد.
- onScreenTexts کوتاه، خوانا و غیرتکراری باشند.
- caption آماده انتشار، طبیعی و متناسب با هدف باشد.
- callToAction فقط یک اقدام روشن بخواهد.
- هشتگ‌ها مستقیم و مرتبط باشند و با # شروع شوند.
- بهترین زمان انتشار را قطعی و ساختگی اعلام نکن؛
  یک بازه پیشنهادی برای تست بنویس.
- تمام خروجی فارسی روان و بدون توضیح خارج از JSON باشد.
""".strip()


def clean_content_studio_title(
    value: Any,
    fallback_topic: str,
) -> str:
    title = value if isinstance(value, str) else ""
    title = title.strip()

    if "\n" in title:
        title = next(
            (
                line.strip()
                for line in title.splitlines()
                if line.strip()
            ),
            "",
        )

    title = re.sub(
        r"^(عنوان|تیتر)\s*[:：\-]\s*",
        "",
        title,
        flags=re.IGNORECASE,
    )

    title = re.sub(r"\s+", " ", title)
    title = title.strip(" «»\"'.,،;؛:-")

    banned_titles = {
        "انتخابی که ارزش توجه دارد",
        "این نکته را از دست نده",
        "موضوع انتخاب‌شده",
    }

    if (
        not title
        or title in banned_titles
        or len(title.split()) > 12
        or len(title) > 100
    ):
        topic = re.sub(
            r"\s+",
            " ",
            fallback_topic.strip(),
        )

        return (
            f"راهنمای کاربردی {topic}"
            if topic
            else "یک ایده کاربردی برای محتوای امروز"
        )[:90].strip()

    return title


@app.post(
    "/v1/content-studio/generate",
    tags=["Content Studio"],
)
async def generate_content_studio(
    request: ContentStudioGenerateRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    verify_app_token(authorization)

    try:
        result, was_cached = await request_openai_json(
            model=OPENAI_TEXT_MODEL,
            instructions=(
                "تو یک استراتژیست ارشد محتوای فارسی، "
                "کپی‌رایتر و سناریونویس شبکه‌های اجتماعی هستی. "
                "خروجی باید دقیق، اختصاصی، قابل اجرا و مطابق JSON Schema باشد. "
                "مهم‌ترین قانون: فیلد title فقط یک تیتر کوتاه و حرفه‌ای است."
            ),
            input_text=build_content_studio_input(request),
            schema_name="content_studio_result",
            schema=content_studio_schema(),
            temperature=0.72,
            max_output_tokens=5200,
            use_cache=False,
        )

        if not isinstance(result, dict):
            raise RuntimeError(
                "ساختار خروجی Content Studio معتبر نیست"
            )

        result["title"] = clean_content_studio_title(
            result.get("title"),
            request.topic,
        )

        hashtags = result.get("hashtags")
        if isinstance(hashtags, list):
            cleaned_hashtags: list[str] = []

            for item in hashtags:
                if not isinstance(item, str):
                    continue

                tag = item.strip()
                if not tag:
                    continue

                if not tag.startswith("#"):
                    tag = f"#{tag}"

                tag = re.sub(r"\s+", "_", tag)

                if tag not in cleaned_hashtags:
                    cleaned_hashtags.append(tag)

            result["hashtags"] = cleaned_hashtags[:12]

        return {
            "success": True,
            "result": result,
            "source": (
                "openai_cache"
                if was_cached
                else "openai"
            ),
            "message": None,
        }

    except Exception as error:
        print(
            "CONTENT STUDIO ERROR:",
            repr(error),
            flush=True,
        )
        traceback.print_exc()

        return {
            "success": False,
            "result": None,
            "source": "error",
            "message": str(error),
        }


# Instagram Analyzer module
from instagram_analyzer import router as instagram_router
app.include_router(instagram_router)


# Online Dashboard module
from dashboard_api import router as dashboard_router
app.include_router(dashboard_router)


# Gemini image generation

# OpenAI image generation
from openai_image_api import router as openai_image_router

app.mount("/generated/images", StaticFiles(directory="/root/aistudio-api/generated/images"), name="generated_images")
app.include_router(openai_image_router)

# OpenAI image editing
from openai_image_edit_api import router as openai_image_edit_router

app.mount(
    "/generated/image-edits",
    StaticFiles(
        directory="/root/aistudio-api/generated/image-edits"
    ),
    name="generated_image_edits",
)

app.include_router(openai_image_edit_router)

# AI Growth Planner
from planner_api import router as planner_router
app.include_router(planner_router)

# Generated media retention
from media_retention_api import router as media_retention_router
app.include_router(media_retention_router)


# Subscription, campaigns and admin management
from subscription_admin_api import router as subscription_admin_router
app.include_router(subscription_admin_router)


# Web admin panel
from admin_panel import router as admin_panel_router
app.include_router(admin_panel_router)

# Release Center
from admin.releases import router as releases_router
app.include_router(releases_router)


# Public landing assets
os.makedirs("/root/aistudio-api/site-assets", exist_ok=True)

app.mount(
    "/site-assets",
    StaticFiles(
        directory="/root/aistudio-api/site-assets"
    ),
    name="site_assets",
)


# Rashdyar public static assets
from fastapi.staticfiles import StaticFiles as RashdyarStaticFiles

app.mount(
    "/assets",
    RashdyarStaticFiles(
        directory="/root/aistudio-api/site_assets",
        check_dir=True,
    ),
    name="rashdyar_public_assets",
)


# Public landing page
from landing import router as landing_router
app.include_router(landing_router)

# Landing, sales plans and protected website messages management
from admin.landing import router as landing_admin_router
from admin.plans import router as plans_admin_router
from admin.contacts import router as contacts_admin_router

app.include_router(landing_admin_router)
app.include_router(plans_admin_router)
app.include_router(contacts_admin_router)


# Bazaar purchase verification
from bazaar_purchase_api import router as bazaar_purchase_router
app.include_router(bazaar_purchase_router)


# =========================================================
# Video Render API
# =========================================================
from video_render_api import router as video_render_router

os.makedirs(
    "/root/aistudio-api/generated/videos",
    exist_ok=True,
)

app.mount(
    "/generated/videos",
    StaticFiles(
        directory="/root/aistudio-api/generated/videos"
    ),
    name="generated_videos",
)

app.include_router(video_render_router)


# ===== VIDEO STUDIO LOCK START =====

import os as _video_lock_os
from fastapi.responses import JSONResponse as _VideoLockJSONResponse


def _is_video_studio_enabled() -> bool:
    return (
        _video_lock_os.getenv(
            "ENABLE_VIDEO_STUDIO",
            "false",
        )
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "on",
            "enabled",
        }
    )


@app.middleware("http")
async def _video_studio_lock_middleware(request, call_next):
    """
    جلوگیری کامل از اجرای تمام endpointهای تولید ویدئو.

    وقتی ENABLE_VIDEO_STUDIO=false باشد، درخواست قبل از
    رسیدن به OpenAI یا Sora متوقف می‌شود.
    """

    path = request.url.path.rstrip("/")

    is_video_api = (
        path == "/v1/video"
        or path.startswith("/v1/video/")
    )

    if is_video_api and not _is_video_studio_enabled():
        return _VideoLockJSONResponse(
            status_code=503,
            content={
                "success": False,
                "enabled": False,
                "coming_soon": True,
                "retryable": False,
                "code": "VIDEO_STUDIO_COMING_SOON",
                "title": "استودیو ویدئوی هوشمند",
                "message": (
                    "این قابلیت به‌زودی با موتور جدید، "
                    "سریع‌تر و مقرون‌به‌صرفه‌تر فعال می‌شود."
                ),
                "short_message": "به‌زودی",
            },
            headers={
                "Cache-Control": "no-store",
            },
        )

    return await call_next(request)


@app.get(
    "/v1/features/video-studio",
    tags=["Features"],
)
async def _video_studio_feature_status():
    enabled = _is_video_studio_enabled()

    return {
        "success": True,
        "enabled": enabled,
        "coming_soon": not enabled,
        "code": (
            "VIDEO_STUDIO_ENABLED"
            if enabled
            else "VIDEO_STUDIO_COMING_SOON"
        ),
        "title": "استودیو ویدئوی هوشمند",
        "message": (
            "قابلیت تولید ویدئو فعال است."
            if enabled
            else (
                "نسل جدید ساخت ویدئو با کیفیت بالاتر، "
                "سرعت بیشتر و هزینه کمتر به‌زودی فعال می‌شود."
            )
        ),
        "short_message": (
            "فعال"
            if enabled
            else "به‌زودی"
        ),
    }


# ===== VIDEO STUDIO LOCK END =====
# Online Trend Center
from trend_api import router as trend_router
app.include_router(trend_router)

# =========================================================
# In-app support ticket system
# =========================================================
from support_api import router as support_router
app.include_router(support_router)

from support_admin_panel import router as support_admin_panel_router
app.include_router(support_admin_panel_router)

# Support attachment images
from fastapi.staticfiles import StaticFiles as _SupportStaticFiles
import os as _support_os

_support_os.makedirs(
    "/root/aistudio-api/generated/support",
    exist_ok=True,
)

app.mount(
    "/generated/support",
    _SupportStaticFiles(
        directory="/root/aistudio-api/generated/support"
    ),
    name="generated_support",
)

# Zarinpal Payment
from zarinpal_routes import router as zarinpal_router
app.include_router(zarinpal_router)



# Admin payment gateway
from admin.payment_gateway import router as admin_payment_gateway_router
app.include_router(admin_payment_gateway_router)


# User web panel
from user_panel import router as user_panel_router
app.include_router(user_panel_router)


# Payment gateway public settings
from payment_gateway_settings import router as payment_gateway_settings_router
app.include_router(payment_gateway_settings_router)

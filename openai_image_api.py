from __future__ import annotations

import base64
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field


load_dotenv()


# =========================================================
# Environment
# =========================================================

APP_API_TOKEN = os.getenv(
    "APP_API_TOKEN",
    "",
).strip()

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    "",
).strip()

OPENAI_IMAGE_BASE_URL = os.getenv(
    "OPENAI_IMAGE_BASE_URL",
    "https://api.openai.com/v1",
).strip().rstrip("/")

OPENAI_IMAGE_MODEL = os.getenv(
    "OPENAI_IMAGE_MODEL",
    "gpt-image-2",
).strip()

PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://ap.movifilm.sbs",
).strip().rstrip("/")

GENERATED_IMAGE_DIRECTORY = Path(
    "/root/aistudio-api/generated/images"
)

GENERATED_IMAGE_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# Router
# =========================================================

router = APIRouter(
    prefix="/v1/image",
    tags=["OpenAI Image Generation"],
)


# =========================================================
# Schemas
# =========================================================

class ImageGenerateRequest(BaseModel):
    prompt: str = Field(
        min_length=3,
        max_length=20_000,
    )

    aspect_ratio: Literal[
        "1:1",
        "4:5",
        "5:4",
        "9:16",
        "16:9",
        "3:4",
        "4:3",
    ] = "1:1"

    quality: Literal[
        "low",
        "medium",
        "high",
    ] = "medium"

    style: Literal[
        "واقع‌گرایانه",
        "تبلیغاتی",
        "مینیمال",
        "سه‌بعدی",
        "تصویرسازی",
        "سینمایی",
        "محصول",
        "شبکه‌های اجتماعی",
    ] = "تبلیغاتی"

    background: Literal[
        "auto",
        "opaque",
        "transparent",
    ] = "auto"

    negative_prompt: str = Field(
        default="",
        max_length=2_000,
    )


class ImageGenerateResponse(BaseModel):
    success: bool
    image_url: str | None = None
    filename: str | None = None
    model: str
    size: str
    aspect_ratio: str
    quality: str
    output_format: str
    source: str
    message: str | None = None


# =========================================================
# Helpers
# =========================================================

def verify_app_token(
    authorization: str | None,
) -> None:
    if not APP_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail=(
                "APP_API_TOKEN روی سرور "
                "تنظیم نشده است."
            ),
        )

    expected = f"Bearer {APP_API_TOKEN}"

    if authorization != expected:
        raise HTTPException(
            status_code=401,
            detail="توکن برنامه معتبر نیست.",
        )


def resolve_image_size(
    aspect_ratio: str,
) -> str:
    """
    ابعاد همگی مضرب 16 هستند و برای
    gpt-image-2 معتبرند.
    """

    sizes = {
        "1:1": "1024x1024",
        "4:5": "1024x1280",
        "5:4": "1280x1024",
        "9:16": "1024x1824",
        "16:9": "1824x1024",
        "3:4": "768x1024",
        "4:3": "1024x768",
    }

    return sizes.get(
        aspect_ratio,
        "1024x1024",
    )


def build_professional_prompt(
    request: ImageGenerateRequest,
) -> str:
    aspect_guide = {
        "1:1": (
            "تصویر مربعی مناسب پست اینستاگرام"
        ),
        "4:5": (
            "تصویر عمودی مناسب پست فید اینستاگرام"
        ),
        "5:4": (
            "تصویر افقی نزدیک به مربع"
        ),
        "9:16": (
            "تصویر عمودی تمام‌صفحه مناسب "
            "استوری و کاور ریلز"
        ),
        "16:9": (
            "تصویر افقی مناسب کاور ویدئو"
        ),
        "3:4": (
            "تصویر پرتره عمودی"
        ),
        "4:3": (
            "تصویر افقی کلاسیک"
        ),
    }.get(
        request.aspect_ratio,
        "تصویر مناسب شبکه‌های اجتماعی",
    )

    prompt = f"""
یک تصویر حرفه‌ای، جذاب و آماده استفاده تجاری تولید کن.

شرح تصویر:
{request.prompt.strip()}

سبک بصری:
{request.style}

قالب خروجی:
{aspect_guide}

الزامات طراحی:
- ترکیب‌بندی حرفه‌ای و متعادل
- سوژه اصلی کاملاً واضح باشد
- نورپردازی دقیق و باکیفیت
- جزئیات تمیز و طبیعی
- مناسب انتشار در شبکه‌های اجتماعی
- فضای امن کافی نزدیک لبه‌های تصویر
- بدون واترمارک
- بدون لوگوی تصادفی
- بدون نوشته‌های ناخوانا
- بدون اشیای ناقص یا تکراری
- کیفیت در سطح تبلیغات حرفه‌ای
""".strip()

    negative_prompt = (
        request.negative_prompt.strip()
    )

    if negative_prompt:
        prompt += (
            "\n\nمواردی که نباید در تصویر باشند:\n"
            f"{negative_prompt}"
        )

    return prompt


def image_extension(
    output_format: str,
) -> str:
    if output_format == "jpeg":
        return "jpg"

    return output_format


async def request_openai_image(
    request: ImageGenerateRequest,
) -> tuple[bytes, str, str]:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY روی سرور تنظیم نشده است."
        )

    size = resolve_image_size(
        request.aspect_ratio
    )

    output_format = (
        "png"
        if request.background == "transparent"
        else "webp"
    )

    payload: dict[str, object] = {
        "model": OPENAI_IMAGE_MODEL,
        "prompt": build_professional_prompt(
            request
        ),
        "n": 1,
        "size": size,
        "quality": request.quality,
        "background": request.background,
        "output_format": output_format,
        "moderation": "auto",
    }

    if output_format == "webp":
        payload["output_compression"] = 90

    timeout = httpx.Timeout(
        connect=30.0,
        read=300.0,
        write=60.0,
        pool=30.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout
    ) as client:
        response = await client.post(
            (
                f"{OPENAI_IMAGE_BASE_URL}"
                "/images/generations"
            ),
            headers={
                "Authorization": (
                    f"Bearer {OPENAI_API_KEY}"
                ),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
        )

    response_text = response.text

    if response.status_code not in range(
        200,
        300,
    ):
        try:
            error_data = response.json()

            error_value = error_data.get(
                "error",
                {},
            )

            if isinstance(error_value, dict):
                error_message = (
                    error_value.get("message")
                    or response_text
                )
            else:
                error_message = response_text

        except Exception:
            error_message = response_text

        raise RuntimeError(
            (
                f"OpenAI HTTP "
                f"{response.status_code}: "
                f"{error_message}"
            )
        )

    try:
        response_data = response.json()
    except Exception as error:
        raise RuntimeError(
            "پاسخ OpenAI ساختار JSON معتبری ندارد."
        ) from error

    images = response_data.get(
        "data",
        [],
    )

    if (
        not isinstance(images, list)
        or not images
    ):
        raise RuntimeError(
            "OpenAI هیچ تصویری برنگرداند."
        )

    first_image = images[0]

    if not isinstance(first_image, dict):
        raise RuntimeError(
            "ساختار تصویر دریافتی معتبر نیست."
        )

    image_base64 = first_image.get(
        "b64_json"
    )

    if not isinstance(
        image_base64,
        str,
    ) or not image_base64:
        raise RuntimeError(
            "داده Base64 تصویر دریافت نشد."
        )

    try:
        image_bytes = base64.b64decode(
            image_base64,
            validate=True,
        )
    except Exception as error:
        raise RuntimeError(
            "داده تصویر قابل تبدیل نیست."
        ) from error

    if len(image_bytes) < 1_000:
        raise RuntimeError(
            "حجم تصویر دریافتی معتبر نیست."
        )

    return (
        image_bytes,
        output_format,
        size,
    )


def save_generated_image(
    image_bytes: bytes,
    output_format: str,
) -> tuple[str, Path]:
    now = datetime.now(
        timezone.utc
    )

    timestamp = now.strftime(
        "%Y%m%d-%H%M%S"
    )

    random_value = secrets.token_hex(6)

    extension = image_extension(
        output_format
    )

    filename = (
        f"ai-{timestamp}-"
        f"{random_value}.{extension}"
    )

    target = (
        GENERATED_IMAGE_DIRECTORY
        / filename
    )

    temporary = target.with_suffix(
        f".{extension}.tmp"
    )

    temporary.write_bytes(
        image_bytes
    )

    temporary.replace(
        target
    )

    return filename, target


# =========================================================
# Endpoint
# =========================================================

@router.post(
    "/generate",
    response_model=ImageGenerateResponse,
)
async def generate_openai_image(
    request: ImageGenerateRequest,
    authorization: str | None = Header(
        default=None
    ),
) -> ImageGenerateResponse:
    verify_app_token(
        authorization
    )

    size = resolve_image_size(
        request.aspect_ratio
    )

    try:
        (
            image_bytes,
            output_format,
            resolved_size,
        ) = await request_openai_image(
            request
        )

        filename, _ = save_generated_image(
            image_bytes=image_bytes,
            output_format=output_format,
        )

        image_url = (
            f"{PUBLIC_BASE_URL}"
            f"/generated/images/"
            f"{filename}"
        )

        return ImageGenerateResponse(
            success=True,
            image_url=image_url,
            filename=filename,
            model=OPENAI_IMAGE_MODEL,
            size=resolved_size,
            aspect_ratio=(
                request.aspect_ratio
            ),
            quality=request.quality,
            output_format=output_format,
            source="openai_gpt_image",
            message=None,
        )

    except Exception as error:
        print(
            "OPENAI IMAGE ERROR:",
            repr(error),
            flush=True,
        )

        return ImageGenerateResponse(
            success=False,
            image_url=None,
            filename=None,
            model=OPENAI_IMAGE_MODEL,
            size=size,
            aspect_ratio=(
                request.aspect_ratio
            ),
            quality=request.quality,
            output_format=(
                "png"
                if request.background
                == "transparent"
                else "webp"
            ),
            source="error",
            message=(
                str(error)
                or "تولید تصویر انجام نشد."
            ),
        )

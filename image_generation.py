from __future__ import annotations

import asyncio
import base64
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException
from google import genai
from pydantic import BaseModel, Field


load_dotenv()

APP_API_TOKEN = os.getenv(
    "APP_API_TOKEN",
    "",
).strip()

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    "",
).strip()

GEMINI_IMAGE_MODEL = os.getenv(
    "GEMINI_IMAGE_MODEL",
    "gemini-3.1-flash-image",
).strip()

PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://ap.movifilm.sbs",
).strip().rstrip("/")

GENERATED_DIRECTORY = Path(
    "/root/aistudio-api/generated"
)

GENERATED_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


router = APIRouter(
    prefix="/v1/image",
    tags=["AI Image Generation"],
)


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(
        min_length=3,
        max_length=5000,
    )

    aspect_ratio: Literal[
        "1:1",
        "3:2",
        "2:3",
        "3:4",
        "4:3",
        "4:5",
        "5:4",
        "9:16",
        "16:9",
        "21:9",
    ] = "1:1"

    image_size: Literal[
        "1K",
        "2K",
        "4K",
    ] = "1K"

    style: Literal[
        "واقع‌گرایانه",
        "تبلیغاتی",
        "مینیمال",
        "سه‌بعدی",
        "تصویرسازی",
        "سینمایی",
        "محصول",
    ] = "تبلیغاتی"

    negative_prompt: str = Field(
        default="",
        max_length=1500,
    )


class ImageGenerateResponse(BaseModel):
    success: bool
    image_url: str | None = None
    filename: str | None = None
    model: str
    aspect_ratio: str
    image_size: str
    source: str
    message: str | None = None


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


def clean_filename_part(
    value: str,
) -> str:
    clean = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "-",
        value,
    ).strip("-")

    return clean[:40] or "image"


def build_prompt(
    request: ImageGenerateRequest,
) -> str:
    format_guide = {
        "1:1": (
            "تصویر مربعی مناسب پست اینستاگرام"
        ),
        "4:5": (
            "تصویر عمودی مناسب پست اینستاگرام"
        ),
        "9:16": (
            "تصویر عمودی تمام‌صفحه مناسب "
            "استوری یا کاور ریلز"
        ),
        "16:9": (
            "تصویر افقی مناسب کاور ویدئو"
        ),
    }.get(
        request.aspect_ratio,
        (
            f"تصویر با نسبت "
            f"{request.aspect_ratio}"
        ),
    )

    prompt = f"""
یک تصویر حرفه‌ای و آماده استفاده برای شبکه‌های اجتماعی بساز.

موضوع:
{request.prompt.strip()}

سبک بصری:
{request.style}

قالب:
{format_guide}

الزامات:
- ترکیب‌بندی تمیز و حرفه‌ای
- نورپردازی و جزئیات باکیفیت
- مناسب استفاده تجاری
- بدون واترمارک
- بدون لوگوی تصادفی
- بدون متن ناخوانا
- سوژه اصلی واضح باشد
- فضای امن کافی نزدیک لبه‌ها رعایت شود
""".strip()

    if request.negative_prompt.strip():
        prompt += (
            "\n\nمواردی که نباید در تصویر باشند:\n"
            + request.negative_prompt.strip()
        )

    return prompt


def generate_image_sync(
    request: ImageGenerateRequest,
) -> tuple[bytes, str]:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY روی سرور تنظیم نشده است."
        )

    client = genai.Client(
        api_key=GEMINI_API_KEY,
    )

    interaction = client.interactions.create(
        model=GEMINI_IMAGE_MODEL,
        input=build_prompt(request),
        response_format={
            "type": "image",
            "mime_type": "image/jpeg",
            "aspect_ratio": request.aspect_ratio,
            "image_size": request.image_size,
        },
    )

    output_image = getattr(
        interaction,
        "output_image",
        None,
    )

    if output_image is None:
        raise RuntimeError(
            "مدل تصویر معتبری برنگرداند."
        )

    image_data = getattr(
        output_image,
        "data",
        None,
    )

    if not image_data:
        raise RuntimeError(
            "داده تصویر دریافتی خالی است."
        )

    if isinstance(image_data, bytes):
        image_bytes = image_data
    else:
        image_bytes = base64.b64decode(
            image_data
        )

    if len(image_bytes) < 1000:
        raise RuntimeError(
            "حجم تصویر دریافتی معتبر نیست."
        )

    return image_bytes, "image/jpeg"


@router.post(
    "/generate",
    response_model=ImageGenerateResponse,
)
async def generate_image(
    request: ImageGenerateRequest,
    authorization: str | None = Header(
        default=None
    ),
) -> ImageGenerateResponse:
    verify_app_token(authorization)

    try:
        image_bytes, mime_type = (
            await asyncio.to_thread(
                generate_image_sync,
                request,
            )
        )

        extension = (
            "png"
            if mime_type == "image/png"
            else "jpg"
        )

        now = datetime.now(
            timezone.utc
        )

        date_part = now.strftime(
            "%Y%m%d-%H%M%S"
        )

        style_part = clean_filename_part(
            request.style
        )

        random_part = secrets.token_hex(5)

        filename = (
            f"{date_part}-"
            f"{style_part}-"
            f"{random_part}."
            f"{extension}"
        )

        target = (
            GENERATED_DIRECTORY
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

        image_url = (
            f"{PUBLIC_BASE_URL}"
            f"/generated/{filename}"
        )

        return ImageGenerateResponse(
            success=True,
            image_url=image_url,
            filename=filename,
            model=GEMINI_IMAGE_MODEL,
            aspect_ratio=request.aspect_ratio,
            image_size=request.image_size,
            source="gemini_image",
            message=None,
        )

    except HTTPException:
        raise

    except Exception as error:
        print(
            "GEMINI IMAGE ERROR:",
            repr(error),
            flush=True,
        )

        return ImageGenerateResponse(
            success=False,
            image_url=None,
            filename=None,
            model=GEMINI_IMAGE_MODEL,
            aspect_ratio=request.aspect_ratio,
            image_size=request.image_size,
            source="error",
            message=(
                str(error)
                or "تولید تصویر انجام نشد."
            ),
        )

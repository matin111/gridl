import base64
import os
import re
import secrets
import traceback
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel


router = APIRouter(
    prefix="/v1/images",
    tags=["AI Image Edit"],
)


APP_API_TOKEN = os.getenv(
    "APP_API_TOKEN",
    "",
).strip()

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    "",
).strip()

OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL",
    "https://api.openai.com/v1",
).rstrip("/")

OPENAI_IMAGE_EDIT_MODEL = os.getenv(
    "OPENAI_IMAGE_EDIT_MODEL",
    "gpt-image-2",
).strip()

PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://ap.movifilm.sbs",
).rstrip("/")

OUTPUT_DIRECTORY = Path(
    "/root/aistudio-api/generated/image-edits"
)

MAX_IMAGE_BYTES = 20 * 1024 * 1024

ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}

ALLOWED_QUALITIES = {
    "low",
    "medium",
    "high",
    "auto",
}

ALLOWED_SIZES = {
    "1024x1024",
    "1024x1536",
    "1536x1024",
    "auto",
}

ALLOWED_OUTPUT_FORMATS = {
    "png",
    "webp",
    "jpeg",
}

ALLOWED_BACKGROUNDS = {
    "auto",
    "opaque",
    "transparent",
}


EDIT_PRESETS = {
    "custom": "",

    "remove_background": (
        "پس‌زمینه تصویر را کاملاً حذف کن و سوژه اصلی را با لبه‌های "
        "طبیعی، دقیق و تمیز حفظ کن. جزئیات چهره، مو، لباس و محصول "
        "نباید تغییر کند."
    ),

    "enhance_quality": (
        "کیفیت این تصویر را به شکل طبیعی افزایش بده. وضوح، جزئیات، "
        "نور، کنتراست و رنگ‌ها را اصلاح کن، نویز و تاری را کاهش بده، "
        "اما هویت افراد و شکل واقعی اجسام را تغییر نده."
    ),

    "remove_object": (
        "شیء ناخواسته‌ای که در دستور کاربر مشخص شده را حذف کن و فضای "
        "خالی را کاملاً طبیعی و هماهنگ با محیط بازسازی کن."
    ),

    "change_clothes": (
        "فقط لباس فرد را مطابق دستور کاربر تغییر بده. چهره، مدل مو، "
        "حالت بدن، فرم بدن، دست‌ها و پس‌زمینه بدون تغییر باقی بمانند."
    ),

    "poster": (
        "این تصویر را به یک پوستر تبلیغاتی حرفه‌ای و مدرن تبدیل کن. "
        "سوژه اصلی را حفظ کن، ترکیب‌بندی حرفه‌ای، نورپردازی استودیویی "
        "و فضای خالی مناسب برای افزودن متن ایجاد کن. داخل تصویر نوشته "
        "ناخوانا یا متن تصادفی نساز."
    ),

    "product_photo": (
        "تصویر را به عکس حرفه‌ای محصول با نورپردازی استودیویی، "
        "پس‌زمینه تمیز، سایه طبیعی و جزئیات واقعی تبدیل کن. فرم و "
        "ویژگی‌های اصلی محصول تغییر نکند."
    ),

    "portrait": (
        "این تصویر را به یک پرتره حرفه‌ای با نورپردازی استودیویی، "
        "رنگ پوست طبیعی و جزئیات واقعی تبدیل کن. هویت، چهره و حالت "
        "فرد کاملاً حفظ شود."
    ),

    "social_media": (
        "تصویر را برای انتشار در شبکه‌های اجتماعی حرفه‌ای و چشم‌گیر "
        "کن. نور، رنگ و ترکیب‌بندی را بهبود بده، اما سوژه اصلی و "
        "هویت افراد تغییر نکند."
    ),
}


class ImageEditResponse(BaseModel):
    success: bool
    image_url: str | None = None
    filename: str | None = None
    model: str | None = None
    size: str | None = None
    quality: str | None = None
    output_format: str | None = None
    preset: str | None = None
    message: str | None = None


def verify_app_token(
    authorization: str | None,
) -> None:
    if not APP_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="APP_API_TOKEN روی سرور تنظیم نشده است.",
        )

    expected_token = f"Bearer {APP_API_TOKEN}"

    if authorization != expected_token:
        raise HTTPException(
            status_code=401,
            detail="دسترسی غیرمجاز",
        )


def safe_extension(
    output_format: str,
) -> str:
    if output_format == "jpeg":
        return "jpg"

    return output_format


def sanitize_filename(
    filename: str | None,
) -> str:
    original = filename or "input-image"
    stem = Path(original).stem

    clean_stem = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "-",
        stem,
    ).strip("-")

    return clean_stem[:50] or "input-image"


def build_edit_prompt(
    prompt: str,
    preset: str,
) -> str:
    clean_prompt = prompt.strip()
    preset_prompt = EDIT_PRESETS.get(
        preset,
        "",
    ).strip()

    common_rules = """
قوانین مهم ویرایش:
- تصویر ورودی مرجع اصلی است.
- بخش‌هایی که کاربر درخواست تغییرشان را نداده است حفظ شوند.
- چهره، هویت، حالت بدن، دست‌ها و آناتومی طبیعی باقی بمانند.
- از ایجاد نوشته تصادفی، واترمارک، لوگوی نامرتبط و اشیای تکراری خودداری کن.
- خروجی باید واقعی، تمیز، حرفه‌ای و باکیفیت باشد.
""".strip()

    parts = [
        part
        for part in [
            preset_prompt,
            clean_prompt,
            common_rules,
        ]
        if part
    ]

    return "\n\n".join(parts)


async def read_upload(
    upload: UploadFile,
    field_name: str,
) -> tuple[bytes, str, str]:
    filename = upload.filename or "image.png"

    extension = Path(filename).suffix.lower()

    mime_from_extension = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(extension)

    received_content_type = (
        upload.content_type
        or ""
    ).lower().strip()

    if received_content_type in ALLOWED_IMAGE_TYPES:
        content_type = received_content_type
    elif mime_from_extension is not None:
        content_type = mime_from_extension
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                f"فرمت {field_name} پشتیبانی نمی‌شود. "
                "فقط PNG، JPG و WEBP مجاز است."
            ),
        )

    content = await upload.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail=f"فایل {field_name} خالی است.",
        )

    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"حجم {field_name} بیشتر از ۲۰ مگابایت است."
            ),
        )

    return content, filename, content_type


@router.post(
    "/edit",
    response_model=ImageEditResponse,
)
async def edit_image(
    authorization: str | None = Header(default=None),

    image: UploadFile = File(...),

    prompt: str = Form(default=""),

    preset: Literal[
        "custom",
        "remove_background",
        "enhance_quality",
        "remove_object",
        "change_clothes",
        "poster",
        "product_photo",
        "portrait",
        "social_media",
    ] = Form(default="custom"),

    size: Literal[
        "1024x1024",
        "1024x1536",
        "1536x1024",
        "auto",
    ] = Form(default="auto"),

    quality: Literal[
        "low",
        "medium",
        "high",
        "auto",
    ] = Form(default="medium"),

    output_format: Literal[
        "png",
        "webp",
        "jpeg",
    ] = Form(default="webp"),

    background: Literal[
        "auto",
        "opaque",
        "transparent",
    ] = Form(default="auto"),

    mask: UploadFile | None = File(default=None),
) -> ImageEditResponse:
    verify_app_token(authorization)

    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY روی سرور تنظیم نشده است.",
        )

    if preset == "custom" and not prompt.strip():
        raise HTTPException(
            status_code=400,
            detail="دستور ویرایش تصویر را وارد کنید.",
        )

    image_content, image_name, image_type = (
        await read_upload(
            image,
            "تصویر",
        )
    )

    mask_data: tuple[bytes, str, str] | None = None

    if mask is not None:
        mask_data = await read_upload(
            mask,
            "ماسک",
        )

    final_prompt = build_edit_prompt(
        prompt=prompt,
        preset=preset,
    )

    request_data = {
        "model": OPENAI_IMAGE_EDIT_MODEL,
        "prompt": final_prompt,
        "size": size,
        "quality": quality,
        "output_format": output_format,
        "background": background,
    }

    files: list[
        tuple[str, tuple[str, bytes, str]]
    ] = [
        (
            "image[]",
            (
                image_name,
                image_content,
                image_type,
            ),
        ),
    ]

    if mask_data is not None:
        mask_content, mask_name, mask_type = mask_data

        files.append(
            (
                "mask",
                (
                    mask_name,
                    mask_content,
                    mask_type,
                ),
            )
        )

    timeout = httpx.Timeout(
        connect=30.0,
        read=300.0,
        write=120.0,
        pool=30.0,
    )

    try:
        async with httpx.AsyncClient(
            timeout=timeout
        ) as client:
            response = await client.post(
                f"{OPENAI_BASE_URL}/images/edits",
                headers={
                    "Authorization":
                        f"Bearer {OPENAI_API_KEY}",
                    "Accept": "application/json",
                },
                data=request_data,
                files=files,
            )

        if response.status_code >= 400:
            detail = response.text[:2000]

            try:
                error_payload = response.json()
                error_object = error_payload.get(
                    "error",
                    {},
                )

                if isinstance(error_object, dict):
                    error_message = error_object.get(
                        "message"
                    )

                    if error_message:
                        detail = str(error_message)

            except ValueError:
                pass

            raise RuntimeError(
                f"OpenAI Image Edit error "
                f"{response.status_code}: {detail}"
            )

        response_payload = response.json()
        response_images = response_payload.get(
            "data",
            [],
        )

        if (
            not isinstance(response_images, list)
            or not response_images
            or not isinstance(response_images[0], dict)
        ):
            raise RuntimeError(
                "پاسخ معتبری از سرویس ویرایش تصویر دریافت نشد."
            )

        image_base64 = response_images[0].get(
            "b64_json"
        )

        if not isinstance(
            image_base64,
            str,
        ) or not image_base64.strip():
            raise RuntimeError(
                "داده تصویر ویرایش‌شده در پاسخ وجود ندارد."
            )

        try:
            edited_image_bytes = base64.b64decode(
                image_base64,
                validate=True,
            )

        except Exception as decode_error:
            raise RuntimeError(
                "تصویر خروجی قابل پردازش نیست."
            ) from decode_error

        if not edited_image_bytes:
            raise RuntimeError(
                "تصویر خروجی خالی است."
            )

        OUTPUT_DIRECTORY.mkdir(
            parents=True,
            exist_ok=True,
        )

        extension = safe_extension(
            output_format
        )

        safe_input_name = sanitize_filename(
            image_name
        )

        filename = (
            f"edit-{safe_input_name}-"
            f"{secrets.token_hex(8)}."
            f"{extension}"
        )

        output_path = (
            OUTPUT_DIRECTORY
            / filename
        )

        output_path.write_bytes(
            edited_image_bytes
        )

        image_url = (
            f"{PUBLIC_BASE_URL}"
            f"/generated/image-edits/"
            f"{filename}"
        )

        return ImageEditResponse(
            success=True,
            image_url=image_url,
            filename=filename,
            model=OPENAI_IMAGE_EDIT_MODEL,
            size=size,
            quality=quality,
            output_format=output_format,
            preset=preset,
            message="تصویر با موفقیت ویرایش شد.",
        )

    except HTTPException:
        raise

    except Exception as error:
        print(
            "OPENAI IMAGE EDIT ERROR:",
            repr(error),
            flush=True,
        )

        traceback.print_exc()

        return ImageEditResponse(
            success=False,
            image_url=None,
            filename=None,
            model=OPENAI_IMAGE_EDIT_MODEL,
            size=size,
            quality=quality,
            output_format=output_format,
            preset=preset,
            message=str(error),
        )


@router.get("/edit/presets")
async def image_edit_presets(
    authorization: str | None = Header(default=None),
) -> dict:
    verify_app_token(authorization)

    return {
        "success": True,
        "presets": [
            {
                "key": "custom",
                "title": "ویرایش دلخواه",
                "description": "ویرایش تصویر با دستور اختصاصی",
            },
            {
                "key": "remove_background",
                "title": "حذف پس‌زمینه",
                "description": "حذف دقیق پس‌زمینه و حفظ سوژه",
            },
            {
                "key": "enhance_quality",
                "title": "افزایش کیفیت",
                "description": "افزایش وضوح، نور و جزئیات تصویر",
            },
            {
                "key": "remove_object",
                "title": "حذف اشیا",
                "description": "حذف شیء ناخواسته از تصویر",
            },
            {
                "key": "change_clothes",
                "title": "تغییر لباس",
                "description": "تغییر لباس با حفظ چهره و حالت بدن",
            },
            {
                "key": "poster",
                "title": "تبدیل به پوستر",
                "description": "ساخت پوستر حرفه‌ای از تصویر",
            },
            {
                "key": "product_photo",
                "title": "عکس محصول",
                "description": "تبدیل به عکس استودیویی محصول",
            },
            {
                "key": "portrait",
                "title": "پرتره حرفه‌ای",
                "description": "نور و کیفیت پرتره استودیویی",
            },
            {
                "key": "social_media",
                "title": "مناسب شبکه اجتماعی",
                "description": "بهینه‌سازی تصویر برای انتشار",
            },
        ],
    }

import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(tags=["Video and Audio"])

BASE_DIR = Path("/root/aistudio-api")
GENERATED_DIR = BASE_DIR / "generated"
VIDEO_DIR = GENERATED_DIR / "videos"
AUDIO_DIR = GENERATED_DIR / "audio"

VIDEO_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL",
    "https://api.openai.com/v1"
).rstrip("/")

APP_API_TOKEN = os.getenv("APP_API_TOKEN", "").strip()

OPENAI_PROMPT_MODEL = os.getenv(
    "OPENAI_PROMPT_MODEL",
    os.getenv("OPENAI_TEXT_MODEL", "gpt-4.1-mini")
).strip()

PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://ap.movifilm.sbs"
).rstrip("/")


def check_authorization(authorization: Optional[str]) -> None:
    if not APP_API_TOKEN:
        return

    expected = f"Bearer {APP_API_TOKEN}"

    if authorization != expected:
        raise HTTPException(
            status_code=401,
            detail="توکن دسترسی نامعتبر است."
        )


def check_openai_key() -> None:
    if not OPENAI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY روی سرور تنظیم نشده است."
        )


def openai_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }


def extract_openai_error(response: httpx.Response) -> str:
    try:
        body = response.json()

        if isinstance(body, dict):
            error = body.get("error")

            if isinstance(error, dict):
                message = error.get("message")

                if message:
                    return str(message)

            detail = body.get("detail")

            if detail:
                return str(detail)

        return str(body)

    except Exception:
        text = response.text.strip()
        return text[:1000] if text else "خطای نامشخص OpenAI"


class AudioSpeechRequest(BaseModel):
    input: str = Field(min_length=1, max_length=4096)
    voice: str = "shimmer"
    model: str = "gpt-4o-mini-tts"
    response_format: str = "mp3"
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    instructions: Optional[str] = (
        "با لحن طبیعی، روان، گرم و مناسب محتوای فارسی صحبت کن. "
        "تلفظ کلمات فارسی واضح باشد."
    )


class AudioSpeechResponse(BaseModel):
    success: bool
    audio_url: Optional[str] = None
    url: Optional[str] = None
    filename: Optional[str] = None
    duration_seconds: Optional[float] = None
    model: Optional[str] = None
    voice: Optional[str] = None
    error: Optional[str] = None


class VideoGenerateRequest(BaseModel):
    prompt: str = Field(min_length=5, max_length=12000)
    model: str = "sora-2"
    seconds: str = "8"
    size: str = "720x1280"
    title: Optional[str] = None

    # ارتقای خودکار پرامپت قبل از ساخت ویدیو
    auto_enhance: bool = True

    # این مقادیر فعلاً اختیاری‌اند و اندروید لازم نیست ارسالشان کند.
    style: str = "cinematic photorealistic"
    camera_motion: str = "smooth natural camera movement"
    realism: str = "high"
    target_platform: str = "Instagram Reels"
    language: str = "fa"


class VideoGenerateResponse(BaseModel):
    success: bool
    original_prompt: Optional[str] = None
    enhanced_prompt: Optional[str] = None
    video_url: Optional[str] = None
    url: Optional[str] = None
    output_url: Optional[str] = None
    filename: Optional[str] = None
    video_id: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = None
    duration_seconds: Optional[float] = None
    model: Optional[str] = None
    size: Optional[str] = None
    error: Optional[str] = None


class VideoPromptEnhanceRequest(BaseModel):
    prompt: str = Field(min_length=5, max_length=12000)
    seconds: str = "8"
    size: str = "720x1280"
    style: str = "cinematic photorealistic"
    camera_motion: str = "smooth natural camera movement"
    realism: str = "high"
    target_platform: str = "Instagram Reels"


class VideoPromptEnhanceResponse(BaseModel):
    success: bool
    original_prompt: str
    enhanced_prompt: str
    model: str


class VideoStatusResponse(BaseModel):
    success: bool
    video_id: str
    status: str
    progress: int = 0
    video_url: Optional[str] = None
    error: Optional[str] = None


ALLOWED_VOICES = {
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "onyx",
    "nova",
    "sage",
    "shimmer",
    "verse",
    "marin",
    "cedar",
}

ALLOWED_AUDIO_FORMATS = {
    "mp3",
    "opus",
    "aac",
    "flac",
    "wav",
    "pcm",
}

ALLOWED_VIDEO_MODELS = {
    "sora-2",
    "sora-2-pro",
}

ALLOWED_VIDEO_SECONDS = {
    "4",
    "8",
    "12",
}

ALLOWED_VIDEO_SIZES = {
    "720x1280",
    "1280x720",
    "1024x1792",
    "1792x1024",
}


@router.get("/v1/media/health")
async def media_health(
    authorization: Optional[str] = Header(default=None)
):
    check_authorization(authorization)

    return {
        "success": True,
        "openai_key_configured": bool(OPENAI_API_KEY),
        "audio_endpoint": "/v1/audio/speech",
        "video_endpoint": "/v1/video/generate",
        "video_status_endpoint": "/v1/video/status/{video_id}",
        "video_models": sorted(ALLOWED_VIDEO_MODELS),
        "audio_model": "gpt-4o-mini-tts",
    }


@router.post(
    "/v1/audio/speech",
    response_model=AudioSpeechResponse
)
async def generate_speech(
    request: AudioSpeechRequest,
    authorization: Optional[str] = Header(default=None)
):
    check_authorization(authorization)
    check_openai_key()

    voice = request.voice.strip().lower()
    audio_format = request.response_format.strip().lower()

    if voice not in ALLOWED_VOICES:
        raise HTTPException(
            status_code=400,
            detail=f"صدای {voice} پشتیبانی نمی‌شود."
        )

    if audio_format not in ALLOWED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"فرمت {audio_format} پشتیبانی نمی‌شود."
        )

    payload = {
        "model": request.model,
        "input": request.input.strip(),
        "voice": voice,
        "response_format": audio_format,
        "speed": request.speed,
    }

    if request.instructions and request.model.startswith("gpt-4o"):
        payload["instructions"] = request.instructions.strip()

    timeout = httpx.Timeout(
        connect=30.0,
        read=300.0,
        write=60.0,
        pool=30.0
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{OPENAI_BASE_URL}/audio/speech",
            headers={
                **openai_headers(),
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        message = extract_openai_error(response)

        raise HTTPException(
            status_code=response.status_code,
            detail=f"خطای تولید صدا: {message}"
        )

    filename = (
        f"voice-{time.strftime('%Y%m%d-%H%M%S')}-"
        f"{uuid.uuid4().hex[:8]}.{audio_format}"
    )

    output_path = AUDIO_DIR / filename
    output_path.write_bytes(response.content)

    audio_url = f"{PUBLIC_BASE_URL}/generated/audio/{filename}"

    return AudioSpeechResponse(
        success=True,
        audio_url=audio_url,
        url=audio_url,
        filename=filename,
        model=request.model,
        voice=voice,
    )


def extract_responses_text(data: dict) -> str:
    """
    متن نهایی Responses API را از ساختار پاسخ استخراج می‌کند.
    """

    direct_text = data.get("output_text")

    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    output = data.get("output")

    if not isinstance(output, list):
        return ""

    collected: list[str] = []

    for item in output:
        if not isinstance(item, dict):
            continue

        content = item.get("content")

        if not isinstance(content, list):
            continue

        for part in content:
            if not isinstance(part, dict):
                continue

            text_value = part.get("text")

            if isinstance(text_value, str) and text_value.strip():
                collected.append(text_value.strip())

    return "\n".join(collected).strip()


async def enhance_video_prompt(
    original_prompt: str,
    seconds: str,
    size: str,
    style: str,
    camera_motion: str,
    realism: str,
    target_platform: str,
) -> str:
    """
    ایده ساده کاربر را به پرامپت اجرایی و حرفه‌ای مخصوص ویدیو تبدیل می‌کند.
    """

    system_instruction = """
You are the professional AI video prompt director for AIStudioPro.

Your task is to transform a short user idea into one production-ready prompt
for a photorealistic AI video generator.

Return ONLY the final English video prompt.
Do not add headings, explanations, JSON, markdown or quotation marks.

CORE RULES:

1. Preserve the user's original idea, subject, product, action and intent.

2. Create one visually coherent scene that can realistically happen within
the requested duration. Do not overload a short clip with too many actions.

3. Describe:
- subject appearance
- exact environment
- exact physical action
- shot composition
- camera movement
- lens and depth of field
- lighting
- material and surface details
- realistic motion
- beginning, middle and final frame
- visual continuity

4. For people:
- preserve natural human anatomy
- exactly two arms and two hands when visible
- five fingers on each visible hand
- anatomically correct joints
- natural facial expressions
- stable identity throughout the shot
- realistic body balance and weight transfer
- no duplicated or fused limbs

5. For clothing and fashion:
- use realistic cloth physics
- preserve garment shape, color and material
- maintain correct sleeve, collar and shoulder alignment
- fabric must respond naturally to gravity and body movement
- hands must interact with clothing in physically plausible ways
- keep hands visible whenever possible
- no floating garments
- no fabric merging with skin
- no sudden garment transformation
- no arms passing through fabric
- no impossible dressing motion
- no simultaneous entry of both arms into sleeves

IMPORTANT CLOTHING ACTION RULE:

If the user asks a person to put on, wear, remove, change or try on clothing,
do not depict the dressing or undressing action at all.

The first frame must already show the person wearing the garment completely,
correctly and naturally.

Never begin with:
- the garment in the person's hands
- the garment being lifted
- an arm entering a sleeve
- fabric passing over the head
- clothing moving toward the body
- clothing covering the camera
- a dressing transition
- a before-and-after wardrobe change

Rewrite the scene so the person starts fully dressed in the requested garment.

Only show safe finishing actions such as:
- gently straightening the collar
- adjusting one cuff
- smoothing the front of the garment
- lightly touching one lapel
- fastening or checking one visible button
- checking the fit in a mirror
- turning slightly to view the side profile
- taking one slow natural step

Keep both hands visible and separated whenever possible.

The garment must already have:
- correct sleeve placement
- correct shoulder alignment
- correct collar placement
- stable color and material
- realistic folds and fabric tension
- no clipping into the body
- no fabric fused to hands or skin

The opening shot must immediately communicate that the person is already
wearing the garment confidently and correctly.

Preserve the user's intended result, but replace the literal dressing action
with final styling and mirror inspection.

Prioritize physical realism and visual quality over literal execution.

6. For products:
- preserve exact product shape and material
- keep branding stable unless the user requests no branding
- avoid shape changes, melting or duplication

7. Use realistic cinematic language, but do not fill the prompt with empty
marketing words.

8. The video must have:
- temporal consistency
- subject consistency
- environment consistency
- realistic physics
- smooth motion
- no jump cuts unless explicitly requested
- no slideshow
- no still-image montage

9. Include constraints naturally at the end:
no text overlays, no subtitles, no watermark, no logo added by the model,
no flickering, no warped anatomy, no extra fingers, no duplicated limbs,
no object morphing, no floating objects, no sudden scene changes.

10. Never use celebrity names, living artist style imitation or copyrighted
characters.

11. The final prompt should normally be 180 to 350 English words.
"""

    user_instruction = f"""
USER IDEA:
{original_prompt.strip()}

VIDEO SETTINGS:
Duration: {seconds} seconds
Resolution: {size}
Visual style: {style}
Camera motion: {camera_motion}
Realism: {realism}
Target platform: {target_platform}

Create the strongest production-ready prompt for this exact video.
"""

    payload = {
        "model": OPENAI_PROMPT_MODEL,
        "input": [
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": system_instruction.strip(),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": user_instruction.strip(),
                    }
                ],
            },
        ],
    }

    timeout = httpx.Timeout(
        connect=30.0,
        read=180.0,
        write=60.0,
        pool=30.0,
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{OPENAI_BASE_URL}/responses",
            headers={
                **openai_headers(),
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        message = extract_openai_error(response)

        raise HTTPException(
            status_code=response.status_code,
            detail=f"خطای ساخت پرامپت حرفه‌ای: {message}",
        )

    enhanced_prompt = extract_responses_text(response.json())

    if not enhanced_prompt:
        raise HTTPException(
            status_code=502,
            detail="مدل متنی پرامپت حرفه‌ای برنگرداند.",
        )

    # محدودکردن طول برای جلوگیری از پرامپت غیرعادی
    enhanced_prompt = enhanced_prompt.strip()

    if len(enhanced_prompt) > 12000:
        enhanced_prompt = enhanced_prompt[:12000].rsplit(" ", 1)[0]

    return enhanced_prompt


@router.post(
    "/v1/video/enhance-prompt",
    response_model=VideoPromptEnhanceResponse,
)
async def preview_enhanced_video_prompt(
    request: VideoPromptEnhanceRequest,
    authorization: Optional[str] = Header(default=None),
):
    check_authorization(authorization)
    check_openai_key()

    enhanced_prompt = await enhance_video_prompt(
        original_prompt=request.prompt,
        seconds=request.seconds,
        size=request.size,
        style=request.style,
        camera_motion=request.camera_motion,
        realism=request.realism,
        target_platform=request.target_platform,
    )

    return VideoPromptEnhanceResponse(
        success=True,
        original_prompt=request.prompt,
        enhanced_prompt=enhanced_prompt,
        model=OPENAI_PROMPT_MODEL,
    )


async def create_openai_video(
    request: VideoGenerateRequest
) -> dict:
    form_data = {
        "model": request.model,
        "prompt": request.prompt.strip(),
        "seconds": request.seconds,
        "size": request.size,
    }

    timeout = httpx.Timeout(
        connect=30.0,
        read=180.0,
        write=60.0,
        pool=30.0
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        multipart_files = {
            "model": (None, request.model),
            "prompt": (None, request.prompt.strip()),
            "seconds": (None, request.seconds),
            "size": (None, request.size),
        }

        response = await client.post(
            f"{OPENAI_BASE_URL}/videos",
            headers=openai_headers(),
            files=multipart_files,
        )

    if response.status_code >= 400:
        message = extract_openai_error(response)

        raise HTTPException(
            status_code=response.status_code,
            detail=f"خطای شروع تولید ویدیو: {message}"
        )

    return response.json()


async def retrieve_openai_video(video_id: str) -> dict:
    timeout = httpx.Timeout(
        connect=30.0,
        read=120.0,
        write=30.0,
        pool=30.0
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(
            f"{OPENAI_BASE_URL}/videos/{video_id}",
            headers=openai_headers(),
        )

    if response.status_code >= 400:
        message = extract_openai_error(response)

        raise HTTPException(
            status_code=response.status_code,
            detail=f"خطای دریافت وضعیت ویدیو: {message}"
        )

    return response.json()


async def download_openai_video(video_id: str) -> tuple[str, str]:
    timeout = httpx.Timeout(
        connect=30.0,
        read=600.0,
        write=60.0,
        pool=30.0
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True
    ) as client:
        response = await client.get(
            f"{OPENAI_BASE_URL}/videos/{video_id}/content",
            headers=openai_headers(),
        )

    if response.status_code >= 400:
        message = extract_openai_error(response)

        raise HTTPException(
            status_code=response.status_code,
            detail=f"خطای دانلود ویدیو: {message}"
        )

    filename = (
        f"video-{time.strftime('%Y%m%d-%H%M%S')}-"
        f"{uuid.uuid4().hex[:8]}.mp4"
    )

    output_path = VIDEO_DIR / filename
    output_path.write_bytes(response.content)

    video_url = f"{PUBLIC_BASE_URL}/generated/videos/{filename}"

    return filename, video_url


@router.post(
    "/v1/video/generate",
    response_model=VideoGenerateResponse
)
async def generate_real_video(
    request: VideoGenerateRequest,
    authorization: Optional[str] = Header(default=None)
):
    check_authorization(authorization)
    check_openai_key()

    request.model = request.model.strip()
    request.seconds = str(request.seconds).strip()
    request.size = request.size.strip().lower()

    if request.model not in ALLOWED_VIDEO_MODELS:
        raise HTTPException(
            status_code=400,
            detail="مدل ویدیو باید sora-2 یا sora-2-pro باشد."
        )

    if request.seconds not in ALLOWED_VIDEO_SECONDS:
        raise HTTPException(
            status_code=400,
            detail="مدت ویدیو فقط می‌تواند 4، 8 یا 12 ثانیه باشد."
        )

    if request.size not in ALLOWED_VIDEO_SIZES:
        raise HTTPException(
            status_code=400,
            detail=(
                "اندازه ویدیو باید یکی از این مقادیر باشد: "
                "720x1280، 1280x720، 1024x1792، 1792x1024"
            )
        )

    original_prompt = request.prompt.strip()
    enhanced_prompt = original_prompt

    if request.auto_enhance:
        enhanced_prompt = await enhance_video_prompt(
            original_prompt=original_prompt,
            seconds=request.seconds,
            size=request.size,
            style=request.style,
            camera_motion=request.camera_motion,
            realism=request.realism,
            target_platform=request.target_platform,
        )

    # فقط پرامپت حرفه‌ای برای مدل ویدیو ارسال می‌شود.
    request.prompt = enhanced_prompt

    created = await create_openai_video(request)

    video_id = str(created.get("id", "")).strip()

    if not video_id:
        raise HTTPException(
            status_code=502,
            detail="OpenAI شناسه ویدیو برنگرداند."
        )

    status = str(created.get("status", "queued"))
    progress = int(created.get("progress") or 0)

    # حداکثر تقریباً ۱۵ دقیقه منتظر کامل‌شدن می‌مانیم.
    for _ in range(180):
        if status == "completed":
            filename, video_url = await download_openai_video(video_id)

            return VideoGenerateResponse(
                success=True,
                original_prompt=original_prompt,
                enhanced_prompt=enhanced_prompt,
                video_url=video_url,
                url=video_url,
                output_url=video_url,
                filename=filename,
                video_id=video_id,
                status="completed",
                progress=100,
                duration_seconds=float(request.seconds),
                model=request.model,
                size=request.size,
            )

        if status == "failed":
            error_object = created.get("error")
            error_message = "تولید ویدیو ناموفق بود."

            if isinstance(error_object, dict):
                error_message = str(
                    error_object.get("message") or error_message
                )

            raise HTTPException(
                status_code=502,
                detail=error_message
            )

        await asyncio.sleep(5)

        created = await retrieve_openai_video(video_id)
        status = str(created.get("status", status))
        progress = int(created.get("progress") or progress)

    return VideoGenerateResponse(
        success=True,
        original_prompt=original_prompt,
        enhanced_prompt=enhanced_prompt,
        video_id=video_id,
        status=status,
        progress=progress,
        duration_seconds=float(request.seconds),
        model=request.model,
        size=request.size,
        error=(
            "ساخت ویدیو هنوز کامل نشده است. "
            "وضعیت را با endpoint وضعیت بررسی کنید."
        ),
    )


@router.get(
    "/v1/video/status/{video_id}",
    response_model=VideoStatusResponse
)
async def get_video_status(
    video_id: str,
    authorization: Optional[str] = Header(default=None)
):
    check_authorization(authorization)
    check_openai_key()

    result = await retrieve_openai_video(video_id)

    status = str(result.get("status", "unknown"))
    progress = int(result.get("progress") or 0)

    if status == "completed":
        filename, video_url = await download_openai_video(video_id)

        return VideoStatusResponse(
            success=True,
            video_id=video_id,
            status="completed",
            progress=100,
            video_url=video_url,
        )

    error_message = None

    if status == "failed":
        error_object = result.get("error")

        if isinstance(error_object, dict):
            error_message = str(
                error_object.get("message") or "تولید ویدیو ناموفق بود."
            )

    return VideoStatusResponse(
        success=status != "failed",
        video_id=video_id,
        status=status,
        progress=progress,
        error=error_message,
    )


# === AISTUDIOPRO PROFESSIONAL VIDEO PREPARE V2 ===


class ProfessionalVideoPrepareRequest(BaseModel):
    topic: str = Field(
        min_length=3,
        max_length=6000
    )

    platform: str = "Instagram Reels"

    goal: str = "افزایش بازدید"

    duration: str = "8"

    style: str = "cinematic social media commercial"

    voice_type: str = "صدای زن"

    voice_tone: str = "گرم، طبیعی و حرفه‌ای"

    target_audience: str = (
        "مخاطبان عمومی شبکه‌های اجتماعی"
    )

    generate_images: bool = False


def _clean_json_content(
    content: str
) -> dict:
    cleaned = content.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):]

    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)

        if isinstance(parsed, dict):
            return parsed

    except Exception:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start >= 0 and end > start:
        candidate = cleaned[start:end + 1]

        try:
            parsed = json.loads(candidate)

            if isinstance(parsed, dict):
                return parsed

        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    "پاسخ هوش مصنوعی JSON معتبر نبود: "
                    f"{str(exc)[:200]}"
                )
            )

    raise HTTPException(
        status_code=502,
        detail=(
            "ساختار پاسخ آماده‌سازی پروژه "
            "قابل پردازش نبود."
        )
    )


def _normalize_prepare_result(
    result: dict,
    payload: ProfessionalVideoPrepareRequest,
    model: str
) -> dict:
    scenes = result.get("scenes")

    if not isinstance(scenes, list):
        scenes = []

    normalized_scenes = []

    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            continue

        normalized_scenes.append(
            {
                "number": index + 1,

                "time": str(
                    scene.get("time")
                    or ""
                ).strip(),

                "visual": str(
                    scene.get("visual")
                    or ""
                ).strip(),

                "camera": str(
                    scene.get("camera")
                    or ""
                ).strip(),

                "narration": str(
                    scene.get("narration")
                    or ""
                ).strip(),

                "image_prompt": str(
                    scene.get("image_prompt")
                    or scene.get("imagePrompt")
                    or ""
                ).strip()
            }
        )

    hashtags = result.get("hashtags")

    if not isinstance(hashtags, list):
        hashtags = []

    return {
        "success": True,

        "title": str(
            result.get("title")
            or payload.topic[:80]
        ).strip(),

        "hook": str(
            result.get("hook")
            or ""
        ).strip(),

        "script": str(
            result.get("script")
            or result.get("scenario")
            or ""
        ).strip(),

        "cta": str(
            result.get("cta")
            or ""
        ).strip(),

        "voice_text": str(
            result.get("voice_text")
            or result.get("voiceText")
            or ""
        ).strip(),

        "voice_instructions": str(
            result.get("voice_instructions")
            or result.get("voiceInstructions")
            or ""
        ).strip(),

        "video_prompt": str(
            result.get("video_prompt")
            or result.get("videoPrompt")
            or ""
        ).strip(),

        "caption": str(
            result.get("caption")
            or ""
        ).strip(),

        "cover_text": str(
            result.get("cover_text")
            or result.get("coverText")
            or ""
        ).strip(),

        "hashtags": [
            str(item).strip()
            for item in hashtags
            if str(item).strip()
        ],

        "scenes": normalized_scenes,

        "generate_images": payload.generate_images,

        "platform": payload.platform,

        "goal": payload.goal,

        "duration": payload.duration,

        "style": payload.style,

        "voice_type": payload.voice_type,

        "voice_tone": payload.voice_tone,

        "target_audience": payload.target_audience,

        "model": model,

        "message": (
            "طرح حرفه‌ای تولید محتوا آماده شد."
        )
    }


@router.post("/v1/video/prepare")
async def prepare_professional_video_project(
    payload: ProfessionalVideoPrepareRequest,
    authorization: str | None =
        Header(default=None),
):
    expected_token = (
        os.getenv("APP_API_TOKEN", "").strip()
    )

    if expected_token:
        received_token = (
            authorization or ""
        ).strip()

        expected_header = (
            f"Bearer {expected_token}"
        )

        if received_token != expected_header:
            raise HTTPException(
                status_code=401,
                detail="توکن دسترسی نامعتبر است."
            )

    model = (
        os.getenv("OPENAI_TEXT_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
        or "gpt-4.1-mini"
    )

    system_prompt = """
You are AIStudioPro's senior creative director,
commercial filmmaker, social-media strategist,
Persian copywriter, voice director and Sora prompt engineer.

Convert the user's simple idea into a complete,
production-ready social-media content package.

Return only one valid JSON object.
Do not use markdown.
Do not add explanations outside the JSON.

The response must include:

- professional Persian title
- powerful Persian hook
- practical Persian scenario
- final Persian voice-over text
- highly detailed English voice instructions
- highly detailed professional English Sora prompt
- Persian CTA
- Persian caption
- short Persian cover text
- Persian hashtags
- professional scene list
- professional English image prompt for every scene

VOICE REQUIREMENTS:

The final voice text must:
- sound natural and conversational in Persian
- fit the requested duration
- avoid literary or robotic language
- begin with a strong hook
- include useful pauses
- end with a clear CTA

The voice instructions must define:
- Persian pronunciation
- gender and perceived age
- tone
- emotion
- speaking speed
- energy
- pauses
- emphasis
- advertising delivery style

VIDEO REQUIREMENTS:

The video prompt must:
- be written in professional English
- be directly usable by Sora
- describe the opening frame precisely
- describe subject, environment and clothing
- describe lighting, camera, lens and framing
- describe only physically plausible actions
- preserve face, body, clothing and environment
- maintain temporal continuity
- avoid difficult hand-object interactions
- avoid morphing
- avoid duplicated limbs
- avoid unstable reflections
- avoid sudden scene changes
- contain no text, subtitle, logo or watermark

IMPORTANT CLOTHING RULE:

If the idea involves wearing, changing or trying on
clothing, never show the full dressing action.

The first frame must show the person already wearing
the garment correctly.

Only show safe movements such as:
- adjusting a collar
- touching one lapel
- smoothing the front
- checking one cuff
- turning slightly toward a mirror
- taking one natural step

IMAGE REQUIREMENTS:

Each image prompt must:
- be written in professional English
- use vertical 9:16 composition
- be photorealistic
- match its scene
- contain no text, logo or watermark

Images are optional.
Video generation must never depend on generated images.
""".strip()

    user_prompt = f"""
Prepare a complete professional content production package.

USER IDEA:
{payload.topic}

PLATFORM:
{payload.platform}

CONTENT GOAL:
{payload.goal}

VIDEO DURATION:
{payload.duration} seconds

VISUAL STYLE:
{payload.style}

VOICE TYPE:
{payload.voice_type}

VOICE TONE:
{payload.voice_tone}

TARGET AUDIENCE:
{payload.target_audience}

GENERATE OPTIONAL IMAGES:
{payload.generate_images}

Return exactly this JSON structure:

{{
  "title": "عنوان حرفه‌ای فارسی",

  "hook": "هوک کوتاه و قدرتمند فارسی",

  "script": "سناریوی کامل و کاربردی فارسی",

  "cta": "دعوت به اقدام فارسی",

  "voice_text": "متن نهایی و طبیعی گویندگی فارسی",

  "voice_instructions": "Detailed professional English instructions for Persian TTS delivery",

  "video_prompt": "Extremely detailed professional English Sora prompt",

  "caption": "کپشن کامل فارسی آماده انتشار",

  "cover_text": "متن کوتاه فارسی برای کاور",

  "hashtags": [
    "#هشتگ"
  ],

  "scenes": [
    {{
      "number": 1,

      "time": "0-3s",

      "visual": "شرح فارسی اتفاق صحنه",

      "camera": "شرح فارسی حرکت و زاویه دوربین",

      "narration": "متن گویندگی فارسی همان صحنه",

      "image_prompt": "Professional English 9:16 photorealistic image prompt"
    }}
  ]
}}

Important:

- The first two seconds must be visually powerful.
- Keep the voice text short enough for the duration.
- Create approximately 3 scenes for 8 seconds.
- Create approximately 4 scenes for 12 seconds.
- Image prompts must always be returned even when
  generate_images is false.
- Return only valid JSON.
""".strip()

    body = {
        "model": model,

        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],

        "temperature": 0.65
    }

    timeout = httpx.Timeout(
        240.0,
        connect=30.0
    )

    async with httpx.AsyncClient(
        timeout=timeout
    ) as client:
        response = await client.post(
            (
                os.getenv(
                    "OPENAI_BASE_URL",
                    "https://api.openai.com/v1"
                ).rstrip("/")
                + "/chat/completions"
            ),

            headers={
                "Authorization": (
                    "Bearer "
                    + os.getenv(
                        "OPENAI_API_KEY",
                        ""
                    ).strip()
                ),
                "Content-Type":
                    "application/json"
            },

            json=body
        )

    if response.status_code >= 400:
        error_text = response.text[:1500]

        raise HTTPException(
            status_code=502,
            detail={
                "message": "خطا در آماده‌سازی حرفه‌ای پروژه",
                "openai_status": response.status_code,
                "openai_response": error_text
            }
        )

    response_json = response.json()

    choices = response_json.get("choices") or []

    if not choices:
        raise HTTPException(
            status_code=502,
            detail=(
                "هوش مصنوعی پاسخی برای "
                "آماده‌سازی پروژه برنگرداند."
            )
        )

    first_choice = choices[0]

    if not isinstance(first_choice, dict):
        raise HTTPException(
            status_code=502,
            detail="ساختار پاسخ هوش مصنوعی نامعتبر بود."
        )

    message = first_choice.get("message") or {}

    if not isinstance(message, dict):
        raise HTTPException(
            status_code=502,
            detail="پیام هوش مصنوعی نامعتبر بود."
        )

    content = message.get("content") or ""

    if isinstance(content, list):
        text_parts = []

        for item in content:
            if isinstance(item, dict):
                item_text = item.get("text")

                if item_text:
                    text_parts.append(str(item_text))

        content = "\n".join(text_parts)

    content = str(content).strip()

    if not content:
        raise HTTPException(
            status_code=502,
            detail=(
                "متن پاسخ آماده‌سازی پروژه خالی بود."
            )
        )

    parsed = _clean_json_content(content)

    return _normalize_prepare_result(
        result=parsed,
        payload=payload,
        model=model
    )



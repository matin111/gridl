from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/v1/video",
    tags=["Video Studio"],
)

APP_API_TOKEN = os.getenv("APP_API_TOKEN", "").strip()

PROJECT_ROOT = Path("/root/aistudio-api")
GENERATED_ROOT = PROJECT_ROOT / "generated"
VIDEO_OUTPUT_DIR = GENERATED_ROOT / "videos"
VIDEO_TEMP_DIR = GENERATED_ROOT / "video-temp"

VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_TEMP_DIR.mkdir(parents=True, exist_ok=True)

PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://ap.movifilm.sbs",
).rstrip("/")


class VideoSceneRequest(BaseModel):
    scene_number: int = Field(ge=1)
    image_url: str = Field(min_length=5, max_length=3000)
    duration_seconds: float = Field(default=4.0, ge=1.0, le=15.0)


class VideoRenderRequest(BaseModel):
    title: str = Field(default="AIStudioPro Video", max_length=300)
    scenes: list[VideoSceneRequest] = Field(min_length=1, max_length=20)

    width: int = Field(default=1080, ge=360, le=2160)
    height: int = Field(default=1920, ge=640, le=3840)
    fps: int = Field(default=30, ge=24, le=60)

    quality: str = Field(default="medium")
    transition: str = Field(default="fade")


class VideoRenderResponse(BaseModel):
    success: bool
    video_url: str | None = None
    filename: str | None = None
    duration_seconds: float = 0.0
    scene_count: int = 0
    message: str | None = None


def verify_token(authorization: str | None) -> None:
    if not APP_API_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="APP_API_TOKEN روی سرور تنظیم نشده است.",
        )

    expected = f"Bearer {APP_API_TOKEN}"

    if authorization != expected:
        raise HTTPException(
            status_code=401,
            detail="توکن برنامه معتبر نیست.",
        )


def safe_remove(path: Path) -> None:
    try:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink(missing_ok=True)
    except Exception:
        pass


async def download_image(
    client: httpx.AsyncClient,
    image_url: str,
    destination: Path,
) -> None:
    parsed = urlparse(image_url)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("آدرس تصویر معتبر نیست.")

    response = await client.get(
        image_url,
        follow_redirects=True,
        timeout=90.0,
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "content-type",
        "",
    ).lower()

    if "image" not in content_type:
        raise ValueError(
            f"فایل دریافت‌شده تصویر نیست: {content_type}"
        )

    destination.write_bytes(response.content)


def run_command(command: list[str]) -> None:
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        error_text = result.stderr[-4000:]

        raise RuntimeError(
            f"FFmpeg error:\n{error_text}"
        )


def create_scene_video(
    image_path: Path,
    output_path: Path,
    duration_seconds: float,
    width: int,
    height: int,
    fps: int,
) -> None:
    total_frames = max(
        int(duration_seconds * fps),
        fps,
    )

    zoom_increment = 0.0008

    video_filter = (
        f"scale={width}:{height}:"
        f"force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"zoompan="
        f"z='min(zoom+{zoom_increment},1.08)':"
        f"x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':"
        f"d={total_frames}:"
        f"s={width}x{height}:"
        f"fps={fps},"
        f"format=yuv420p"
    )

    run_command(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-vf",
            video_filter,
            "-t",
            str(duration_seconds),
            "-r",
            str(fps),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )


def concat_scene_videos(
    scene_videos: list[Path],
    output_path: Path,
) -> None:
    concat_file = output_path.parent / "concat.txt"

    concat_lines = []

    for video_path in scene_videos:
        escaped_path = str(video_path).replace(
            "'",
            "'\\''",
        )

        concat_lines.append(
            f"file '{escaped_path}'"
        )

    concat_file.write_text(
        "\n".join(concat_lines),
        encoding="utf-8",
    )

    try:
        run_command(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )
    finally:
        concat_file.unlink(missing_ok=True)


def render_video_sync(
    request: VideoRenderRequest,
    downloaded_images: list[Path],
    work_dir: Path,
    output_path: Path,
) -> None:
    scene_videos: list[Path] = []

    for index, scene in enumerate(request.scenes):
        scene_video_path = (
            work_dir /
            f"scene-{index + 1:02d}.mp4"
        )

        create_scene_video(
            image_path=downloaded_images[index],
            output_path=scene_video_path,
            duration_seconds=scene.duration_seconds,
            width=request.width,
            height=request.height,
            fps=request.fps,
        )

        scene_videos.append(scene_video_path)

    concat_scene_videos(
        scene_videos=scene_videos,
        output_path=output_path,
    )


@router.post(
    "/render",
    response_model=VideoRenderResponse,
)
async def render_video(
    request: VideoRenderRequest,
    authorization: str | None = Header(default=None),
) -> VideoRenderResponse:
    verify_token(authorization)

    if not request.scenes:
        raise HTTPException(
            status_code=422,
            detail="حداقل یک صحنه لازم است.",
        )

    job_id = uuid.uuid4().hex
    work_dir = VIDEO_TEMP_DIR / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    output_filename = f"ai-video-{job_id}.mp4"
    output_path = VIDEO_OUTPUT_DIR / output_filename

    downloaded_images: list[Path] = []

    try:
        async with httpx.AsyncClient() as client:
            for index, scene in enumerate(request.scenes):
                image_path = (
                    work_dir /
                    f"image-{index + 1:02d}.jpg"
                )

                await download_image(
                    client=client,
                    image_url=scene.image_url,
                    destination=image_path,
                )

                downloaded_images.append(image_path)

        await asyncio.to_thread(
            render_video_sync,
            request,
            downloaded_images,
            work_dir,
            output_path,
        )

        if not output_path.exists():
            raise RuntimeError(
                "فایل ویدیوی خروجی ساخته نشد."
            )

        if output_path.stat().st_size < 10_000:
            raise RuntimeError(
                "حجم فایل خروجی غیرعادی است."
            )

        total_duration = sum(
            scene.duration_seconds
            for scene in request.scenes
        )

        return VideoRenderResponse(
            success=True,
            video_url=(
                f"{PUBLIC_BASE_URL}"
                f"/generated/videos/"
                f"{output_filename}"
            ),
            filename=output_filename,
            duration_seconds=total_duration,
            scene_count=len(request.scenes),
            message="ویدیو با موفقیت ساخته شد.",
        )

    except httpx.HTTPError as error:
        safe_remove(output_path)

        raise HTTPException(
            status_code=502,
            detail=(
                "دانلود یکی از تصاویر انجام نشد: "
                f"{error}"
            ),
        ) from error

    except Exception as error:
        safe_remove(output_path)

        raise HTTPException(
            status_code=500,
            detail=f"ساخت ویدیو انجام نشد: {error}",
        ) from error

    finally:
        safe_remove(work_dir)

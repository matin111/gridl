from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel


router = APIRouter(
    prefix="/v1/media",
    tags=["media-retention"],
)


BASE_DIR = Path("/root/aistudio-api")

MEDIA_DIRECTORIES = {
    "generated": BASE_DIR / "generated" / "images",
    "edited": BASE_DIR / "generated" / "image-edits",
}

MEDIA_URL_PREFIXES = {
    "generated": "/generated/images",
    "edited": "/generated/image-edits",
}

ALLOWED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}

RETENTION_DAYS = int(
    os.getenv(
        "MEDIA_RETENTION_DAYS",
        "7",
    )
)

WARNING_HOURS = int(
    os.getenv(
        "MEDIA_RETENTION_WARNING_HOURS",
        "24",
    )
)


class MediaRetentionItem(BaseModel):
    filename: str
    media_type: Literal["generated", "edited"]
    image_url: str
    created_at: str
    expires_at: str
    seconds_remaining: int
    hours_remaining: int
    days_remaining: int
    expiring_soon: bool
    expired: bool


class MediaRetentionResponse(BaseModel):
    success: bool
    retention_days: int
    warning_hours: int
    server_time: str
    items: list[MediaRetentionItem]
    message: str | None = None


class CleanupResponse(BaseModel):
    success: bool
    deleted_count: int
    deleted_files: list[str]
    failed_files: list[str]
    message: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_app_token() -> str:
    return os.getenv(
        "APP_API_TOKEN",
        "",
    ).strip()


def verify_authorization(
    authorization: str | None,
) -> None:
    expected_token = get_app_token()

    if not expected_token:
        raise HTTPException(
            status_code=500,
            detail="APP_API_TOKEN روی سرور تنظیم نشده است.",
        )

    expected_header = f"Bearer {expected_token}"

    if authorization != expected_header:
        raise HTTPException(
            status_code=401,
            detail="دسترسی غیرمجاز است.",
        )


def ensure_directories() -> None:
    for directory in MEDIA_DIRECTORIES.values():
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


def file_created_at(
    file_path: Path,
) -> datetime:
    stat = file_path.stat()

    # در لینوکس معمولاً birthtime وجود ندارد؛
    # mtime زمان مناسب‌تری برای فایل تولیدشده است.
    timestamp = stat.st_mtime

    return datetime.fromtimestamp(
        timestamp,
        tz=timezone.utc,
    )


def build_public_url(
    media_type: str,
    filename: str,
) -> str:
    public_base_url = os.getenv(
        "PUBLIC_BASE_URL",
        "https://ap.movifilm.sbs",
    ).rstrip("/")

    prefix = MEDIA_URL_PREFIXES[media_type]

    return f"{public_base_url}{prefix}/{filename}"


def calculate_status(
    *,
    file_path: Path,
    media_type: Literal["generated", "edited"],
    now: datetime,
) -> MediaRetentionItem:
    created_at = file_created_at(
        file_path
    )

    expires_at = (
        created_at +
        timedelta(days=RETENTION_DAYS)
    )

    remaining_seconds = int(
        (
            expires_at - now
        ).total_seconds()
    )

    safe_remaining_seconds = max(
        remaining_seconds,
        0,
    )

    hours_remaining = (
        safe_remaining_seconds // 3600
    )

    days_remaining = (
        safe_remaining_seconds // 86400
    )

    expired = (
        remaining_seconds <= 0
    )

    expiring_soon = (
        not expired
        and
        remaining_seconds <=
        WARNING_HOURS * 3600
    )

    return MediaRetentionItem(
        filename=file_path.name,
        media_type=media_type,
        image_url=build_public_url(
            media_type,
            file_path.name,
        ),
        created_at=created_at.isoformat(),
        expires_at=expires_at.isoformat(),
        seconds_remaining=
            safe_remaining_seconds,
        hours_remaining=
            hours_remaining,
        days_remaining=
            days_remaining,
        expiring_soon=
            expiring_soon,
        expired=
            expired,
    )


def list_media_items(
    *,
    include_expired: bool = False,
) -> list[MediaRetentionItem]:
    ensure_directories()

    now = utc_now()
    items: list[MediaRetentionItem] = []

    for media_type, directory in (
        MEDIA_DIRECTORIES.items()
    ):
        for file_path in directory.iterdir():
            if not file_path.is_file():
                continue

            if (
                file_path.suffix.lower()
                not in ALLOWED_EXTENSIONS
            ):
                continue

            status = calculate_status(
                file_path=file_path,
                media_type=media_type,
                now=now,
            )

            if (
                status.expired
                and
                not include_expired
            ):
                continue

            items.append(
                status
            )

    return sorted(
        items,
        key=lambda item: item.created_at,
        reverse=True,
    )


def cleanup_expired_media() -> CleanupResponse:
    ensure_directories()

    now = utc_now()

    deleted_files: list[str] = []
    failed_files: list[str] = []

    for media_type, directory in (
        MEDIA_DIRECTORIES.items()
    ):
        for file_path in directory.iterdir():
            if not file_path.is_file():
                continue

            if (
                file_path.suffix.lower()
                not in ALLOWED_EXTENSIONS
            ):
                continue

            try:
                created_at = file_created_at(
                    file_path
                )

                expires_at = (
                    created_at +
                    timedelta(
                        days=RETENTION_DAYS
                    )
                )

                if now < expires_at:
                    continue

                file_path.unlink()

                deleted_files.append(
                    f"{media_type}/{file_path.name}"
                )

            except Exception:
                failed_files.append(
                    f"{media_type}/{file_path.name}"
                )

    return CleanupResponse(
        success=
            len(failed_files) == 0,
        deleted_count=
            len(deleted_files),
        deleted_files=
            deleted_files,
        failed_files=
            failed_files,
        message=(
            f"{len(deleted_files)} فایل منقضی حذف شد."
        ),
    )


@router.get(
    "/retention",
    response_model=MediaRetentionResponse,
)
async def get_media_retention(
    authorization: str | None =
        Header(default=None),
) -> MediaRetentionResponse:
    verify_authorization(
        authorization
    )

    items = list_media_items(
        include_expired=False
    )

    return MediaRetentionResponse(
        success=True,
        retention_days=
            RETENTION_DAYS,
        warning_hours=
            WARNING_HOURS,
        server_time=
            utc_now().isoformat(),
        items=
            items,
        message=
            "وضعیت نگهداری تصاویر دریافت شد.",
    )


@router.post(
    "/cleanup",
    response_model=CleanupResponse,
)
async def cleanup_media_endpoint(
    authorization: str | None =
        Header(default=None),
) -> CleanupResponse:
    verify_authorization(
        authorization
    )

    return cleanup_expired_media()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--cleanup",
        action="store_true",
    )

    arguments = parser.parse_args()

    if arguments.cleanup:
        result = cleanup_expired_media()

        print(
            result.model_dump_json(
                indent=2
            )
        )

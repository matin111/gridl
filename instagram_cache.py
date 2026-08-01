from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent

CACHE_DIR = Path(
    os.getenv(
        "INSTAGRAM_CACHE_DIR",
        str(BASE_DIR / "cache" / "instagram"),
    )
)

CACHE_TTL_SECONDS = int(
    os.getenv(
        "INSTAGRAM_CACHE_TTL_SECONDS",
        "1800",
    )
)

STALE_CACHE_TTL_SECONDS = int(
    os.getenv(
        "INSTAGRAM_STALE_CACHE_TTL_SECONDS",
        "604800",
    )
)


def _normalize_username(username: str) -> str:
    value = (username or "").strip().lower()

    value = value.removeprefix("@")

    if not value:
        raise ValueError(
            "نام کاربری برای کش خالی است."
        )

    return value


def _cache_file(username: str) -> Path:
    normalized = _normalize_username(username)

    safe_name = "".join(
        character
        if character.isalnum() or character in "._-"
        else "_"
        for character in normalized
    )

    digest = hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()[:12]

    return CACHE_DIR / f"{safe_name}-{digest}.json"


def load_analysis_cache(
    username: str,
    allow_stale: bool = False,
) -> dict[str, Any] | None:
    try:
        path = _cache_file(username)

        if not path.exists():
            return None

        age_seconds = max(
            0.0,
            time.time() - path.stat().st_mtime,
        )

        maximum_age = (
            STALE_CACHE_TTL_SECONDS
            if allow_stale
            else CACHE_TTL_SECONDS
        )

        if maximum_age >= 0 and age_seconds > maximum_age:
            if not allow_stale:
                return None

            if age_seconds > STALE_CACHE_TTL_SECONDS:
                return None

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            payload = json.load(file)

        if not isinstance(payload, dict):
            return None

        response_data = payload.get(
            "response_data"
        )

        if isinstance(response_data, dict):
            return response_data

        # پشتیبانی از کش‌هایی که مستقیماً
        # پاسخ تحلیل را ذخیره کرده‌اند.
        if "success" in payload:
            return payload

        return None

    except (
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as error:
        print(
            "INSTAGRAM CACHE LOAD ERROR:",
            repr(error),
            flush=True,
        )

        return None


def save_analysis_cache(
    username: str,
    response_data: dict[str, Any],
) -> None:
    try:
        if not isinstance(response_data, dict):
            raise TypeError(
                "response_data باید dict باشد."
            )

        CACHE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination = _cache_file(username)

        payload = {
            "username": _normalize_username(
                username
            ),
            "saved_at": int(time.time()),
            "response_data": response_data,
        }

        temporary_path: str | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(CACHE_DIR),
                prefix=".instagram-cache-",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = (
                    temporary_file.name
                )

                json.dump(
                    payload,
                    temporary_file,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )

                temporary_file.flush()

                os.fsync(
                    temporary_file.fileno()
                )

            os.replace(
                temporary_path,
                destination,
            )

        finally:
            if (
                temporary_path
                and os.path.exists(temporary_path)
            ):
                try:
                    os.unlink(temporary_path)
                except OSError:
                    pass

    except (
        OSError,
        ValueError,
        TypeError,
    ) as error:
        print(
            "INSTAGRAM CACHE SAVE ERROR:",
            repr(error),
            flush=True,
        )


def delete_analysis_cache(
    username: str,
) -> bool:
    try:
        path = _cache_file(username)

        if not path.exists():
            return False

        path.unlink()

        return True

    except (OSError, ValueError):
        return False


def clear_analysis_cache() -> int:
    deleted_count = 0

    try:
        if not CACHE_DIR.exists():
            return 0

        for path in CACHE_DIR.glob("*.json"):
            try:
                path.unlink()
                deleted_count += 1
            except OSError:
                continue

    except OSError:
        return deleted_count

    return deleted_count

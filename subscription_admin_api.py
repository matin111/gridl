from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/v1",
    tags=["subscription"],
)


BASE_DIR = Path("/root/aistudio-api")
DATABASE_PATH = BASE_DIR / "subscription.db"


FREE_LIMITS: dict[str, int] = {
    "image_generate": 3,
    "image_edit": 3,
    "planner": 1,
    "analyzer": 1,
    "text_content": 5,
}


DAILY_FEATURES = {
    "text_content",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail="فرمت تاریخ معتبر نیست.",
        ) from error


@contextmanager
def database():
    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    try:
        yield connection
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def initialize_database() -> None:
    with database() as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                installation_id TEXT NOT NULL UNIQUE,
                display_name TEXT,
                phone TEXT,
                email TEXT,
                auth_user_id TEXT,
                device_model TEXT,
                manufacturer TEXT,
                android_version TEXT,
                app_version TEXT,
                is_blocked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                plan_key TEXT NOT NULL,
                source TEXT NOT NULL,
                starts_at TEXT NOT NULL,
                expires_at TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_manual INTEGER NOT NULL DEFAULT 0,
                purchase_token TEXT,
                product_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_subscriptions_user
            ON subscriptions(user_id);

            CREATE TABLE IF NOT EXISTS campaigns (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                audience TEXT NOT NULL,
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                premium_access INTEGER NOT NULL DEFAULT 1,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS campaign_features (
                campaign_id TEXT NOT NULL,
                feature_key TEXT NOT NULL,
                PRIMARY KEY(campaign_id, feature_key),
                FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
            );

            CREATE TABLE IF NOT EXISTS usage_counters (
                user_id TEXT NOT NULL,
                feature_key TEXT NOT NULL,
                period_key TEXT NOT NULL,
                used_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, feature_key, period_key),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                audience TEXT NOT NULL,
                target_route TEXT,
                image_url TEXT,
                scheduled_at TEXT,
                sent_at TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notification_reads (
                notification_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                read_at TEXT NOT NULL,
                PRIMARY KEY(notification_id, user_id),
                FOREIGN KEY(notification_id) REFERENCES notifications(id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS admin_actions (
                id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id TEXT,
                payload TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS campaign_events (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                installation_id TEXT,
                event_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_campaign_events_campaign
            ON campaign_events(campaign_id, event_type);

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS feature_flags (
                feature_key TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                premium_only INTEGER NOT NULL DEFAULT 0,
                message TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS usage_events (
                id TEXT PRIMARY KEY,
                installation_id TEXT NOT NULL,
                feature_key TEXT NOT NULL,
                event_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_usage_events_created
            ON usage_events(created_at);
            """
        )

        # Lightweight SQLite migrations for older installations.
        user_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        user_additions = {
            "auth_user_id": "TEXT",
            "device_model": "TEXT",
            "manufacturer": "TEXT",
            "android_version": "TEXT",
            "app_version": "TEXT",
        }
        for name, column_type in user_additions.items():
            if name not in user_columns:
                connection.execute(
                    f"ALTER TABLE users ADD COLUMN {name} {column_type}"
                )

        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_auth_user_id ON users(auth_user_id)"
        )

        campaign_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(campaigns)").fetchall()
        }
        additions = {
            "badge_text": "TEXT",
            "button_text": "TEXT",
            "action_type": "TEXT NOT NULL DEFAULT 'none'",
            "action_value": "TEXT",
            "image_url": "TEXT",
            "priority": "INTEGER NOT NULL DEFAULT 0",
            "dismissible": "INTEGER NOT NULL DEFAULT 1",
            "show_once": "INTEGER NOT NULL DEFAULT 0",
            "campaign_type": "TEXT NOT NULL DEFAULT 'banner'",
        }
        for name, column_type in additions.items():
            if name not in campaign_columns:
                connection.execute(
                    f"ALTER TABLE campaigns ADD COLUMN {name} {column_type}"
                )

        now = isoformat(utc_now())
        default_settings = {
            "beta_enabled": "1",
            "beta_title": "نسخه آزمایشی رایگان",
            "minimum_version_code": "1",
            "latest_version_code": "1",
            "force_update": "0",
            "update_message": "نسخه جدید AIStudioPro منتشر شده است.",
        }
        for key, value in default_settings.items():
            connection.execute(
                "INSERT OR IGNORE INTO app_settings(key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, now),
            )

        default_flags = [
            ("analyzer", "تحلیل پیج", 1, 0),
            ("content_studio", "استودیو محتوا", 1, 0),
            ("image_generator", "ساخت تصویر", 1, 0),
            ("image_edit", "ویرایش تصویر", 1, 0),
            ("video_studio", "استودیو ویدیو", 1, 0),
            ("planner", "برنامه رشد", 1, 0),
            ("trends", "مرکز ترند", 1, 0),
        ]
        for feature_key, title, enabled, premium_only in default_flags:
            connection.execute(
                """
                INSERT OR IGNORE INTO feature_flags(
                    feature_key, title, enabled, premium_only, message, updated_at
                ) VALUES (?, ?, ?, ?, NULL, ?)
                """,
                (feature_key, title, enabled, premium_only, now),
            )


initialize_database()


def bearer_token(
    authorization: str | None,
) -> str:
    if not authorization:
        return ""

    prefix = "Bearer "

    if not authorization.startswith(prefix):
        return ""

    return authorization[len(prefix):].strip()


def verify_app_token(
    authorization: str | None,
) -> None:
    expected = os.getenv(
        "APP_API_TOKEN",
        "",
    ).strip()

    if not expected:
        raise HTTPException(
            status_code=500,
            detail="APP_API_TOKEN روی سرور تنظیم نشده است.",
        )

    if bearer_token(authorization) != expected:
        raise HTTPException(
            status_code=401,
            detail="دسترسی غیرمجاز است.",
        )


def verify_admin_token(
    authorization: str | None,
) -> None:
    expected = os.getenv(
        "ADMIN_API_TOKEN",
        "",
    ).strip()

    if not expected:
        raise HTTPException(
            status_code=500,
            detail="ADMIN_API_TOKEN روی سرور تنظیم نشده است.",
        )

    if bearer_token(authorization) != expected:
        raise HTTPException(
            status_code=401,
            detail="دسترسی مدیریتی غیرمجاز است.",
        )


def get_or_create_user(
    installation_id: str,
    display_name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    auth_user_id: str | None = None,
    device_model: str | None = None,
    manufacturer: str | None = None,
    android_version: str | None = None,
    app_version: str | None = None,
) -> sqlite3.Row:
    now = isoformat(utc_now())
    normalized_auth_id = (auth_user_id or "").strip() or None

    with database() as connection:
        existing = connection.execute(
            "SELECT * FROM users WHERE installation_id = ?",
            (installation_id,),
        ).fetchone()

        if existing is None and normalized_auth_id:
            existing = connection.execute(
                "SELECT * FROM users WHERE auth_user_id = ? ORDER BY last_seen_at DESC LIMIT 1",
                (normalized_auth_id,),
            ).fetchone()

        if existing:
            old_installation_id = existing["installation_id"]
            if old_installation_id != installation_id:
                collision = connection.execute(
                    "SELECT id FROM users WHERE installation_id = ? AND id != ?",
                    (installation_id, existing["id"]),
                ).fetchone()
                if collision is None:
                    connection.execute(
                        "UPDATE users SET installation_id = ? WHERE id = ?",
                        (installation_id, existing["id"]),
                    )

            connection.execute(
                """
                UPDATE users
                SET display_name = COALESCE(NULLIF(?, ''), display_name),
                    phone = COALESCE(NULLIF(?, ''), phone),
                    email = COALESCE(NULLIF(?, ''), email),
                    auth_user_id = COALESCE(NULLIF(?, ''), auth_user_id),
                    device_model = COALESCE(NULLIF(?, ''), device_model),
                    manufacturer = COALESCE(NULLIF(?, ''), manufacturer),
                    android_version = COALESCE(NULLIF(?, ''), android_version),
                    app_version = COALESCE(NULLIF(?, ''), app_version),
                    updated_at = ?,
                    last_seen_at = ?
                WHERE id = ?
                """,
                (
                    display_name, phone, email, normalized_auth_id,
                    device_model, manufacturer, android_version, app_version,
                    now, now, existing["id"],
                ),
            )
            return connection.execute(
                "SELECT * FROM users WHERE id = ?",
                (existing["id"],),
            ).fetchone()

        user_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO users (
                id, installation_id, display_name, phone, email,
                auth_user_id, device_model, manufacturer, android_version, app_version,
                created_at, updated_at, last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id, installation_id, display_name, phone, email,
                normalized_auth_id, device_model, manufacturer, android_version, app_version,
                now, now, now,
            ),
        )
        return connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()


def active_manual_or_bazaar_subscription(
    user_id: str,
) -> sqlite3.Row | None:
    now = isoformat(utc_now())

    with database() as connection:
        return connection.execute(
            """
            SELECT *
            FROM subscriptions
            WHERE user_id = ?
              AND is_active = 1
              AND (
                    expires_at IS NULL
                    OR expires_at > ?
                  )
            ORDER BY
                is_manual DESC,
                created_at DESC
            LIMIT 1
            """,
            (
                user_id,
                now,
            ),
        ).fetchone()


def active_campaign(
    audience: Literal[
        "all",
        "free",
        "premium",
        "new_users",
    ],
) -> sqlite3.Row | None:
    now = isoformat(utc_now())

    with database() as connection:
        return connection.execute(
            """
            SELECT *
            FROM campaigns
            WHERE enabled = 1
              AND starts_at <= ?
              AND ends_at > ?
              AND audience IN ('all', ?)
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (
                now,
                now,
                audience,
            ),
        ).fetchone()


def user_subscription_snapshot(
    user: sqlite3.Row,
) -> dict:
    if bool(user["is_blocked"]):
        return {
            "is_premium": False,
            "plan_key": "blocked",
            "source": "admin",
            "starts_at": None,
            "expires_at": None,
            "campaign_id": None,
            "campaign_title": None,
            "blocked": True,
        }

    subscription = active_manual_or_bazaar_subscription(
        user["id"]
    )

    if subscription:
        return {
            "is_premium": True,
            "plan_key": subscription["plan_key"],
            "source": subscription["source"],
            "starts_at": subscription["starts_at"],
            "expires_at": subscription["expires_at"],
            "campaign_id": None,
            "campaign_title": None,
            "blocked": False,
        }

    campaign = active_campaign(
        audience="free",
    )

    if campaign:
        return {
            "is_premium": bool(
                campaign["premium_access"]
            ),
            "plan_key": "campaign",
            "source": "campaign",
            "starts_at": campaign["starts_at"],
            "expires_at": campaign["ends_at"],
            "campaign_id": campaign["id"],
            "campaign_title": campaign["title"],
            "blocked": False,
        }

    return {
        "is_premium": False,
        "plan_key": "free",
        "source": "free",
        "starts_at": None,
        "expires_at": None,
        "campaign_id": None,
        "campaign_title": None,
        "blocked": False,
    }


def usage_period_key(
    feature_key: str,
) -> str:
    if feature_key in DAILY_FEATURES:
        return utc_now().date().isoformat()

    return "lifetime"


def read_usage(
    user_id: str,
    feature_key: str,
) -> int:
    period_key = usage_period_key(
        feature_key
    )

    with database() as connection:
        row = connection.execute(
            """
            SELECT used_count
            FROM usage_counters
            WHERE user_id = ?
              AND feature_key = ?
              AND period_key = ?
            """,
            (
                user_id,
                feature_key,
                period_key,
            ),
        ).fetchone()

    return int(row["used_count"]) if row else 0


def quota_snapshot(
    user: sqlite3.Row,
    subscription: dict,
) -> dict[str, dict]:
    result: dict[str, dict] = {}

    for feature_key, free_limit in FREE_LIMITS.items():
        if subscription["is_premium"]:
            result[feature_key] = {
                "used": 0,
                "limit": None,
                "remaining": None,
                "unlimited": True,
                "has_access": True,
            }
            continue

        used = read_usage(
            user["id"],
            feature_key,
        )

        remaining = max(
            free_limit - used,
            0,
        )

        result[feature_key] = {
            "used": used,
            "limit": free_limit,
            "remaining": remaining,
            "unlimited": False,
            "has_access": remaining > 0,
        }

    return result


class RegisterRequest(BaseModel):
    installation_id: str = Field(
        min_length=8,
        max_length=200,
    )

    display_name: str | None = Field(
        default=None,
        max_length=120,
    )

    phone: str | None = Field(
        default=None,
        max_length=40,
    )

    email: str | None = Field(
        default=None,
        max_length=160,
    )

    auth_user_id: str | None = Field(default=None, max_length=200)
    device_model: str | None = Field(default=None, max_length=160)
    manufacturer: str | None = Field(default=None, max_length=120)
    android_version: str | None = Field(default=None, max_length=80)
    app_version: str | None = Field(default=None, max_length=80)


class UsageConsumeRequest(BaseModel):
    installation_id: str = Field(
        min_length=8,
        max_length=200,
    )

    feature_key: str


class CampaignCreateRequest(BaseModel):
    title: str = Field(
        min_length=2,
        max_length=160,
    )

    description: str | None = Field(
        default=None,
        max_length=1000,
    )

    audience: Literal[
        "all",
        "free",
        "premium",
        "new_users",
    ] = "free"

    starts_at: str
    ends_at: str

    premium_access: bool = True

    enabled: bool = True

    feature_keys: list[str] = Field(
        default_factory=list,
    )

    badge_text: str | None = Field(default=None, max_length=80)
    button_text: str | None = Field(default=None, max_length=80)
    action_type: Literal[
        "none", "route", "url", "analyzer", "planner",
        "ai_studio", "subscription", "trend", "hashtag"
    ] = "none"
    action_value: str | None = Field(default=None, max_length=1000)
    image_url: str | None = Field(default=None, max_length=1000)
    priority: int = Field(default=0, ge=-1000, le=1000)
    dismissible: bool = True
    show_once: bool = False
    campaign_type: Literal["banner", "dialog", "card"] = "banner"


class ManualSubscriptionRequest(BaseModel):
    installation_id: str = Field(
        min_length=8,
        max_length=200,
    )

    days: int | None = Field(
        default=None,
        ge=1,
        le=3650,
    )

    plan_key: str = "manual"


class NotificationCreateRequest(BaseModel):
    title: str = Field(
        min_length=2,
        max_length=160,
    )

    body: str = Field(
        min_length=2,
        max_length=2000,
    )

    audience: Literal[
        "all",
        "free",
        "premium",
        "expired",
        "new_users",
    ] = "all"

    target_route: str | None = Field(
        default=None,
        max_length=200,
    )

    image_url: str | None = Field(
        default=None,
        max_length=1000,
    )

    scheduled_at: str | None = None


class MarkNotificationReadRequest(BaseModel):
    installation_id: str = Field(
        min_length=8,
        max_length=200,
    )

    notification_id: str


@router.post("/subscription/register")
async def register_user(
    request: RegisterRequest,
    authorization: str | None = Header(default=None),
):
    verify_app_token(
        authorization
    )

    user = get_or_create_user(
        installation_id = request.installation_id,
        display_name = request.display_name,
        phone = request.phone,
        email = request.email,
        auth_user_id = request.auth_user_id,
        device_model = request.device_model,
        manufacturer = request.manufacturer,
        android_version = request.android_version,
        app_version = request.app_version,
    )

    subscription = user_subscription_snapshot(
            user
        )

    return {
        "success": True,
        "user_id": user["id"],
        "subscription": subscription,
        "quotas": quota_snapshot(
            user,
            subscription,
        ),
    }


@router.get("/subscription/status")
async def get_subscription_status(
    installation_id: str,
    authorization: str | None = Header(default=None),
):
    verify_app_token(
        authorization
    )

    user = get_or_create_user(
        installation_id = installation_id,
    )

    subscription = user_subscription_snapshot(
            user
        )

    return {
        "success": True,
        "user_id": user["id"],
        "subscription": subscription,
        "quotas": quota_snapshot(
            user,
            subscription,
        ),
    }


@router.post("/subscription/usage/consume")
async def consume_usage(
    request: UsageConsumeRequest,
    authorization: str | None = Header(default=None),
):
    verify_app_token(
        authorization
    )

    if request.feature_key not in FREE_LIMITS:
        raise HTTPException(
            status_code=422,
            detail="ابزار موردنظر معتبر نیست.",
        )

    user = get_or_create_user(
        installation_id = request.installation_id,
    )

    subscription = user_subscription_snapshot(
            user
        )

    if subscription["blocked"]:
        raise HTTPException(
            status_code=403,
            detail="حساب کاربر مسدود شده است.",
        )

    if subscription["is_premium"]:
        return {
            "success": True,
            "allowed": True,
            "premium": True,
            "quota": {
                "used": 0,
                "limit": None,
                "remaining": None,
                "unlimited": True,
                "has_access": True,
            },
        }

    limit = FREE_LIMITS[
        request.feature_key
    ]

    period_key = usage_period_key(
        request.feature_key
    )

    now = isoformat(utc_now())

    with database() as connection:
        row = connection.execute(
            """
            SELECT used_count
            FROM usage_counters
            WHERE user_id = ?
              AND feature_key = ?
              AND period_key = ?
            """,
            (
                user["id"],
                request.feature_key,
                period_key,
            ),
        ).fetchone()

        used = int(
            row["used_count"]
        ) if row else 0

        if used >= limit:
            return {
                "success": True,
                "allowed": False,
                "premium": False,
                "quota": {
                    "used": used,
                    "limit": limit,
                    "remaining": 0,
                    "unlimited": False,
                    "has_access": False,
                },
                "message":
                    "سهمیه رایگان این ابزار تمام شده است.",
            }

        updated_used = used + 1

        connection.execute(
            """
            INSERT INTO usage_counters (
                user_id,
                feature_key,
                period_key,
                used_count,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(
                user_id,
                feature_key,
                period_key
            )
            DO UPDATE SET
                used_count = excluded.used_count,
                updated_at = excluded.updated_at
            """,
            (
                user["id"],
                request.feature_key,
                period_key,
                updated_used,
                now,
            ),
        )

    return {
        "success": True,
        "allowed": True,
        "premium": False,
        "quota": {
            "used": updated_used,
            "limit": limit,
            "remaining": max(
                limit - updated_used,
                0,
            ),
            "unlimited": False,
            "has_access":
                updated_used < limit,
        },
    }


@router.get("/subscription/notifications")
async def get_notifications(
    installation_id: str,
    authorization: str | None = Header(default=None),
):
    verify_app_token(
        authorization
    )

    user = get_or_create_user(
        installation_id = installation_id,
    )

    subscription = user_subscription_snapshot(
            user
        )

    audience = (
        "premium"
        if subscription["is_premium"]
        else "free"
    )

    now = isoformat(utc_now())

    with database() as connection:
        rows = connection.execute(
            """
            SELECT
                notifications.*,
                CASE
                    WHEN notification_reads.notification_id
                         IS NULL
                    THEN 0
                    ELSE 1
                END AS is_read
            FROM notifications
            LEFT JOIN notification_reads
              ON notification_reads.notification_id = notifications.id
             AND notification_reads.user_id = ?
            WHERE notifications.enabled = 1
              AND (
                    notifications.scheduled_at IS NULL
                    OR notifications.scheduled_at <= ?
                  )
              AND notifications.audience
                    IN ('all', ?)
            ORDER BY
                notifications.created_at DESC
            LIMIT 100
            """,
            (
                user["id"],
                now,
                audience,
            ),
        ).fetchall()

    return {
        "success": True,
        "items": [
            dict(row)
            for row in rows
        ],
    }


@router.post("/subscription/notifications/read")
async def mark_notification_read(
    request: MarkNotificationReadRequest,
    authorization: str | None = Header(default=None),
):
    verify_app_token(
        authorization
    )

    user = get_or_create_user(
        installation_id = request.installation_id,
    )

    with database() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO
                notification_reads (
                    notification_id,
                    user_id,
                    read_at
                )
            VALUES (?, ?, ?)
            """,
            (
                request.notification_id,
                user["id"],
                isoformat(utc_now()),
            ),
        )

    return {
        "success": True,
    }


@router.post("/subscription/admin/campaigns")
async def admin_create_campaign(
    request: CampaignCreateRequest,
    authorization: str | None = Header(default=None),
):
    verify_admin_token(
        authorization
    )

    starts_at = parse_datetime(
        request.starts_at
    )

    ends_at = parse_datetime(
        request.ends_at
    )

    if ends_at <= starts_at:
        raise HTTPException(
            status_code=422,
            detail="تاریخ پایان باید بعد از تاریخ شروع باشد.",
        )

    invalid_features = [
        feature
        for feature in request.feature_keys
        if feature not in FREE_LIMITS
    ]

    if invalid_features:
        raise HTTPException(
            status_code=422,
            detail=(
                "ابزارهای نامعتبر: "
                + ", ".join(
                    invalid_features
                )
            ),
        )

    campaign_id = str(
        uuid.uuid4()
    )

    now = isoformat(
        utc_now()
    )

    with database() as connection:
        connection.execute(
            """
            INSERT INTO campaigns (
                id,
                title,
                description,
                audience,
                starts_at,
                ends_at,
                premium_access,
                enabled,
                badge_text,
                button_text,
                action_type,
                action_value,
                image_url,
                priority,
                dismissible,
                show_once,
                campaign_type,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                campaign_id,
                request.title,
                request.description,
                request.audience,
                isoformat(starts_at),
                isoformat(ends_at),
                int(request.premium_access),
                int(request.enabled),
                request.badge_text,
                request.button_text,
                request.action_type,
                request.action_value,
                request.image_url,
                request.priority,
                int(request.dismissible),
                int(request.show_once),
                request.campaign_type,
                now,
                now,
            ),
        )

        for feature_key in request.feature_keys:
            connection.execute(
                """
                INSERT INTO campaign_features (
                    campaign_id,
                    feature_key
                )
                VALUES (?, ?)
                """,
                (
                    campaign_id,
                    feature_key,
                ),
            )

    return {
        "success": True,
        "campaign_id": campaign_id,
        "message": "کمپین رایگان ساخته شد.",
    }


@router.get("/subscription/admin/campaigns")
async def admin_list_campaigns(
    authorization: str | None = Header(default=None),
):
    verify_admin_token(
        authorization
    )

    with database() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM campaigns
            ORDER BY created_at DESC
            """
        ).fetchall()

    return {
        "success": True,
        "items": [
            dict(row)
            for row in rows
        ],
    }


@router.post(
    "/subscription/admin/campaigns/{campaign_id}/toggle"
)
async def admin_toggle_campaign(
    campaign_id: str,
    authorization: str | None = Header(default=None),
):
    verify_admin_token(
        authorization
    )

    now = isoformat(
        utc_now()
    )

    with database() as connection:
        row = connection.execute(
            """
            SELECT enabled
            FROM campaigns
            WHERE id = ?
            """,
            (campaign_id,),
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="کمپین پیدا نشد.",
            )

        enabled = 0 if row["enabled"] else 1

        connection.execute(
            """
            UPDATE campaigns
            SET enabled = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                enabled,
                now,
                campaign_id,
            ),
        )

    return {
        "success": True,
        "enabled": bool(enabled),
    }


@router.post("/subscription/admin/subscriptions/activate")
async def admin_activate_subscription(
    request: ManualSubscriptionRequest,
    authorization: str | None = Header(default=None),
):
    verify_admin_token(
        authorization
    )

    user = get_or_create_user(
        installation_id = request.installation_id,
    )

    starts_at = utc_now()

    expires_at = (
        starts_at +
        timedelta(
            days=request.days
        )
        if request.days
        else None
    )

    now = isoformat(
        utc_now()
    )

    subscription_id = str(
        uuid.uuid4()
    )

    with database() as connection:
        connection.execute(
            """
            UPDATE subscriptions
            SET is_active = 0,
                updated_at = ?
            WHERE user_id = ?
              AND is_manual = 1
            """,
            (
                now,
                user["id"],
            ),
        )

        connection.execute(
            """
            INSERT INTO subscriptions (
                id,
                user_id,
                plan_key,
                source,
                starts_at,
                expires_at,
                is_active,
                is_manual,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
            """,
            (
                subscription_id,
                user["id"],
                request.plan_key,
                "admin",
                isoformat(starts_at),
                isoformat(expires_at),
                now,
                now,
            ),
        )

    return {
        "success": True,
        "subscription_id":
            subscription_id,
        "expires_at":
            isoformat(expires_at),
        "message":
            "اشتراک مدیریتی فعال شد.",
    }


@router.post(
    "/subscription/admin/subscriptions/{installation_id}/deactivate"
)
async def admin_deactivate_subscription(
    installation_id: str,
    authorization: str | None = Header(default=None),
):
    verify_admin_token(
        authorization
    )

    user = get_or_create_user(
        installation_id = installation_id,
    )

    with database() as connection:
        connection.execute(
            """
            UPDATE subscriptions
            SET is_active = 0,
                updated_at = ?
            WHERE user_id = ?
            """,
            (
                isoformat(utc_now()),
                user["id"],
            ),
        )

    return {
        "success": True,
        "message":
            "اشتراک کاربر غیرفعال شد.",
    }


@router.post("/subscription/admin/notifications")
async def admin_create_notification(
    request: NotificationCreateRequest,
    authorization: str | None = Header(default=None),
):
    verify_admin_token(
        authorization
    )

    scheduled_at = parse_datetime(
        request.scheduled_at
    )

    notification_id = str(
        uuid.uuid4()
    )

    now = isoformat(
        utc_now()
    )

    with database() as connection:
        connection.execute(
            """
            INSERT INTO notifications (
                id,
                title,
                body,
                audience,
                target_route,
                image_url,
                scheduled_at,
                sent_at,
                enabled,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 1, ?)
            """,
            (
                notification_id,
                request.title,
                request.body,
                request.audience,
                request.target_route,
                request.image_url,
                isoformat(scheduled_at),
                now,
            ),
        )

    return {
        "success": True,
        "notification_id":
            notification_id,
        "message":
            "اعلان داخل اپ ثبت شد.",
    }


@router.get("/subscription/admin/users")
async def admin_list_users(
    search: str = "",
    limit: int = 100,
    authorization: str | None = Header(default=None),
):
    verify_admin_token(
        authorization
    )

    safe_limit = max(
        1,
        min(limit, 500),
    )

    like = f"%{search.strip()}%"

    with database() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM users
            WHERE installation_id LIKE ?
               OR COALESCE(display_name, '') LIKE ?
               OR COALESCE(phone, '') LIKE ?
               OR COALESCE(email, '') LIKE ?
            ORDER BY last_seen_at DESC
            LIMIT ?
            """,
            (
                like,
                like,
                like,
                like,
                safe_limit,
            ),
        ).fetchall()

    items = []

    for row in rows:
        subscription = user_subscription_snapshot(
                row
            )

        items.append(
            {
                **dict(row),
                "subscription":
                    subscription,
            }
        )

    return {
        "success": True,
        "items": items,
    }


class CampaignEventRequest(BaseModel):
    campaign_id: str = Field(min_length=1, max_length=120)
    installation_id: str | None = Field(default=None, max_length=200)
    event_type: Literal["impression", "click", "dismiss"]


class UsageEventRequest(BaseModel):
    installation_id: str = Field(min_length=8, max_length=200)
    feature_key: str = Field(min_length=1, max_length=120)
    event_type: Literal["open", "success", "error", "share", "save"] = "open"


def _setting(connection: sqlite3.Connection, key: str, default: str = "") -> str:
    row = connection.execute(
        "SELECT value FROM app_settings WHERE key = ?",
        (key,),
    ).fetchone()
    return str(row["value"]) if row else default


@router.get("/app/campaigns/active")
async def app_active_campaigns(
    installation_id: str | None = None,
    authorization: str | None = Header(default=None),
):
    verify_app_token(authorization)
    now = isoformat(utc_now())
    audience = "free"
    if installation_id:
        user = get_or_create_user(installation_id=installation_id)
        subscription = user_subscription_snapshot(user)
        audience = "premium" if subscription["is_premium"] else "free"

    with database() as connection:
        rows = connection.execute(
            """
            SELECT c.*,
                   COALESCE(SUM(CASE WHEN e.event_type='impression' THEN 1 ELSE 0 END),0) AS impressions,
                   COALESCE(SUM(CASE WHEN e.event_type='click' THEN 1 ELSE 0 END),0) AS clicks
            FROM campaigns c
            LEFT JOIN campaign_events e ON e.campaign_id = c.id
            WHERE c.enabled = 1
              AND c.starts_at <= ?
              AND c.ends_at > ?
              AND c.audience IN ('all', ?)
            GROUP BY c.id
            ORDER BY c.priority DESC, c.created_at DESC
            LIMIT 20
            """,
            (now, now, audience),
        ).fetchall()

    campaigns = []
    for row in rows:
        item = dict(row)
        item["message"] = item.get("description") or ""
        item["dismissible"] = bool(item.get("dismissible", 1))
        item["show_once"] = bool(item.get("show_once", 0))
        item["enabled"] = bool(item.get("enabled", 1))
        campaigns.append(item)

    return {"success": True, "campaigns": campaigns}


@router.post("/app/campaigns/event")
async def app_campaign_event(
    request: CampaignEventRequest,
    authorization: str | None = Header(default=None),
):
    verify_app_token(authorization)
    with database() as connection:
        exists = connection.execute(
            "SELECT id FROM campaigns WHERE id = ?",
            (request.campaign_id,),
        ).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="کمپین پیدا نشد.")
        connection.execute(
            "INSERT INTO campaign_events(id, campaign_id, installation_id, event_type, created_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), request.campaign_id, request.installation_id, request.event_type, isoformat(utc_now())),
        )
    return {"success": True}


@router.get("/app/config")
async def app_config(
    authorization: str | None = Header(default=None),
):
    verify_app_token(authorization)
    with database() as connection:
        settings = {
            row["key"]: row["value"]
            for row in connection.execute("SELECT key, value FROM app_settings").fetchall()
        }
        flags = []
        for row in connection.execute("SELECT * FROM feature_flags ORDER BY title").fetchall():
            item = dict(row)
            item["enabled"] = bool(item["enabled"])
            item["premium_only"] = bool(item["premium_only"])
            flags.append(item)
    return {
        "success": True,
        "beta": {
            "enabled": settings.get("beta_enabled", "1") == "1",
            "title": settings.get("beta_title", "نسخه آزمایشی رایگان"),
        },
        "version": {
            "minimum_version_code": int(settings.get("minimum_version_code", "1")),
            "latest_version_code": int(settings.get("latest_version_code", "1")),
            "force_update": settings.get("force_update", "0") == "1",
            "message": settings.get("update_message", ""),
        },
        "feature_flags": flags,
    }


@router.post("/app/usage/event")
async def app_usage_event(
    request: UsageEventRequest,
    authorization: str | None = Header(default=None),
):
    verify_app_token(authorization)
    get_or_create_user(installation_id=request.installation_id)
    with database() as connection:
        connection.execute(
            "INSERT INTO usage_events(id, installation_id, feature_key, event_type, created_at) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), request.installation_id, request.feature_key, request.event_type, isoformat(utc_now())),
        )
    return {"success": True}


@router.get("/admin/analytics")
async def admin_analytics(
    days: int = 30,
    authorization: str | None = Header(default=None),
):
    verify_admin_token(authorization)
    safe_days = max(1, min(days, 365))
    since = isoformat(utc_now() - timedelta(days=safe_days))
    with database() as connection:
        total_users = connection.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        active_users = connection.execute("SELECT COUNT(*) AS n FROM users WHERE last_seen_at >= ?", (since,)).fetchone()["n"]
        events = [dict(r) for r in connection.execute(
            "SELECT feature_key, event_type, COUNT(*) AS count FROM usage_events WHERE created_at >= ? GROUP BY feature_key, event_type ORDER BY count DESC",
            (since,),
        ).fetchall()]
        campaigns = [dict(r) for r in connection.execute(
            """SELECT c.id, c.title,
                      SUM(CASE WHEN e.event_type='impression' THEN 1 ELSE 0 END) AS impressions,
                      SUM(CASE WHEN e.event_type='click' THEN 1 ELSE 0 END) AS clicks,
                      SUM(CASE WHEN e.event_type='dismiss' THEN 1 ELSE 0 END) AS dismisses
               FROM campaigns c LEFT JOIN campaign_events e ON e.campaign_id=c.id
               GROUP BY c.id ORDER BY impressions DESC"""
        ).fetchall()]
    return {"success": True, "days": safe_days, "total_users": total_users, "active_users": active_users, "usage": events, "campaigns": campaigns}


class AdminPaymentGatewayUpdateRequest(BaseModel):
    zarinpal_enabled: bool
    bazaar_enabled: bool


@router.get(
    "/subscription/admin/payment-gateways",
)
async def admin_get_payment_gateways(
    authorization: str | None = Header(
        default=None,
    ),
):
    verify_admin_token(authorization)

    from payment_gateway_settings import (
        gateway_enabled,
    )

    zarinpal_enabled = gateway_enabled(
        "zarinpal_enabled"
    )

    bazaar_enabled = gateway_enabled(
        "bazaar_payment_enabled"
    )

    return {
        "success": True,
        "zarinpal_enabled": zarinpal_enabled,
        "bazaar_enabled": bazaar_enabled,
    }


@router.post(
    "/subscription/admin/payment-gateways",
)
async def admin_update_payment_gateways(
    request: AdminPaymentGatewayUpdateRequest,
    authorization: str | None = Header(
        default=None,
    ),
):
    verify_admin_token(authorization)

    from payment_gateway_settings import (
        set_setting,
    )

    set_setting(
        "zarinpal_enabled",
        "1" if request.zarinpal_enabled else "0",
    )

    set_setting(
        "bazaar_payment_enabled",
        "1" if request.bazaar_enabled else "0",
    )

    return {
        "success": True,
        "zarinpal_enabled":
            request.zarinpal_enabled,
        "bazaar_enabled":
            request.bazaar_enabled,
        "message":
            "تنظیمات درگاه‌های پرداخت ذخیره شد.",
    }

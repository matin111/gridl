from __future__ import annotations

import json
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter,
    File,
    Header,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/v1/support",
    tags=["support"],
)

BASE_DIR = Path("/root/aistudio-api")
USERS_FILE = BASE_DIR / "data/users.json"
DATABASE_PATH = BASE_DIR / "support.db"
ATTACHMENTS_DIR = (
    BASE_DIR / "generated/support"
)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024


def utc_now_text() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


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


def table_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> set[str]:
    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return {
        str(row["name"])
        for row in rows
    }


def initialize_database() -> None:
    ATTACHMENTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with database() as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;

            CREATE TABLE IF NOT EXISTS support_tickets (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                user_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                priority TEXT NOT NULL DEFAULT 'normal',
                user_unread_count INTEGER NOT NULL DEFAULT 0,
                admin_unread_count INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_support_tickets_user
            ON support_tickets(user_id, updated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_support_tickets_status
            ON support_tickets(status, updated_at DESC);

            CREATE TABLE IF NOT EXISTS support_messages (
                id TEXT PRIMARY KEY,
                ticket_id TEXT NOT NULL,
                sender_type TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                message TEXT NOT NULL,
                attachment_url TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(ticket_id)
                    REFERENCES support_tickets(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_support_messages_ticket
            ON support_messages(ticket_id, created_at ASC);
            """
        )

        message_columns = table_columns(
            connection,
            "support_messages",
        )

        if "attachment_url" not in message_columns:
            connection.execute(
                """
                ALTER TABLE support_messages
                ADD COLUMN attachment_url TEXT
                """
            )


initialize_database()


class TicketCreateRequest(BaseModel):
    subject: str = Field(
        min_length=3,
        max_length=120,
    )
    category: str = Field(
        default="general",
        max_length=40,
    )
    message: str = Field(
        min_length=2,
        max_length=5000,
    )
    attachment_url: str | None = Field(
        default=None,
        max_length=1000,
    )


class TicketMessageRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=5000,
    )
    attachment_url: str | None = Field(
        default=None,
        max_length=1000,
    )


def load_users() -> list[dict]:
    if not USERS_FILE.exists():
        return []

    try:
        value = json.loads(
            USERS_FILE.read_text(
                encoding="utf-8"
            )
        )
        return (
            value
            if isinstance(value, list)
            else []
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return []


def bearer_token(
    authorization: str | None,
) -> str:
    if not authorization:
        return ""

    scheme, _, token = (
        authorization
        .strip()
        .partition(" ")
    )

    if scheme.lower() != "bearer":
        return ""

    return token.strip()


def authenticated_user(
    authorization: str | None,
) -> dict:
    token = bearer_token(
        authorization
    )

    if not token:
        raise HTTPException(
            status_code=401,
            detail=(
                "توکن ورود ارسال نشده است"
            ),
        )

    for user in load_users():
        saved_token = str(
            user.get("token", "")
        )

        if (
            saved_token
            and secrets.compare_digest(
                saved_token,
                token,
            )
        ):
            return user

    raise HTTPException(
        status_code=401,
        detail="نشست کاربری معتبر نیست",
    )


def ticket_to_dict(
    ticket: sqlite3.Row,
) -> dict:
    return {
        "id": ticket["id"],
        "subject": ticket["subject"],
        "category": ticket["category"],
        "status": ticket["status"],
        "priority": ticket["priority"],
        "user_unread_count":
            int(
                ticket[
                    "user_unread_count"
                ]
            ),
        "created_at":
            ticket["created_at"],
        "updated_at":
            ticket["updated_at"],
    }


def message_to_dict(
    message: sqlite3.Row,
) -> dict:
    return {
        "id": message["id"],
        "sender_type":
            message["sender_type"],
        "message": message["message"],
        "attachment_url":
            message["attachment_url"],
        "created_at":
            message["created_at"],
    }


@router.post("/attachments")
async def upload_attachment(
    authorization: str | None =
        Header(default=None),
    image: UploadFile =
        File(...),
):
    authenticated_user(
        authorization
    )

    content_type = (
        image.content_type or ""
    ).lower()

    extension = (
        ALLOWED_IMAGE_TYPES.get(
            content_type
        )
    )

    if not extension:
        raise HTTPException(
            status_code=415,
            detail=(
                "فقط تصویر JPG، PNG یا WEBP "
                "مجاز است"
            ),
        )

    content = await image.read(
        MAX_ATTACHMENT_BYTES + 1
    )

    if not content:
        raise HTTPException(
            status_code=422,
            detail="فایل تصویر خالی است",
        )

    if (
        len(content)
        > MAX_ATTACHMENT_BYTES
    ):
        raise HTTPException(
            status_code=413,
            detail=(
                "حجم تصویر باید کمتر از "
                "۸ مگابایت باشد"
            ),
        )

    filename = (
        f"{uuid.uuid4().hex}"
        f"{extension}"
    )
    file_path = (
        ATTACHMENTS_DIR / filename
    )

    file_path.write_bytes(content)

    return {
        "success": True,
        "attachment_url": (
            f"/generated/support/"
            f"{filename}"
        ),
        "message":
            "تصویر با موفقیت بارگذاری شد",
    }


@router.post("/tickets")
async def create_ticket(
    request: TicketCreateRequest,
    authorization: str | None =
        Header(default=None),
):
    user = authenticated_user(
        authorization
    )
    now = utc_now_text()
    ticket_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())

    with database() as connection:
        connection.execute(
            """
            INSERT INTO support_tickets (
                id,
                user_id,
                user_name,
                user_email,
                subject,
                category,
                status,
                priority,
                user_unread_count,
                admin_unread_count,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'open', 'normal', 0, 1, ?, ?)
            """,
            (
                ticket_id,
                str(user.get("id", "")),
                str(user.get("name", "")),
                str(user.get("email", "")),
                request.subject.strip(),
                (
                    request.category.strip()
                    or "general"
                ),
                now,
                now,
            ),
        )

        connection.execute(
            """
            INSERT INTO support_messages (
                id,
                ticket_id,
                sender_type,
                sender_id,
                message,
                attachment_url,
                created_at
            )
            VALUES (?, ?, 'user', ?, ?, ?, ?)
            """,
            (
                message_id,
                ticket_id,
                str(user.get("id", "")),
                request.message.strip(),
                request.attachment_url,
                now,
            ),
        )

    return {
        "success": True,
        "ticket_id": ticket_id,
        "message":
            "درخواست پشتیبانی ثبت شد",
    }


@router.get("/tickets")
async def list_tickets(
    authorization: str | None =
        Header(default=None),
):
    user = authenticated_user(
        authorization
    )

    with database() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM support_tickets
            WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT 100
            """,
            (
                str(user.get("id", "")),
            ),
        ).fetchall()

    return {
        "success": True,
        "tickets": [
            ticket_to_dict(row)
            for row in rows
        ],
    }


@router.get(
    "/tickets/{ticket_id}"
)
async def ticket_details(
    ticket_id: str,
    authorization: str | None =
        Header(default=None),
):
    user = authenticated_user(
        authorization
    )
    user_id = str(
        user.get("id", "")
    )

    with database() as connection:
        ticket = connection.execute(
            """
            SELECT *
            FROM support_tickets
            WHERE id = ?
              AND user_id = ?
            """,
            (
                ticket_id,
                user_id,
            ),
        ).fetchone()

        if not ticket:
            raise HTTPException(
                status_code=404,
                detail=(
                    "درخواست پشتیبانی "
                    "پیدا نشد"
                ),
            )

        messages = connection.execute(
            """
            SELECT *
            FROM support_messages
            WHERE ticket_id = ?
            ORDER BY created_at ASC
            """,
            (ticket_id,),
        ).fetchall()

        connection.execute(
            """
            UPDATE support_tickets
            SET user_unread_count = 0
            WHERE id = ?
            """,
            (ticket_id,),
        )

    return {
        "success": True,
        "ticket":
            ticket_to_dict(ticket),
        "messages": [
            message_to_dict(row)
            for row in messages
        ],
    }


@router.post(
    "/tickets/{ticket_id}/messages"
)
async def send_message(
    ticket_id: str,
    request: TicketMessageRequest,
    authorization: str | None =
        Header(default=None),
):
    user = authenticated_user(
        authorization
    )
    user_id = str(
        user.get("id", "")
    )
    now = utc_now_text()

    with database() as connection:
        ticket = connection.execute(
            """
            SELECT id, status
            FROM support_tickets
            WHERE id = ?
              AND user_id = ?
            """,
            (
                ticket_id,
                user_id,
            ),
        ).fetchone()

        if not ticket:
            raise HTTPException(
                status_code=404,
                detail=(
                    "درخواست پشتیبانی "
                    "پیدا نشد"
                ),
            )

        if ticket["status"] == "closed":
            raise HTTPException(
                status_code=409,
                detail=(
                    "این درخواست بسته "
                    "شده است"
                ),
            )

        connection.execute(
            """
            INSERT INTO support_messages (
                id,
                ticket_id,
                sender_type,
                sender_id,
                message,
                attachment_url,
                created_at
            )
            VALUES (?, ?, 'user', ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                ticket_id,
                user_id,
                request.message.strip(),
                request.attachment_url,
                now,
            ),
        )

        connection.execute(
            """
            UPDATE support_tickets
            SET status = 'open',
                admin_unread_count =
                    admin_unread_count + 1,
                updated_at = ?
            WHERE id = ?
            """,
            (
                now,
                ticket_id,
            ),
        )

    return {
        "success": True,
        "message": "پیام ارسال شد",
    }


@router.post(
    "/tickets/{ticket_id}/close"
)
async def close_ticket(
    ticket_id: str,
    authorization: str | None =
        Header(default=None),
):
    user = authenticated_user(
        authorization
    )

    with database() as connection:
        cursor = connection.execute(
            """
            UPDATE support_tickets
            SET status = 'closed',
                updated_at = ?
            WHERE id = ?
              AND user_id = ?
            """,
            (
                utc_now_text(),
                ticket_id,
                str(user.get("id", "")),
            ),
        )

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail=(
                    "درخواست پشتیبانی "
                    "پیدا نشد"
                ),
            )

    return {
        "success": True,
        "message": "درخواست بسته شد",
    }

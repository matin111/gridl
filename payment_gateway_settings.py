from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

DATABASE_PATH = Path("/root/aistudio-api/subscription.db")

router = APIRouter(
    prefix="/v1/payment-gateways",
    tags=["payment-gateways"],
)


DEFAULT_SETTINGS = {
    "zarinpal_enabled": "0",
    "bazaar_payment_enabled": "1",
}


def database() -> sqlite3.Connection:
    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )
    connection.row_factory = sqlite3.Row
    return connection


def ensure_settings() -> None:
    connection = database()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            INSERT OR IGNORE INTO app_settings(
                key,
                value,
                updated_at
            )
            VALUES(
                'zarinpal_enabled',
                '0',
                datetime('now')
            )
            """
        )

        connection.execute(
            """
            INSERT OR IGNORE INTO app_settings(
                key,
                value,
                updated_at
            )
            VALUES(
                'bazaar_payment_enabled',
                '1',
                datetime('now')
            )
            """
        )

        connection.commit()

    finally:
        connection.close()


def get_setting(
    key: str,
    default: str = "",
) -> str:
    ensure_settings()

    connection = database()

    try:
        row = connection.execute(
            """
            SELECT value
            FROM app_settings
            WHERE key = ?
            """,
            (key,),
        ).fetchone()

        return (
            str(row["value"])
            if row is not None
            else default
        )

    finally:
        connection.close()


def set_setting(
    key: str,
    value: str,
) -> None:
    ensure_settings()

    connection = database()

    try:
        connection.execute(
            """
            INSERT INTO app_settings(
                key,
                value,
                updated_at
            )
            VALUES(
                ?,
                ?,
                datetime('now')
            )
            ON CONFLICT(key)
            DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (
                key,
                value,
            ),
        )

        connection.commit()

    finally:
        connection.close()


def gateway_enabled(key: str) -> bool:
    return get_setting(
        key,
        DEFAULT_SETTINGS.get(key, "0"),
    ) == "1"


def require_gateway_enabled(
    key: str,
    title: str,
) -> None:
    if not gateway_enabled(key):
        raise HTTPException(
            status_code=503,
            detail=(
                f"پرداخت از طریق {title} "
                "در حال حاضر غیرفعال است."
            ),
        )


class PaymentGatewayConfigResponse(BaseModel):
    success: bool = True
    zarinpal_enabled: bool
    bazaar_enabled: bool
    any_payment_enabled: bool
    message: str = ""


@router.get(
    "",
    response_model=PaymentGatewayConfigResponse,
)
async def public_payment_gateway_settings():
    zarinpal_enabled = gateway_enabled(
        "zarinpal_enabled"
    )

    bazaar_enabled = gateway_enabled(
        "bazaar_payment_enabled"
    )

    any_payment_enabled = (
        zarinpal_enabled
        or bazaar_enabled
    )

    message = (
        ""
        if any_payment_enabled
        else "خرید اشتراک موقتاً غیرفعال است."
    )

    return PaymentGatewayConfigResponse(
        zarinpal_enabled=zarinpal_enabled,
        bazaar_enabled=bazaar_enabled,
        any_payment_enabled=any_payment_enabled,
        message=message,
    )

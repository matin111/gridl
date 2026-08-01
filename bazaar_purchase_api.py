from __future__ import annotations

import base64
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from payment_gateway_settings import require_gateway_enabled

from subscription_admin_api import (
    database,
    get_or_create_user,
    isoformat,
    utc_now,
    verify_app_token,
)


router = APIRouter(
    prefix="/v1/subscription/bazaar",
    tags=["bazaar-subscription"],
)


ALLOWED_PRODUCTS = {
    "aistudio_pro_monthly": 35,
    "aistudio_pro_2_months": 65,
    "aistudio_pro_3_months": 95,
    "aistudio_pro_6_months": 185,
    "aistudio_pro_yearly": 370,
}


EXPECTED_PACKAGE_NAME = os.getenv(
    "ANDROID_APPLICATION_ID",
    "com.aistudiopro.app",
).strip()


def bazaar_public_key() -> str:
    return os.getenv(
        "BAZAAR_RSA_PUBLIC_KEY",
        "",
    ).strip()


def verify_signature(
    original_json: str,
    data_signature: str,
) -> bool:
    public_key_value = bazaar_public_key()

    if not public_key_value:
        raise HTTPException(
            status_code=500,
            detail="BAZAAR_RSA_PUBLIC_KEY روی سرور تنظیم نشده است.",
        )

    normalized_key = (
        public_key_value
        .replace(
            "-----BEGIN PUBLIC KEY-----",
            "",
        )
        .replace(
            "-----END PUBLIC KEY-----",
            "",
        )
        .replace("\n", "")
        .replace("\r", "")
        .strip()
    )

    try:
        der_key = base64.b64decode(
            normalized_key,
            validate=True,
        )

        public_key = serialization.load_der_public_key(
            der_key
        )

        signature_bytes = base64.b64decode(
            data_signature,
            validate=True,
        )

        public_key.verify(
            signature_bytes,
            original_json.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA1(),
        )

        return True

    except Exception:
        return False


def ensure_purchase_columns() -> None:
    with database() as connection:
        existing_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(subscriptions)"
            ).fetchall()
        }

        additions = {
            "order_id": "TEXT",
            "original_json": "TEXT",
            "data_signature": "TEXT",
            "purchase_time": "INTEGER",
            "package_name": "TEXT",
            "payload": "TEXT",
            "verified_at": "TEXT",
        }

        for column_name, column_type in additions.items():
            if column_name not in existing_columns:
                connection.execute(
                    f"""
                    ALTER TABLE subscriptions
                    ADD COLUMN {column_name} {column_type}
                    """
                )

        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_subscriptions_purchase_token
            ON subscriptions(purchase_token)
            WHERE purchase_token IS NOT NULL
            """
        )


ensure_purchase_columns()


class BazaarPurchaseVerifyRequest(BaseModel):
    installation_id: str = Field(
        min_length=8,
        max_length=200,
    )

    product_id: str = Field(
        min_length=2,
        max_length=200,
    )

    purchase_token: str = Field(
        min_length=5,
        max_length=2000,
    )

    order_id: str = Field(
        default="",
        max_length=500,
    )

    package_name: str = Field(
        min_length=3,
        max_length=300,
    )

    payload: str = Field(
        default="",
        max_length=2000,
    )

    purchase_time: int = Field(
        ge=0,
    )

    original_json: str = Field(
        min_length=2,
        max_length=20000,
    )

    data_signature: str = Field(
        min_length=2,
        max_length=10000,
    )


class BazaarRestoreRequest(BaseModel):
    installation_id: str = Field(
        min_length=8,
        max_length=200,
    )

    active_purchase_tokens: list[str] = Field(
        default_factory=list,
        max_length=20,
    )


@router.post("/verify")
async def verify_bazaar_purchase(
    request: BazaarPurchaseVerifyRequest,
    authorization: str | None =
        Header(default=None),
):
    require_gateway_enabled(
        "bazaar_payment_enabled",
        "بازار",
    )

    verify_app_token(
        authorization
    )

    if request.product_id not in ALLOWED_PRODUCTS:
        raise HTTPException(
            status_code=422,
            detail="شناسه محصول اشتراک معتبر نیست.",
        )

    if request.package_name != EXPECTED_PACKAGE_NAME:
        raise HTTPException(
            status_code=422,
            detail="نام پکیج خرید با برنامه مطابقت ندارد.",
        )

    if not verify_signature(
        request.original_json,
        request.data_signature,
    ):
        raise HTTPException(
            status_code=400,
            detail="امضای خرید بازار معتبر نیست.",
        )

    try:
        purchase_json = json.loads(
            request.original_json
        )
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=422,
            detail="اطلاعات اصلی خرید معتبر نیست.",
        ) from error

    json_product_id = str(
        purchase_json.get("productId")
        or purchase_json.get("sku")
        or ""
    )

    json_purchase_token = str(
        purchase_json.get("purchaseToken")
        or purchase_json.get("token")
        or ""
    )

    json_package_name = str(
        purchase_json.get("packageName")
        or ""
    )

    if json_product_id != request.product_id:
        raise HTTPException(
            status_code=422,
            detail="شناسه محصول داخل امضای خرید متفاوت است.",
        )

    if json_purchase_token != request.purchase_token:
        raise HTTPException(
            status_code=422,
            detail="توکن داخل امضای خرید متفاوت است.",
        )

    if json_package_name != request.package_name:
        raise HTTPException(
            status_code=422,
            detail="پکیج داخل امضای خرید متفاوت است.",
        )

    user = get_or_create_user(
        installation_id =
            request.installation_id,
    )

    now = utc_now()

    purchase_datetime = datetime.fromtimestamp(
        request.purchase_time / 1000,
        tz=timezone.utc,
    )

    if purchase_datetime > now + timedelta(minutes=10):
        raise HTTPException(
            status_code=422,
            detail="زمان خرید معتبر نیست.",
        )

    provisional_expires_at = max(
        purchase_datetime,
        now,
    ) + timedelta(
        days=ALLOWED_PRODUCTS[
            request.product_id
        ]
    )

    subscription_id = str(
        uuid.uuid4()
    )

    with database() as connection:
        existing = connection.execute(
            """
            SELECT id
            FROM subscriptions
            WHERE purchase_token = ?
            """,
            (
                request.purchase_token,
            ),
        ).fetchone()

        connection.execute(
            """
            UPDATE subscriptions
            SET is_active = 0,
                updated_at = ?
            WHERE user_id = ?
              AND source = 'bazaar'
              AND purchase_token <> ?
            """,
            (
                isoformat(now),
                user["id"],
                request.purchase_token,
            ),
        )

        if existing:
            subscription_id = existing["id"]

            connection.execute(
                """
                UPDATE subscriptions
                SET user_id = ?,
                    plan_key = ?,
                    source = 'bazaar',
                    starts_at = ?,
                    expires_at = ?,
                    is_active = 1,
                    is_manual = 0,
                    product_id = ?,
                    order_id = ?,
                    original_json = ?,
                    data_signature = ?,
                    purchase_time = ?,
                    package_name = ?,
                    payload = ?,
                    verified_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    user["id"],
                    request.product_id,
                    isoformat(purchase_datetime),
                    isoformat(provisional_expires_at),
                    request.product_id,
                    request.order_id,
                    request.original_json,
                    request.data_signature,
                    request.purchase_time,
                    request.package_name,
                    request.payload,
                    isoformat(now),
                    isoformat(now),
                    subscription_id,
                ),
            )

        else:
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
                    purchase_token,
                    product_id,
                    order_id,
                    original_json,
                    data_signature,
                    purchase_time,
                    package_name,
                    payload,
                    verified_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?, ?, ?, 'bazaar', ?, ?, 1, 0,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    subscription_id,
                    user["id"],
                    request.product_id,
                    isoformat(purchase_datetime),
                    isoformat(provisional_expires_at),
                    request.purchase_token,
                    request.product_id,
                    request.order_id,
                    request.original_json,
                    request.data_signature,
                    request.purchase_time,
                    request.package_name,
                    request.payload,
                    isoformat(now),
                    isoformat(now),
                    isoformat(now),
                ),
            )

    return {
        "success": True,
        "verified": True,
        "subscription": {
            "plan_key":
                request.product_id,
            "source": "bazaar",
            "starts_at":
                isoformat(purchase_datetime),
            "expires_at":
                isoformat(provisional_expires_at),
            "purchase_token":
                request.purchase_token,
        },
        "message":
            "خرید بازار در سرور تأیید و اشتراک فعال شد.",
    }


@router.post("/restore")
async def restore_bazaar_purchases(
    request: BazaarRestoreRequest,
    authorization: str | None =
        Header(default=None),
):
    require_gateway_enabled(
        "bazaar_payment_enabled",
        "بازار",
    )

    verify_app_token(
        authorization
    )

    user = get_or_create_user(
        installation_id =
            request.installation_id,
    )

    active_tokens = {
        token.strip()
        for token in
            request.active_purchase_tokens
        if token.strip()
    }

    now = isoformat(
        utc_now()
    )

    with database() as connection:
        subscriptions = connection.execute(
            """
            SELECT id, purchase_token
            FROM subscriptions
            WHERE user_id = ?
              AND source = 'bazaar'
              AND is_active = 1
            """,
            (
                user["id"],
            ),
        ).fetchall()

        deactivated = 0

        for item in subscriptions:
            if item["purchase_token"] not in active_tokens:
                connection.execute(
                    """
                    UPDATE subscriptions
                    SET is_active = 0,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        now,
                        item["id"],
                    ),
                )

                deactivated += 1

    return {
        "success": True,
        "deactivated": deactivated,
    }

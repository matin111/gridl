from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import httpx


DATABASE_PATH = Path("/root/aistudio-api/subscription.db")

REQUEST_URL = "https://api.zarinpal.com/pg/v4/payment/request.json"
VERIFY_URL = "https://api.zarinpal.com/pg/v4/payment/verify.json"
START_PAY_URL = "https://www.zarinpal.com/pg/StartPay/"

DEFAULT_CALLBACK_URL = "https://ap.movifilm.sbs/payment/verify"


class ZarinpalError(RuntimeError):
    pass


def _database_settings() -> dict[str, str]:
    result = {
        "zarinpal_enabled": "0",
        "zarinpal_merchant_id": "",
        "zarinpal_callback_url": DEFAULT_CALLBACK_URL,
    }

    try:
        connection = sqlite3.connect(
            DATABASE_PATH,
            timeout=30,
        )
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT key, value
            FROM app_settings
            WHERE key IN (
                'zarinpal_enabled',
                'zarinpal_merchant_id',
                'zarinpal_callback_url'
            )
            """
        ).fetchall()

        connection.close()

        for row in rows:
            result[str(row["key"])] = str(
                row["value"] or ""
            )

    except Exception:
        pass

    return result


def _gateway_config() -> dict[str, str]:
    settings = _database_settings()

    merchant_id = settings[
        "zarinpal_merchant_id"
    ].strip()

    callback_url = (
        settings["zarinpal_callback_url"].strip()
        or DEFAULT_CALLBACK_URL
    )

    enabled = (
        settings["zarinpal_enabled"] == "1"
    )

    return {
        "merchant_id": merchant_id,
        "callback_url": callback_url,
        "enabled": "1" if enabled else "0",
    }


def _require_gateway() -> dict[str, str]:
    config = _gateway_config()

    if config["enabled"] != "1":
        raise ZarinpalError(
            "درگاه زرین‌پال هنوز از پنل مدیریت فعال نشده است."
        )

    merchant_id = config["merchant_id"]

    if not merchant_id:
        raise ZarinpalError(
            "Merchant ID زرین‌پال هنوز در پنل مدیریت ثبت نشده است."
        )

    if (
        "مرچنت" in merchant_id
        or "واقعی" in merchant_id
        or "MERCHANT-ID" in merchant_id
    ):
        raise ZarinpalError(
            "Merchant ID ثبت‌شده مقدار نمونه است."
        )

    return config


def _safe_json(
    response: httpx.Response,
) -> dict[str, Any]:
    try:
        payload = response.json()

    except (json.JSONDecodeError, ValueError) as exc:
        body = response.text[:600].replace(
            "\n",
            " ",
        ).strip()

        raise ZarinpalError(
            "پاسخ دریافتی از زرین‌پال معتبر نبود؛ "
            f"HTTP={response.status_code}، "
            f"Body={body or '[empty]'}"
        ) from exc

    if not isinstance(payload, dict):
        raise ZarinpalError(
            "ساختار پاسخ زرین‌پال نامعتبر است."
        )

    return payload


def _error_text(
    payload: dict[str, Any],
) -> str:
    errors = payload.get("errors")

    if isinstance(errors, dict):
        return (
            f"کد {errors.get('code', '-')}: "
            f"{errors.get('message', 'خطای نامشخص')}"
        )

    data = payload.get("data")

    if isinstance(data, dict):
        return (
            f"کد {data.get('code', '-')}: "
            f"{data.get('message', 'خطای نامشخص')}"
        )

    return str(payload)


async def create_payment(
    amount_rial: int | None = None,
    description: str = "",
    email: str = "",
    mobile: str = "",
    amount: int | None = None,
) -> dict[str, Any]:
    config = _require_gateway()

    final_amount = (
        amount_rial
        if amount_rial is not None
        else amount
    )

    if final_amount is None:
        raise ZarinpalError(
            "مبلغ پرداخت ارسال نشده است."
        )

    final_amount = int(final_amount)

    if final_amount <= 0:
        raise ZarinpalError(
            "مبلغ پرداخت نامعتبر است."
        )

    metadata: dict[str, str] = {}

    if email:
        metadata["email"] = email.strip()

    if mobile:
        metadata["mobile"] = mobile.strip()

    payload = {
        "merchant_id": config["merchant_id"],
        "amount": final_amount,
        "callback_url": config["callback_url"],
        "description": (
            description
            or "خرید اشتراک رشدیار"
        )[:255],
        "metadata": metadata,
    }

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(40.0),
            follow_redirects=False,
        ) as client:
            response = await client.post(
                REQUEST_URL,
                json=payload,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "Rashdyar-Payment/1.0",
                },
            )

    except httpx.RequestError as exc:
        raise ZarinpalError(
            f"ارتباط با زرین‌پال برقرار نشد: {exc}"
        ) from exc

    result = _safe_json(response)

    if response.status_code >= 400:
        raise ZarinpalError(
            f"خطای درخواست زرین‌پال: {_error_text(result)}"
        )

    data = result.get("data")

    if not isinstance(data, dict):
        raise ZarinpalError(
            "پاسخ زرین‌پال فاقد اطلاعات پرداخت است."
        )

    code = int(data.get("code") or 0)
    authority = str(
        data.get("authority") or ""
    ).strip()

    if code != 100 or not authority:
        raise ZarinpalError(
            f"درخواست پرداخت تأیید نشد: {_error_text(result)}"
        )

    payment_url = (
        START_PAY_URL.rstrip("/")
        + "/"
        + authority
    )

    return {
        "success": True,
        "authority": authority,
        "payment_url": payment_url,
        "url": payment_url,
        "code": code,
        "fee": data.get("fee"),
        "fee_type": data.get("fee_type"),
    }


async def verify_payment(
    amount_rial: int | None = None,
    authority: str = "",
    amount: int | None = None,
) -> dict[str, Any]:
    config = _require_gateway()

    final_amount = (
        amount_rial
        if amount_rial is not None
        else amount
    )

    if final_amount is None:
        raise ZarinpalError(
            "مبلغ تأیید پرداخت ارسال نشده است."
        )

    authority = str(authority or "").strip()

    if not authority:
        raise ZarinpalError(
            "Authority پرداخت خالی است."
        )

    payload = {
        "merchant_id": config["merchant_id"],
        "amount": int(final_amount),
        "authority": authority,
    }

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(40.0),
            follow_redirects=False,
        ) as client:
            response = await client.post(
                VERIFY_URL,
                json=payload,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "Rashdyar-Payment/1.0",
                },
            )

    except httpx.RequestError as exc:
        raise ZarinpalError(
            f"ارتباط تأیید پرداخت برقرار نشد: {exc}"
        ) from exc

    result = _safe_json(response)

    if response.status_code >= 400:
        raise ZarinpalError(
            f"خطای تأیید پرداخت: {_error_text(result)}"
        )

    data = result.get("data")

    if not isinstance(data, dict):
        raise ZarinpalError(
            "پاسخ تأیید زرین‌پال فاقد اطلاعات است."
        )

    code = int(data.get("code") or 0)

    if code not in (100, 101):
        raise ZarinpalError(
            f"پرداخت تأیید نشد: {_error_text(result)}"
        )

    return {
        "success": True,
        "already_verified": code == 101,
        "code": code,
        "ref_id": str(data.get("ref_id") or ""),
        "card_pan": str(data.get("card_pan") or ""),
        "card_hash": str(data.get("card_hash") or ""),
        "fee": data.get("fee"),
        "fee_type": data.get("fee_type"),
    }

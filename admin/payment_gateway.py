from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .common import *


router = APIRouter(prefix="/admin")

DATABASE_PATH = Path("/root/aistudio-api/subscription.db")

DEFAULT_CALLBACK_URL = "https://ap.movifilm.sbs/payment/verify"


def open_database() -> sqlite3.Connection:
    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )
    connection.row_factory = sqlite3.Row
    return connection


def ensure_gateway_settings() -> None:
    now = isoformat(utc_now())

    defaults = {
        "zarinpal_enabled": "0",
        "zarinpal_merchant_id": "",
        "zarinpal_callback_url": DEFAULT_CALLBACK_URL,
    }

    with open_database() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            )
            """
        )

        for key, value in defaults.items():
            connection.execute(
                """
                INSERT INTO app_settings(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO NOTHING
                """,
                (key, value, now),
            )

        connection.commit()


def load_gateway_settings() -> dict[str, str]:
    ensure_gateway_settings()

    keys = (
        "zarinpal_enabled",
        "zarinpal_merchant_id",
        "zarinpal_callback_url",
    )

    with open_database() as connection:
        rows = connection.execute(
            """
            SELECT key, value
            FROM app_settings
            WHERE key IN (?, ?, ?)
            """,
            keys,
        ).fetchall()

    values = {row["key"]: str(row["value"] or "") for row in rows}

    values.setdefault("zarinpal_enabled", "0")
    values.setdefault("zarinpal_merchant_id", "")
    values.setdefault("zarinpal_callback_url", DEFAULT_CALLBACK_URL)

    return values


def load_transaction_summary() -> tuple[dict[str, int], list[sqlite3.Row]]:
    summary = {
        "all": 0,
        "paid": 0,
        "pending": 0,
        "failed": 0,
    }
    transactions: list[sqlite3.Row] = []

    try:
        with open_database() as connection:
            table = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                  AND name='payment_transactions'
                """
            ).fetchone()

            if table is None:
                return summary, transactions

            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(payment_transactions)"
                ).fetchall()
            }

            summary["all"] = int(
                connection.execute(
                    "SELECT COUNT(*) AS total FROM payment_transactions"
                ).fetchone()["total"]
            )

            summary["paid"] = int(
                connection.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM payment_transactions
                    WHERE status='paid'
                    """
                ).fetchone()["total"]
            )

            summary["pending"] = int(
                connection.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM payment_transactions
                    WHERE status='pending'
                    """
                ).fetchone()["total"]
            )

            summary["failed"] = int(
                connection.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM payment_transactions
                    WHERE status IN (
                        'failed',
                        'cancelled',
                        'verify_failed'
                    )
                    """
                ).fetchone()["total"]
            )

            select_fields = [
                "id",
                "authority",
                "email",
                "plan_slug",
                "status",
                "created_at",
            ]

            for optional_field in (
                "amount_toman",
                "amount",
                "ref_id",
                "verified_at",
            ):
                if optional_field in columns:
                    select_fields.append(optional_field)

            transactions = connection.execute(
                f"""
                SELECT {", ".join(select_fields)}
                FROM payment_transactions
                ORDER BY created_at DESC
                LIMIT 20
                """
            ).fetchall()

    except Exception:
        pass

    return summary, transactions


def mask_merchant_id(value: str) -> str:
    value = str(value or "").strip()

    if len(value) < 10:
        return "تنظیم نشده"

    return f"{value[:4]}••••••••{value[-4:]}"


def payment_css() -> str:
    return """
<style>
.gateway-page{
    display:grid;
    gap:16px;
}

.gateway-hero{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:18px;
    padding:22px;
    border:1px solid var(--border);
    border-radius:22px;
    background:
      radial-gradient(circle at 10% 100%,rgba(108,60,255,.13),transparent 34%),
      var(--card);
    box-shadow:var(--shadow);
}

.gateway-hero h2{
    margin:0 0 7px;
    font-size:23px;
}

.gateway-hero p{
    margin:0;
    color:var(--muted);
    font-size:12px;
}

.gateway-logo{
    width:68px;
    height:68px;
    display:grid;
    place-items:center;
    flex:0 0 auto;
    border-radius:20px;
    color:#fff;
    background:linear-gradient(135deg,#6c3cff,#3f168f);
    font-size:28px;
    box-shadow:0 15px 34px rgba(108,60,255,.24);
}

.gateway-status{
    display:inline-flex;
    align-items:center;
    gap:7px;
    padding:7px 11px;
    border-radius:999px;
    font-size:11px;
    font-weight:900;
}

.gateway-status.on{
    color:#12845d;
    background:#e7f8f0;
}

.gateway-status.off{
    color:#b13c55;
    background:#fff0f3;
}

.gateway-grid{
    display:grid;
    grid-template-columns:minmax(0,1.2fr) minmax(300px,.8fr);
    gap:16px;
}

.gateway-card{
    padding:22px;
    border:1px solid var(--border);
    border-radius:21px;
    background:var(--card);
    box-shadow:var(--shadow);
}

.gateway-title{
    margin:0 0 5px;
    font-size:17px;
}

.gateway-desc{
    margin:0 0 18px;
    color:var(--muted);
    font-size:11px;
}

.gateway-field{
    margin-top:15px;
}

.gateway-field label{
    margin-bottom:7px;
}

.gateway-field small{
    display:block;
    margin-top:6px;
    color:var(--muted);
    line-height:1.8;
    font-size:10px;
}

.gateway-secret{
    position:relative;
}

.gateway-secret input{
    padding-left:86px;
    direction:ltr;
}

.show-secret{
    position:absolute;
    left:7px;
    top:7px;
    width:auto;
    padding:6px 10px;
    border:0;
    border-radius:9px;
    color:var(--primary);
    background:var(--primary-soft);
    font-size:10px;
    font-weight:900;
}

.gateway-switch{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:18px;
    padding:14px;
    border:1px solid var(--border);
    border-radius:15px;
    background:var(--card-2);
}

.gateway-switch strong{
    display:block;
    font-size:12px;
}

.gateway-switch span{
    display:block;
    margin-top:4px;
    color:var(--muted);
    font-size:10px;
}

.gateway-switch input{
    width:20px;
    height:20px;
    flex:0 0 auto;
    accent-color:var(--primary);
}

.callback-box{
    padding:13px;
    border-radius:13px;
    background:var(--card-2);
    direction:ltr;
    text-align:left;
    word-break:break-all;
    font-size:11px;
}

.gateway-actions{
    display:flex;
    align-items:center;
    gap:9px;
    margin-top:20px;
    flex-wrap:wrap;
}

.gateway-info{
    display:grid;
    gap:10px;
}

.gateway-info-row{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:12px;
    padding:12px;
    border-radius:14px;
    background:var(--card-2);
    font-size:11px;
}

.gateway-info-row span{
    color:var(--muted);
}

.gateway-info-row strong{
    direction:ltr;
    text-align:left;
}

.gateway-notice{
    padding:13px 15px;
    border:1px solid #f0d98e;
    border-radius:14px;
    color:#7d6215;
    background:var(--warning-soft);
    font-size:11px;
    line-height:1.9;
}

.gateway-success{
    padding:12px 14px;
    border:1px solid #a9e6cc;
    border-radius:14px;
    color:#13714f;
    background:#eaf9f2;
    font-size:11px;
    font-weight:850;
}

.gateway-error{
    padding:12px 14px;
    border:1px solid #f1b9c5;
    border-radius:14px;
    color:#a62e49;
    background:#fff0f3;
    font-size:11px;
    font-weight:850;
}

.gateway-kpis{
    display:grid;
    grid-template-columns:repeat(4,minmax(0,1fr));
    gap:12px;
}

.gateway-kpi{
    padding:16px;
    border:1px solid var(--border);
    border-radius:17px;
    background:var(--card);
}

.gateway-kpi span{
    display:block;
    color:var(--muted);
    font-size:10px;
}

.gateway-kpi strong{
    display:block;
    margin-top:5px;
    color:var(--primary);
    font-size:24px;
}

.status-paid{
    color:#12845d;
    background:#e7f8f0;
}

.status-pending{
    color:#8a6511;
    background:#fff7dc;
}

.status-failed{
    color:#b13c55;
    background:#fff0f3;
}

.transaction-status{
    display:inline-flex;
    padding:5px 8px;
    border-radius:999px;
    font-size:9px;
    font-weight:900;
}

@media(max-width:900px){
    .gateway-grid{
        grid-template-columns:1fr;
    }

    .gateway-kpis{
        grid-template-columns:repeat(2,1fr);
    }
}

@media(max-width:560px){
    .gateway-hero{
        align-items:flex-start;
    }

    .gateway-kpis{
        grid-template-columns:1fr;
    }
}
</style>
"""


@router.get(
    "/payment-gateway",
    response_class=HTMLResponse,
)
async def payment_gateway_page(request: Request):
    redirect = require_auth(request)

    if redirect:
        return redirect

    settings = load_gateway_settings()
    summary, transactions = load_transaction_summary()

    enabled = settings["zarinpal_enabled"] == "1"
    merchant_id = settings["zarinpal_merchant_id"]
    callback_url = (
        settings["zarinpal_callback_url"]
        or DEFAULT_CALLBACK_URL
    )

    configured = bool(merchant_id.strip())
    active = enabled and configured

    status = request.query_params.get("status", "")
    message = request.query_params.get("message", "")

    alert_html = ""

    if status == "success":
        alert_html = (
            f'<div class="gateway-success">{esc(message or "تنظیمات ذخیره شد.")}</div>'
        )
    elif status == "error":
        alert_html = (
            f'<div class="gateway-error">{esc(message or "ذخیره تنظیمات ناموفق بود.")}</div>'
        )

    rows_html = ""

    for item in transactions:
        keys = item.keys()

        amount_value = 0

        if "amount_toman" in keys:
            amount_value = int(item["amount_toman"] or 0)
        elif "amount" in keys:
            amount_value = int(item["amount"] or 0)

        status_value = str(item["status"] or "")
        status_class = (
            "status-paid"
            if status_value == "paid"
            else (
                "status-pending"
                if status_value == "pending"
                else "status-failed"
            )
        )

        ref_id = (
            str(item["ref_id"] or "")
            if "ref_id" in keys
            else ""
        )

        rows_html += f"""
        <tr>
            <td>{esc(item["email"])}</td>
            <td>{esc(item["plan_slug"])}</td>
            <td>{money(amount_value) if amount_value else "—"}</td>
            <td>
                <span class="transaction-status {status_class}">
                    {esc(status_value)}
                </span>
            </td>
            <td>{esc(ref_id or "—")}</td>
            <td>{esc(item["created_at"])}</td>
        </tr>
        """

    if not rows_html:
        rows_html = """
        <tr>
            <td colspan="6">
                <div class="empty-state">
                    هنوز تراکنشی ثبت نشده است.
                </div>
            </td>
        </tr>
        """

    body = f"""
{payment_css()}

<div class="gateway-page">

    {alert_html}

    <section class="gateway-hero">
        <div>
            <div class="gateway-status {'on' if active else 'off'}">
                {'● درگاه فعال' if active else '● درگاه غیرفعال'}
            </div>

            <h2>درگاه پرداخت زرین‌پال</h2>

            <p>
                تنظیم Merchant ID، مدیریت وضعیت درگاه و مشاهده تراکنش‌های خرید سایت.
            </p>
        </div>

        <div class="gateway-logo">💳</div>
    </section>

    <section class="gateway-kpis">
        <div class="gateway-kpi">
            <span>کل تراکنش‌ها</span>
            <strong>{summary["all"]}</strong>
        </div>

        <div class="gateway-kpi">
            <span>پرداخت موفق</span>
            <strong>{summary["paid"]}</strong>
        </div>

        <div class="gateway-kpi">
            <span>در انتظار</span>
            <strong>{summary["pending"]}</strong>
        </div>

        <div class="gateway-kpi">
            <span>ناموفق یا لغوشده</span>
            <strong>{summary["failed"]}</strong>
        </div>
    </section>

    <div class="gateway-grid">

        <section class="gateway-card">
            <h3 class="gateway-title">تنظیمات اتصال</h3>

            <p class="gateway-desc">
                بعد از دریافت درگاه، Merchant ID را در این بخش وارد و درگاه را فعال کن.
            </p>

            {
                ''
                if configured
                else '''
                <div class="gateway-notice">
                    هنوز Merchant ID ثبت نشده است. تا قبل از ثبت و فعال‌کردن
                    درگاه، خرید کاربران آغاز نمی‌شود و پیام مناسب نمایش داده خواهد شد.
                </div>
                '''
            }

            <form
                method="post"
                action="/admin/payment-gateway/save">

                <div class="gateway-switch">
                    <div>
                        <strong>فعال‌سازی درگاه زرین‌پال</strong>
                        <span>
                            فقط پس از دریافت Merchant ID این گزینه را فعال کن.
                        </span>
                    </div>

                    <input
                        type="checkbox"
                        name="zarinpal_enabled"
                        value="1"
                        {'checked' if enabled else ''}>
                </div>

                <div class="gateway-field">
                    <label for="merchantId">Merchant ID</label>

                    <div class="gateway-secret">
                        <input
                            id="merchantId"
                            type="password"
                            name="zarinpal_merchant_id"
                            value="{esc(merchant_id)}"
                            autocomplete="off"
                            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx">

                        <button
                            class="show-secret"
                            type="button"
                            onclick="toggleMerchant()">
                            نمایش
                        </button>
                    </div>

                    <small>
                        Merchant ID را دقیقاً از پنل زرین‌پال کپی کن.
                    </small>
                </div>

                <div class="gateway-field">
                    <label>Callback URL</label>

                    <div class="callback-box">
                        {esc(callback_url)}
                    </div>

                    <input
                        type="hidden"
                        name="zarinpal_callback_url"
                        value="{esc(callback_url)}">

                    <small>
                        این نشانی باید در تنظیمات درگاه زرین‌پال مجاز باشد.
                    </small>
                </div>

                <div class="gateway-actions">
                    <button class="btn btn-primary" type="submit">
                        ذخیره تنظیمات درگاه
                    </button>

                    <a
                        class="btn btn-secondary"
                        href="/buy/pro-monthly"
                        target="_blank">
                        مشاهده صفحه خرید
                    </a>
                </div>
            </form>
        </section>

        <aside class="gateway-card">
            <h3 class="gateway-title">وضعیت فعلی</h3>

            <p class="gateway-desc">
                خلاصه تنظیمات ثبت‌شده در سیستم مرکزی پرداخت.
            </p>

            <div class="gateway-info">

                <div class="gateway-info-row">
                    <span>ارائه‌دهنده</span>
                    <strong>زرین‌پال</strong>
                </div>

                <div class="gateway-info-row">
                    <span>Merchant ID</span>
                    <strong>{esc(mask_merchant_id(merchant_id))}</strong>
                </div>

                <div class="gateway-info-row">
                    <span>وضعیت تنظیمات</span>
                    <strong>
                        {'آماده استفاده' if active else 'نیازمند تنظیم'}
                    </strong>
                </div>

                <div class="gateway-info-row">
                    <span>واحد قیمت سایت</span>
                    <strong>تومان</strong>
                </div>

                <div class="gateway-info-row">
                    <span>فعال‌سازی اشتراک</span>
                    <strong>خودکار با ایمیل</strong>
                </div>

            </div>
        </aside>
    </div>

    <section class="gateway-card">
        <h3 class="gateway-title">آخرین تراکنش‌ها</h3>

        <p class="gateway-desc">
            آخرین درخواست‌ها و پرداخت‌های ثبت‌شده در سایت رشدیار.
        </p>

        <div style="overflow:auto">
            <table>
                <thead>
                    <tr>
                        <th>ایمیل</th>
                        <th>پلن</th>
                        <th>مبلغ</th>
                        <th>وضعیت</th>
                        <th>شماره پیگیری</th>
                        <th>تاریخ</th>
                    </tr>
                </thead>

                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
    </section>

</div>

<script>
function toggleMerchant(){{
    const input = document.getElementById("merchantId");
    const button = event.currentTarget;

    if(input.type === "password"){{
        input.type = "text";
        button.textContent = "پنهان";
    }}else{{
        input.type = "password";
        button.textContent = "نمایش";
    }}
}}
</script>
"""

    return HTMLResponse(
        page_layout(
            "درگاه پرداخت",
            body,
        )
    )


@router.post("/payment-gateway/save")
async def save_payment_gateway(request: Request):
    redirect = require_auth(request)

    if redirect:
        return redirect

    try:
        form = await read_form(request)

        enabled = (
            "1"
            if form.get("zarinpal_enabled") == "1"
            else "0"
        )

        merchant_id = str(
            form.get("zarinpal_merchant_id") or ""
        ).strip()

        callback_url = str(
            form.get("zarinpal_callback_url")
            or DEFAULT_CALLBACK_URL
        ).strip()

        if enabled == "1" and not merchant_id:
            raise ValueError(
                "برای فعال‌کردن زرین‌پال باید Merchant ID وارد شود."
            )

        if merchant_id and len(merchant_id) < 20:
            raise ValueError(
                "Merchant ID واردشده معتبر به نظر نمی‌رسد."
            )

        if not callback_url.startswith("https://"):
            raise ValueError(
                "Callback URL باید با https:// شروع شود."
            )

        values = {
            "zarinpal_enabled": enabled,
            "zarinpal_merchant_id": merchant_id,
            "zarinpal_callback_url": callback_url,
        }

        now = isoformat(utc_now())

        with open_database() as connection:
            for key, value in values.items():
                connection.execute(
                    """
                    INSERT INTO app_settings(key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key)
                    DO UPDATE SET
                        value=excluded.value,
                        updated_at=excluded.updated_at
                    """,
                    (key, value, now),
                )

            connection.commit()

        return RedirectResponse(
            "/admin/payment-gateway?"
            "status=success&message="
            + quote("تنظیمات زرین‌پال با موفقیت ذخیره شد."),
            status_code=303,
        )

    except Exception as exc:
        return RedirectResponse(
            "/admin/payment-gateway?"
            "status=error&message="
            + quote(str(exc)),
            status_code=303,
        )


ensure_gateway_settings()

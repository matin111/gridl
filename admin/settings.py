from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from urllib.parse import quote

from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse

from .common import *


router = APIRouter(prefix="/admin")

BASE_DIR = Path("/root/aistudio-api")
DATABASE_PATH = BASE_DIR / "subscription.db"

APK_DIR = BASE_DIR / "site-assets" / "apk"
APK_URL_BASE = "https://ap.movifilm.sbs/site-assets/apk"


@contextmanager
def database():
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


def settings_css():
    return """
<style>

.settings-page{
    display:grid;
    gap:20px;
}

.settings-card{
    background:white;
    border:1px solid #e8e3f8;
    border-radius:24px;
    padding:25px;
}

.title{
    font-size:24px;
    font-weight:900;
}

.desc{
    color:#777;
    margin:15px 0;
}

.field{
    display:grid;
    gap:8px;
    margin-top:20px;
}

.settings-page input{
    padding:14px;
    border-radius:14px;
    border:1px solid #ddd;
    direction:ltr;
}

.settings-page button{
    background:#6c3cff;
    color:white;
    border:0;
    padding:14px 30px;
    border-radius:15px;
    font-weight:900;
}

.file-box{
    background:#f7f5ff;
    padding:15px;
    border-radius:15px;
    direction:ltr;
    overflow-wrap:anywhere;
}

/* =========================
   Payment gateway settings
   ========================= */

.gateway-section{
    margin-top:30px;
    padding-top:25px;
    border-top:1px solid #e8e3f8;
}

.gateway-heading{
    display:flex;
    align-items:flex-start;
    justify-content:space-between;
    gap:18px;
    margin-bottom:18px;
}

.gateway-heading h3{
    margin:0 0 7px;
    font-size:20px;
    font-weight:900;
}

.gateway-heading p{
    margin:0;
    color:#777;
    font-size:11px;
    line-height:1.9;
}

.gateway-badges{
    display:flex;
    align-items:center;
    gap:7px;
    flex-wrap:wrap;
}

.gateway-badge{
    min-height:28px;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    padding:5px 10px;
    border-radius:999px;
    font-size:9px;
    font-weight:900;
    white-space:nowrap;
}

.gateway-on{
    color:#147052;
    border:1px solid #bce7d5;
    background:#ebfaf3;
}

.gateway-off{
    color:#a8314b;
    border:1px solid #efbdc8;
    background:#fff0f3;
}

.gateway-grid{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:13px;
}

.gateway-item{
    min-height:98px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:18px;
    padding:16px;
    border:1px solid #e8e3f8;
    border-radius:17px;
    background:
        linear-gradient(
            145deg,
            #ffffff,
            #faf8ff
        );
}

.gateway-copy{
    min-width:0;
}

.gateway-copy strong{
    display:block;
    margin-bottom:6px;
    font-size:13px;
}

.gateway-copy small{
    display:block;
    color:#777;
    font-size:10px;
    line-height:1.8;
}

.gateway-switch{
    position:relative;
    width:52px;
    height:29px;
    min-width:52px;
    margin:0;
    cursor:pointer;
}

.gateway-switch input{
    position:absolute;
    width:1px;
    height:1px;
    opacity:0;
    pointer-events:none;
}

.gateway-slider{
    position:absolute;
    inset:0;
    border-radius:999px;
    background:#dcd7e8;
    cursor:pointer;
    transition:.22s ease;
}

.gateway-slider::before{
    content:"";
    position:absolute;
    top:4px;
    right:4px;
    width:21px;
    height:21px;
    border-radius:50%;
    background:#fff;
    box-shadow:0 4px 12px rgba(39,24,78,.18);
    transition:.22s ease;
}

.gateway-switch input:checked + .gateway-slider{
    background:
        linear-gradient(
            135deg,
            #8150ff,
            #531dbd
        );
}

.gateway-switch input:checked + .gateway-slider::before{
    transform:translateX(-23px);
}

.gateway-note{
    margin-top:15px;
    padding:12px 14px;
    border:1px solid #f0d98e;
    border-radius:13px;
    color:#765f1b;
    background:#fff9df;
    font-size:10px;
    line-height:1.9;
}

.save-row{
    display:flex;
    align-items:center;
    gap:10px;
    flex-wrap:wrap;
    margin-top:20px;
}

@media(max-width:720px){

    .settings-card{
        padding:18px;
        border-radius:20px;
    }

    .gateway-heading{
        flex-direction:column;
    }

    .gateway-grid{
        grid-template-columns:1fr;
    }

    .gateway-item{
        min-height:90px;
    }

}

</style>
"""


@router.get(
    "/settings",
    response_class=HTMLResponse,
)
async def settings_page(request: Request):
    redirect = require_auth(request)

    if redirect:
        return redirect

    with database() as db:
        rows = db.execute(
            """
            SELECT key, value
            FROM app_settings
            WHERE key IN (
                'apk_url',
                'market_url',
                'google_play_url',
                'zarinpal_enabled',
                'bazaar_payment_enabled'
            )
            """
        ).fetchall()

    settings = {
        str(row["key"]): str(row["value"] or "")
        for row in rows
    }

    zarinpal_enabled = (
        settings.get(
            "zarinpal_enabled",
            "0",
        ) == "1"
    )

    bazaar_enabled = (
        settings.get(
            "bazaar_payment_enabled",
            "1",
        ) == "1"
    )

    zarinpal_checked = (
        "checked"
        if zarinpal_enabled
        else ""
    )

    bazaar_checked = (
        "checked"
        if bazaar_enabled
        else ""
    )

    zarinpal_status = (
        "فعال"
        if zarinpal_enabled
        else "غیرفعال"
    )

    bazaar_status = (
        "فعال"
        if bazaar_enabled
        else "غیرفعال"
    )

    zarinpal_badge_class = (
        "gateway-on"
        if zarinpal_enabled
        else "gateway-off"
    )

    bazaar_badge_class = (
        "gateway-on"
        if bazaar_enabled
        else "gateway-off"
    )

    apk_url = esc(
        settings.get(
            "apk_url",
            "هنوز آپلود نشده",
        )
    )

    market_url = esc(
        settings.get(
            "market_url",
            "",
        )
    )

    google_play_url = esc(
        settings.get(
            "google_play_url",
            "",
        )
    )

    body = f"""
{settings_css()}

<div class="settings-page">

    <div class="settings-card">

        <div class="title">
            دانلود و انتشار اپلیکیشن رشدیار
        </div>

        <div class="desc">
            آپلود APK، مدیریت لینک‌های انتشار و کنترل
            مرکزی روش‌های پرداخت
        </div>

        <form
            method="post"
            action="/admin/settings/upload-apk"
            enctype="multipart/form-data"
        >

            <div class="field">
                <label>فایل APK</label>

                <input
                    type="file"
                    name="apk_file"
                    accept=".apk"
                    required
                >
            </div>

            <div class="save-row">
                <button type="submit">
                    آپلود فایل APK
                </button>
            </div>

        </form>

        <div class="field">
            <label>لینک APK فعلی</label>

            <div class="file-box">
                {apk_url}
            </div>
        </div>

        <form
            method="post"
            action="/admin/settings/save"
        >

            <div class="field">
                <label>لینک بازار</label>

                <input
                    name="market_url"
                    value="{market_url}"
                    placeholder="https://cafebazaar.ir/app/..."
                >
            </div>

            <div class="field">
                <label>Google Play</label>

                <input
                    name="google_play_url"
                    value="{google_play_url}"
                    placeholder="https://play.google.com/store/apps/..."
                >
            </div>

            <div class="gateway-section">

                <div class="gateway-heading">

                    <div>
                        <h3>
                            مدیریت درگاه‌های پرداخت
                        </h3>

                        <p>
                            روش‌های خرید اشتراک سایت و اپلیکیشن
                            را به‌صورت مرکزی فعال یا غیرفعال کن.
                        </p>
                    </div>

                    <div class="gateway-badges">

                        <span
                            class="gateway-badge {zarinpal_badge_class}"
                        >
                            زرین‌پال: {zarinpal_status}
                        </span>

                        <span
                            class="gateway-badge {bazaar_badge_class}"
                        >
                            بازار: {bazaar_status}
                        </span>

                    </div>

                </div>

                <div class="gateway-grid">

                    <div class="gateway-item">

                        <div class="gateway-copy">
                            <strong>
                                درگاه زرین‌پال
                            </strong>

                            <small>
                                پرداخت اشتراک از سایت و
                                پنل کاربری با زرین‌پال
                            </small>
                        </div>

                        <label class="gateway-switch">

                            <input
                                type="checkbox"
                                name="zarinpal_enabled"
                                value="1"
                                {zarinpal_checked}
                            >

                            <span class="gateway-slider"></span>

                        </label>

                    </div>

                    <div class="gateway-item">

                        <div class="gateway-copy">
                            <strong>
                                پرداخت درون‌برنامه‌ای بازار
                            </strong>

                            <small>
                                خرید اشتراک داخل اپ اندروید
                                با کافه‌بازار و Poolakey
                            </small>
                        </div>

                        <label class="gateway-switch">

                            <input
                                type="checkbox"
                                name="bazaar_payment_enabled"
                                value="1"
                                {bazaar_checked}
                            >

                            <span class="gateway-slider"></span>

                        </label>

                    </div>

                </div>

                <div class="gateway-note">
                    خاموش‌کردن هر روش فقط خریدهای جدید را
                    متوقف می‌کند. اشتراک فعال و خریدهای قبلی
                    کاربران حذف نخواهند شد.
                </div>

            </div>

            <div class="save-row">
                <button type="submit">
                    ذخیره تنظیمات
                </button>
            </div>

        </form>

    </div>

</div>
"""

    return HTMLResponse(
        page_layout(
            "نسخه و تنظیمات",
            body,
        )
    )


@router.post("/settings/upload-apk")
async def upload_apk(
    request: Request,
    apk_file: UploadFile = File(...),
):
    redirect = require_auth(request)

    if redirect:
        return redirect

    filename = str(
        apk_file.filename or ""
    ).strip()

    if not filename.lower().endswith(".apk"):
        return RedirectResponse(
            "/admin/settings",
            status_code=303,
        )

    APK_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_filename = Path(filename).name

    file_path = (
        APK_DIR
        / safe_filename
    )

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(
            apk_file.file,
            buffer,
        )

    apk_url = (
        f"{APK_URL_BASE}/"
        f"{quote(safe_filename)}"
    )

    with database() as db:
        db.execute(
            """
            INSERT INTO app_settings(
                key,
                value,
                updated_at
            )
            VALUES(
                ?,
                ?,
                ?
            )
            ON CONFLICT(key)
            DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (
                "apk_url",
                apk_url,
                isoformat(utc_now()),
            ),
        )

    return RedirectResponse(
        "/admin/settings",
        status_code=303,
    )


@router.post("/settings/save")
async def save_settings(request: Request):
    redirect = require_auth(request)

    if redirect:
        return redirect

    form = await read_form(request)

    values = {
        "market_url": str(
            form.get(
                "market_url",
                "",
            )
            or ""
        ).strip(),

        "google_play_url": str(
            form.get(
                "google_play_url",
                "",
            )
            or ""
        ).strip(),

        "zarinpal_enabled": (
            "1"
            if form.get(
                "zarinpal_enabled"
            ) == "1"
            else "0"
        ),

        "bazaar_payment_enabled": (
            "1"
            if form.get(
                "bazaar_payment_enabled"
            ) == "1"
            else "0"
        ),
    }

    now = isoformat(
        utc_now()
    )

    with database() as db:
        for key, value in values.items():
            db.execute(
                """
                INSERT INTO app_settings(
                    key,
                    value,
                    updated_at
                )
                VALUES(
                    ?,
                    ?,
                    ?
                )
                ON CONFLICT(key)
                DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    value,
                    now,
                ),
            )

    return RedirectResponse(
        "/admin/settings",
        status_code=303,
    )

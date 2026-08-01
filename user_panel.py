from __future__ import annotations

import html
import os
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse


router = APIRouter(tags=["user-panel"])

API_BASE_URL = os.getenv(
    "USER_PANEL_API_BASE_URL",
    "http://127.0.0.1:8080",
).rstrip("/")

COOKIE_NAME = "rashdyar_user_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def get_token(request: Request) -> str:
    return request.cookies.get(COOKIE_NAME, "").strip()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def to_persian_digits(value: Any) -> str:
    return str(value).translate(
        str.maketrans(
            "0123456789",
            "۰۱۲۳۴۵۶۷۸۹",
        )
    )


def normalize_plan(plan: str) -> str:
    value = (plan or "free").strip().lower()

    names = {
        "free": "رایگان",
        "monthly": "حرفه‌ای ماهانه",
        "pro": "حرفه‌ای",
        "professional": "حرفه‌ای",
        "quarterly": "حرفه‌ای سه‌ماهه",
        "premium": "پریمیوم",
        "manual": "اشتراک ویژه",
    }

    return names.get(value, plan or "رایگان")


def normalize_date(value: str) -> str:
    if not value:
        return "ثبت نشده"

    clean = (
        value.strip()
        .replace("T", " ")
        .replace("Z", "")
    )

    if "." in clean:
        clean = clean.split(".", 1)[0]

    try:
        parsed = datetime.fromisoformat(clean)
        result = parsed.strftime("%Y/%m/%d – %H:%M")
        return to_persian_digits(result)
    except ValueError:
        return to_persian_digits(clean)


def active_nav(current: str, expected: str) -> str:
    return " active" if current == expected else ""


async def api_get(
    path: str,
    *,
    token: str,
) -> tuple[int, dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{API_BASE_URL}{path}",
                headers=auth_headers(token),
            )

        try:
            data = response.json()
        except ValueError:
            data = {
                "success": False,
                "message": "پاسخ نامعتبر از سرور دریافت شد.",
            }

        return response.status_code, data

    except httpx.HTTPError:
        return 503, {
            "success": False,
            "message": "ارتباط با سرور برقرار نشد.",
        }


async def api_post(
    path: str,
    *,
    json_data: dict[str, Any],
    token: str = "",
) -> tuple[int, dict[str, Any]]:
    headers = auth_headers(token) if token else {}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{API_BASE_URL}{path}",
                json=json_data,
                headers=headers,
            )

        try:
            data = response.json()
        except ValueError:
            data = {
                "success": False,
                "message": "پاسخ نامعتبر از سرور دریافت شد.",
            }

        return response.status_code, data

    except httpx.HTTPError:
        return 503, {
            "success": False,
            "message": "ارتباط با سرور برقرار نشد.",
        }


async def require_user(
    request: Request,
) -> tuple[str, dict[str, Any]] | RedirectResponse:
    token = get_token(request)

    if not token:
        return RedirectResponse(
            "/account/login",
            status_code=303,
        )

    status, data = await api_get(
        "/v1/auth/me",
        token=token,
    )

    if status != 200 or not data.get("success"):
        response = RedirectResponse(
            "/account/login?error="
            + quote_plus("نشست شما منقضی شده است."),
            status_code=303,
        )

        response.delete_cookie(
            COOKIE_NAME,
            path="/",
        )

        return response

    return token, (data.get("user") or {})


# ---------------------------------------------------------
# Shared layout
# ---------------------------------------------------------

def base_page(
    *,
    title: str,
    body: str,
) -> str:
    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} | رشدیار</title>

<style>
:root{{
    --purple:#6c3cff;
    --purple-dark:#41169d;
    --purple-soft:#f2edff;
    --bg:#f8f7ff;
    --card:#fff;
    --ink:#181320;
    --muted:#7e7689;
    --line:#e8e1f4;
    --green:#22b878;
    --red:#c93e5c;
    --shadow:0 15px 40px rgba(48,27,96,.07);
}}

*{{
    box-sizing:border-box;
}}

html{{
    scroll-behavior:smooth;
}}

body{{
    margin:0;
    min-height:100vh;
    color:var(--ink);
    background:
        radial-gradient(
            circle at 12% 5%,
            rgba(108,60,255,.11),
            transparent 27%
        ),
        radial-gradient(
            circle at 92% 90%,
            rgba(108,60,255,.08),
            transparent 28%
        ),
        var(--bg);
    font-family:Tahoma,Arial,sans-serif;
}}

a{{
    color:inherit;
    text-decoration:none;
}}

button,
input{{
    font-family:inherit;
}}

.container{{
    width:min(1180px,calc(100% - 36px));
    margin-inline:auto;
}}

.topbar{{
    position:sticky;
    top:0;
    z-index:50;
    min-height:70px;
    display:flex;
    align-items:center;
    background:rgba(255,255,255,.93);
    border-bottom:1px solid rgba(108,60,255,.09);
    backdrop-filter:blur(15px);
}}

.topbar-inner{{
    width:min(1180px,calc(100% - 36px));
    margin:auto;
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:18px;
}}

.brand{{
    display:flex;
    align-items:center;
    gap:10px;
    font-size:20px;
    font-weight:950;
}}

.brand img{{
    width:43px;
    height:43px;
    border-radius:13px;
    object-fit:cover;
    box-shadow:0 11px 25px rgba(108,60,255,.22);
}}

.top-actions{{
    display:flex;
    align-items:center;
    gap:9px;
}}

.top-btn{{
    min-height:40px;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    padding:9px 15px;
    border:1px solid var(--line);
    border-radius:12px;
    background:#fff;
    font-size:10px;
    font-weight:900;
}}

.top-btn.primary{{
    color:#fff;
    border-color:transparent;
    background:linear-gradient(
        135deg,
        var(--purple),
        var(--purple-dark)
    );
}}

.account-shell{{
    padding:30px 0 65px;
}}

.dashboard-head{{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:18px;
    margin-bottom:21px;
}}

.dashboard-head h1{{
    margin:0 0 7px;
    font-size:28px;
}}

.dashboard-head p{{
    margin:0;
    color:var(--muted);
    font-size:10px;
}}

.head-actions{{
    display:flex;
    gap:9px;
}}

.logout-btn,
.upgrade-btn{{
    min-height:41px;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    padding:9px 15px;
    border-radius:12px;
    font-size:10px;
    font-weight:950;
}}

.logout-btn{{
    color:#b13250;
    border:1px solid #efc3cd;
    background:#fff3f6;
}}

.upgrade-btn{{
    color:#fff;
    background:linear-gradient(
        135deg,
        #8150ff,
        #4d19b4
    );
    box-shadow:0 12px 28px rgba(108,60,255,.21);
}}

.account-nav{{
    display:flex;
    gap:8px;
    margin-bottom:20px;
    padding:7px;
    overflow-x:auto;
    border:1px solid var(--line);
    border-radius:17px;
    background:rgba(255,255,255,.80);
    box-shadow:var(--shadow);
}}

.account-nav a{{
    min-width:max-content;
    min-height:40px;
    display:flex;
    align-items:center;
    justify-content:center;
    gap:7px;
    padding:8px 15px;
    border-radius:11px;
    color:var(--muted);
    font-size:10px;
    font-weight:900;
    transition:.22s ease;
}}

.account-nav a:hover{{
    color:var(--purple);
    background:var(--purple-soft);
}}

.account-nav a.active{{
    color:#fff;
    background:linear-gradient(
        135deg,
        var(--purple),
        var(--purple-dark)
    );
    box-shadow:0 10px 23px rgba(108,60,255,.20);
}}

.hero{{
    position:relative;
    overflow:hidden;
    display:grid;
    grid-template-columns:1.2fr .8fr;
    align-items:center;
    gap:25px;
    margin-bottom:18px;
    padding:28px;
    border-radius:27px;
    color:#fff;
    background:
        radial-gradient(
            circle at 8% 92%,
            rgba(177,137,255,.34),
            transparent 36%
        ),
        linear-gradient(
            135deg,
            #7b47f5,
            #4c1bab 58%,
            #2b0d68
        );
    box-shadow:0 22px 56px rgba(61,27,139,.20);
}}

.hero h2{{
    margin:0 0 10px;
    font-size:25px;
}}

.hero p{{
    max-width:620px;
    margin:0;
    color:rgba(255,255,255,.78);
    font-size:10px;
    line-height:1.95;
}}

.plan-box{{
    width:min(240px,100%);
    justify-self:center;
    padding:18px;
    border:1px solid rgba(255,255,255,.14);
    border-radius:18px;
    background:rgba(255,255,255,.09);
    backdrop-filter:blur(10px);
}}

.plan-box small{{
    display:block;
    margin-bottom:6px;
    color:rgba(255,255,255,.68);
    font-size:9px;
}}

.plan-box strong{{
    display:block;
    font-size:20px;
}}

.plan-box a{{
    min-height:39px;
    display:flex;
    align-items:center;
    justify-content:center;
    margin-top:13px;
    border:1px solid rgba(255,255,255,.16);
    border-radius:11px;
    background:rgba(255,255,255,.10);
    font-size:9px;
    font-weight:900;
}}

.stats{{
    display:grid;
    grid-template-columns:repeat(4,minmax(0,1fr));
    gap:13px;
    margin-bottom:18px;
}}

.stat{{
    min-height:112px;
    padding:18px;
    border:1px solid var(--line);
    border-radius:18px;
    background:#fff;
    box-shadow:var(--shadow);
}}

.stat-icon{{
    width:32px;
    height:32px;
    display:grid;
    place-items:center;
    margin-bottom:12px;
    border-radius:10px;
    background:var(--purple-soft);
    font-size:15px;
}}

.stat span{{
    display:block;
    margin-bottom:7px;
    color:var(--muted);
    font-size:9px;
}}

.stat strong{{
    display:block;
    overflow-wrap:anywhere;
    font-size:14px;
    line-height:1.55;
}}

.stat.email strong{{
    direction:ltr;
    text-align:right;
    font-size:11px;
}}

.content-grid{{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:17px;
}}

.card{{
    min-width:0;
    padding:22px;
    border:1px solid var(--line);
    border-radius:21px;
    background:#fff;
    box-shadow:var(--shadow);
}}

.card h3{{
    margin:0 0 7px;
    font-size:17px;
}}

.card-subtitle{{
    margin:0 0 18px;
    color:var(--muted);
    font-size:9px;
    line-height:1.8;
}}

.info-list{{
    display:grid;
    gap:9px;
}}

.info-row{{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:15px;
    min-height:45px;
    padding:10px 12px;
    border-radius:12px;
    background:#f8f5ff;
    font-size:10px;
}}

.info-row span{{
    color:var(--muted);
}}

.info-row strong{{
    overflow-wrap:anywhere;
    text-align:left;
}}

.shortcuts{{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:10px;
}}

.shortcut{{
    min-height:105px;
    display:flex;
    flex-direction:column;
    justify-content:space-between;
    padding:14px;
    border:1px solid var(--line);
    border-radius:15px;
    background:linear-gradient(
        145deg,
        #fff,
        #faf8ff
    );
    transition:.22s ease;
}}

.shortcut:hover{{
    transform:translateY(-3px);
    border-color:rgba(108,60,255,.28);
    box-shadow:0 14px 30px rgba(108,60,255,.10);
}}

.shortcut i{{
    width:34px;
    height:34px;
    display:grid;
    place-items:center;
    border-radius:11px;
    background:var(--purple-soft);
    font-style:normal;
    font-size:16px;
}}

.shortcut strong{{
    font-size:10px;
}}


.app-download-card{{
    display:flex;
    flex-direction:column;
    justify-content:space-between;
    min-height:100%;
    background:
        radial-gradient(
            circle at 10% 90%,
            rgba(108,60,255,.08),
            transparent 35%
        ),
        linear-gradient(
            145deg,
            #fff,
            #faf8ff
        );
}}

.app-download-head{{
    display:flex;
    align-items:center;
    gap:14px;
    margin-bottom:17px;
}}

.app-download-head img{{
    width:60px;
    height:60px;
    flex:0 0 60px;
    object-fit:cover;
    border-radius:17px;
    box-shadow:0 14px 30px rgba(108,60,255,.20);
}}

.app-download-head h3{{
    margin-bottom:5px;
}}

.app-download-head .card-subtitle{{
    margin-bottom:0;
}}

.app-feature-list{{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:9px;
    margin-bottom:18px;
}}

.app-feature-list div{{
    min-height:42px;
    display:flex;
    align-items:center;
    padding:9px 11px;
    border:1px solid var(--line);
    border-radius:12px;
    background:#f8f5ff;
    font-size:9px;
    font-weight:800;
}}

.app-download-actions{{
    display:grid;
    grid-template-columns:1.3fr 1fr 1fr;
    gap:8px;
}}

.download-btn{{
    min-height:42px;
    display:flex;
    align-items:center;
    justify-content:center;
    padding:8px 11px;
    border:1px solid var(--line);
    border-radius:11px;
    background:#fff;
    font-size:9px;
    font-weight:950;
    transition:
        transform .22s ease,
        box-shadow .22s ease,
        border-color .22s ease;
}}

.download-btn.primary{{
    color:#fff;
    border-color:transparent;
    background:linear-gradient(
        135deg,
        var(--purple),
        var(--purple-dark)
    );
    box-shadow:0 12px 25px rgba(108,60,255,.19);
}}

.download-btn:hover{{
    transform:translateY(-2px);
    border-color:rgba(108,60,255,.28);
    box-shadow:0 12px 25px rgba(108,60,255,.11);
}}

@media(max-width:620px){{
    .app-feature-list{{
        grid-template-columns:1fr;
    }}

    .app-download-actions{{
        grid-template-columns:1fr;
    }}

    .app-download-head{{
        align-items:flex-start;
    }}
}}

.empty-state{{
    min-height:220px;
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    padding:25px;
    border:1px dashed #d9cfeb;
    border-radius:17px;
    background:#fbfaff;
    text-align:center;
}}

.empty-state i{{
    width:55px;
    height:55px;
    display:grid;
    place-items:center;
    margin-bottom:13px;
    border-radius:17px;
    background:var(--purple-soft);
    font-style:normal;
    font-size:24px;
}}

.empty-state strong{{
    margin-bottom:7px;
    font-size:13px;
}}

.empty-state p{{
    max-width:430px;
    margin:0;
    color:var(--muted);
    font-size:9px;
    line-height:1.9;
}}

.password-form{{
    display:grid;
    gap:10px;
}}

.password-form input{{
    width:100%;
    height:44px;
    padding:9px 12px;
    border:1px solid var(--line);
    border-radius:12px;
    outline:none;
    direction:ltr;
}}

.password-form input:focus{{
    border-color:var(--purple);
    box-shadow:0 0 0 4px rgba(108,60,255,.08);
}}

.password-form button{{
    min-height:44px;
    border:0;
    border-radius:12px;
    color:#fff;
    background:linear-gradient(
        135deg,
        var(--purple),
        var(--purple-dark)
    );
    font-weight:950;
    cursor:pointer;
}}

.notice{{
    margin-bottom:17px;
    padding:11px 13px;
    border-radius:12px;
    font-size:10px;
    line-height:1.8;
}}

.notice.success{{
    color:#157052;
    border:1px solid #bce7d5;
    background:#ebfaf3;
}}

.notice.error{{
    color:#a8314b;
    border:1px solid #efbdc8;
    background:#fff0f3;
}}

.subscription-card{{
    display:grid;
    grid-template-columns:1fr auto;
    gap:20px;
    align-items:center;
    padding:23px;
    border:1px solid var(--line);
    border-radius:20px;
    background:linear-gradient(
        145deg,
        #fff,
        #faf8ff
    );
}}

.subscription-card .price{{
    color:var(--purple);
    font-size:22px;
    font-weight:950;
}}

.subscription-card .actions{{
    display:flex;
    gap:8px;
}}

.primary-action,
.secondary-action{{
    min-height:41px;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    padding:8px 14px;
    border-radius:11px;
    font-size:9px;
    font-weight:950;
}}

.primary-action{{
    color:#fff;
    background:linear-gradient(
        135deg,
        var(--purple),
        var(--purple-dark)
    );
}}

.secondary-action{{
    border:1px solid var(--line);
    background:#fff;
}}


.subscription-overview{{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:20px;
}}

.subscription-current{{
    min-width:230px;
    padding:17px;
    border:1px solid var(--line);
    border-radius:16px;
    background:linear-gradient(
        145deg,
        #f7f2ff,
        #fff
    );
}}

.subscription-current span{{
    display:block;
    margin-bottom:6px;
    color:var(--muted);
    font-size:9px;
}}

.subscription-current strong{{
    display:block;
    margin-bottom:6px;
    color:var(--purple);
    font-size:18px;
}}

.subscription-current small{{
    color:var(--muted);
    font-size:9px;
}}

.plans-header{{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:18px;
    margin-bottom:18px;
}}

.account-plans{{
    display:grid;
    grid-template-columns:repeat(3,minmax(0,1fr));
    align-items:stretch;
    gap:14px;
}}

.account-plan{{
    position:relative;
    min-width:0;
    min-height:460px;
    display:flex;
    flex-direction:column;
    padding:22px;
    border:1px solid var(--line);
    border-radius:20px;
    background:#fff;
    box-shadow:0 14px 34px rgba(48,27,96,.065);
    transition:
        transform .24s ease,
        box-shadow .24s ease,
        border-color .24s ease;
}}

.account-plan:hover{{
    transform:translateY(-5px);
    border-color:rgba(108,60,255,.25);
    box-shadow:0 21px 45px rgba(76,39,155,.12);
}}

.account-plan.featured{{
    color:#fff;
    border-color:transparent;
    background:
        radial-gradient(
            circle at 12% 88%,
            rgba(157,107,255,.24),
            transparent 38%
        ),
        linear-gradient(
            145deg,
            #4e2a68,
            #24142f 58%,
            #160d1e
        );
    box-shadow:0 22px 50px rgba(45,21,67,.22);
}}

.account-plan.featured .account-plan-head small,
.account-plan.featured .account-plan-meta,
.account-plan.featured li,
.account-plan.featured .account-plan-old-price{{
    color:rgba(255,255,255,.72);
}}

.account-plan-head small{{
    display:block;
    margin-bottom:8px;
    color:var(--muted);
    font-size:9px;
}}

.account-plan-head h3{{
    margin:0;
    font-size:20px;
}}

.account-plan-price{{
    margin-top:20px;
    color:var(--purple);
    font-size:27px;
    font-weight:950;
}}

.account-plan.featured .account-plan-price{{
    color:#fff;
}}

.account-plan-price small{{
    margin-right:4px;
    font-size:9px;
    font-weight:800;
}}

.account-plan-old-price{{
    min-height:18px;
    margin-top:5px;
    color:#9b929f;
    font-size:9px;
    text-decoration:line-through;
}}

.account-plan-meta{{
    margin-top:12px;
    color:var(--muted);
    font-size:9px;
}}

.account-plan ul{{
    display:grid;
    gap:10px;
    margin:22px 0;
    padding:0;
    list-style:none;
}}

.account-plan li{{
    position:relative;
    padding-right:16px;
    color:#4f4858;
    font-size:9px;
    line-height:1.7;
}}

.account-plan li::before{{
    content:"✓";
    position:absolute;
    right:0;
    top:0;
    color:#39c585;
    font-weight:950;
}}

.account-plan-btn{{
    width:100%;
    min-height:43px;
    display:flex;
    align-items:center;
    justify-content:center;
    margin-top:auto;
    padding:9px 13px;
    border:1px solid var(--line);
    border-radius:12px;
    color:#fff;
    background:#18121f;
    font-size:9px;
    font-weight:950;
    transition:
        transform .22s ease,
        box-shadow .22s ease;
}}

.account-plan-btn.primary{{
    border-color:transparent;
    background:linear-gradient(
        135deg,
        #8b55ff,
        #6023db
    );
    box-shadow:0 14px 29px rgba(108,60,255,.25);
}}

.account-plan-btn.disabled{{
    color:#8b8393;
    background:#f1edf6;
    cursor:default;
}}

.account-plan-btn:not(.disabled):hover{{
    transform:translateY(-2px);
    box-shadow:0 17px 34px rgba(108,60,255,.20);
}}

.popular-badge,
.saving-badge,
.current-plan-badge{{
    position:absolute;
    top:-11px;
    z-index:2;
    min-height:24px;
    display:flex;
    align-items:center;
    justify-content:center;
    padding:4px 11px;
    border-radius:999px;
    font-size:8px;
    font-weight:950;
}}

.popular-badge{{
    left:20px;
    color:#fff;
    background:linear-gradient(
        135deg,
        #8b55ff,
        #6225dc
    );
}}

.saving-badge{{
    left:20px;
    color:#fff;
    background:#6c3cff;
}}

.current-plan-badge{{
    right:18px;
    color:#137252;
    border:1px solid #bce7d5;
    background:#eafaf3;
}}

.account-plan.featured .current-plan-badge{{
    color:#fff;
    border-color:rgba(255,255,255,.17);
    background:rgba(255,255,255,.13);
}}

@media(max-width:900px){{
    .account-plans{{
        grid-template-columns:1fr;
    }}

    .account-plan{{
        min-height:auto;
    }}
}}

@media(max-width:620px){{
    .subscription-overview{{
        align-items:stretch;
        flex-direction:column;
    }}

    .subscription-current{{
        min-width:0;
        width:100%;
    }}
}}


/* SUBSCRIPTION PRO START */

.subscription-hero{{
    position:relative;
    overflow:hidden;

    display:grid;
    grid-template-columns:minmax(0,1.15fr) minmax(270px,.85fr);
    align-items:center;
    gap:28px;

    margin-bottom:17px;
    padding:29px;

    border:1px solid rgba(108,60,255,.13);
    border-radius:27px;

    color:#fff;

    background:
        radial-gradient(
            circle at 10% 92%,
            rgba(179,138,255,.34),
            transparent 36%
        ),
        radial-gradient(
            circle at 92% 8%,
            rgba(147,100,255,.18),
            transparent 34%
        ),
        linear-gradient(
            135deg,
            #7b47f5,
            #4c1bab 58%,
            #2b0d68
        );

    box-shadow:
        0 22px 56px rgba(61,27,139,.20);
}}

.subscription-hero::before{{
    content:"";
    position:absolute;
    inset:0;

    background-image:
        radial-gradient(
            rgba(255,255,255,.16) 1px,
            transparent 1px
        );

    background-size:25px 25px;
    opacity:.10;
    pointer-events:none;
}}

.subscription-hero-copy,
.subscription-hero-status{{
    position:relative;
    z-index:2;
}}

.subscription-eyebrow{{
    display:inline-flex;
    align-items:center;

    min-height:27px;
    margin-bottom:10px;
    padding:5px 10px;

    border:1px solid rgba(255,255,255,.13);
    border-radius:999px;

    background:rgba(255,255,255,.09);

    color:rgba(255,255,255,.84);
    font-size:9px;
    font-weight:900;
}}

.subscription-hero h2{{
    margin:0 0 10px;
    font-size:27px;
    line-height:1.4;
}}

.subscription-hero-copy p{{
    max-width:610px;
    margin:0;

    color:rgba(255,255,255,.76);
    font-size:10px;
    line-height:1.95;
}}

.subscription-hero-actions{{
    display:flex;
    align-items:center;
    flex-wrap:wrap;
    gap:8px;

    margin-top:19px;
}}

.subscription-main-action,
.subscription-secondary-action{{
    min-height:41px;

    display:inline-flex;
    align-items:center;
    justify-content:center;

    padding:9px 15px;
    border-radius:12px;

    font-size:9px;
    font-weight:950;

    transition:
        transform .22s ease,
        background .22s ease,
        box-shadow .22s ease;
}}

.subscription-main-action{{
    color:#5520c4;
    background:#fff;
    box-shadow:0 12px 28px rgba(24,8,65,.16);
}}

.subscription-secondary-action{{
    color:#fff;
    border:1px solid rgba(255,255,255,.16);
    background:rgba(255,255,255,.08);
}}

.subscription-main-action:hover,
.subscription-secondary-action:hover{{
    transform:translateY(-2px);
}}

.subscription-secondary-action:hover{{
    background:rgba(255,255,255,.14);
}}

.subscription-hero-status{{
    padding:20px;

    border:1px solid rgba(255,255,255,.15);
    border-radius:20px;

    background:rgba(255,255,255,.09);
    backdrop-filter:blur(11px);

    box-shadow:
        inset 0 1px 0 rgba(255,255,255,.10);
}}

.subscription-status-top{{
    display:flex;
    align-items:center;
    gap:8px;
    margin-bottom:14px;
}}

.subscription-status-dot{{
    width:8px;
    height:8px;
    border-radius:50%;
    background:#42e29a;

    box-shadow:
        0 0 0 5px rgba(66,226,154,.10),
        0 0 15px rgba(66,226,154,.50);
}}

.subscription-status-top strong{{
    font-size:9px;
}}

.subscription-credit-number{{
    margin-bottom:2px;

    font-size:36px;
    line-height:1.2;
    font-weight:950;
}}

.subscription-hero-status > small{{
    color:rgba(255,255,255,.67);
    font-size:9px;
}}

.subscription-progress{{
    margin-top:17px;
}}

.subscription-progress-head{{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:10px;

    margin-bottom:7px;

    color:rgba(255,255,255,.70);
    font-size:8px;
}}

.subscription-progress-head strong{{
    color:#fff;
}}

.subscription-progress-track{{
    height:7px;
    overflow:hidden;

    border-radius:999px;
    background:rgba(255,255,255,.13);
}}

.subscription-progress-track span{{
    display:block;
    height:100%;
    border-radius:inherit;

    background:
        linear-gradient(
            90deg,
            #ffffff,
            #bf9fff
        );
}}

.subscription-details-grid{{
    display:grid;
    grid-template-columns:repeat(4,minmax(0,1fr));
    gap:13px;

    margin-bottom:17px;
}}

.subscription-detail-card{{
    min-width:0;
    min-height:125px;

    display:flex;
    flex-direction:column;
    justify-content:center;

    padding:18px;

    border:1px solid var(--line);
    border-radius:18px;

    background:
        linear-gradient(
            145deg,
            #ffffff,
            #faf8ff
        );

    box-shadow:var(--shadow);
}}

.subscription-detail-card i{{
    width:33px;
    height:33px;

    display:grid;
    place-items:center;

    margin-bottom:11px;

    border-radius:10px;
    background:var(--purple-soft);

    font-style:normal;
    font-size:15px;
}}

.subscription-detail-card span{{
    display:block;
    margin-bottom:6px;

    color:var(--muted);
    font-size:8px;
}}

.subscription-detail-card strong{{
    overflow-wrap:anywhere;

    font-size:11px;
    line-height:1.65;
}}

.account-plans-section{{
    margin-bottom:17px;
}}

.payment-history-card{{
    margin-top:0;
}}

.payment-history-head{{
    display:flex;
    align-items:flex-start;
    justify-content:space-between;
    gap:18px;
}}

.coming-soon-badge{{
    min-width:max-content;
    min-height:28px;

    display:inline-flex;
    align-items:center;
    justify-content:center;

    padding:5px 10px;

    border:1px solid rgba(108,60,255,.12);
    border-radius:999px;

    color:var(--purple);
    background:var(--purple-soft);

    font-size:8px;
    font-weight:900;
}}

.compact-empty{{
    min-height:190px;
}}

@media(max-width:900px){{
    .subscription-hero{{
        grid-template-columns:1fr;
    }}

    .subscription-hero-status{{
        width:100%;
    }}

    .subscription-details-grid{{
        grid-template-columns:repeat(2,1fr);
    }}
}}

@media(max-width:620px){{
    .subscription-hero{{
        padding:21px;
        border-radius:22px;
    }}

    .subscription-hero h2{{
        font-size:23px;
    }}

    .subscription-hero-actions{{
        display:grid;
        grid-template-columns:1fr;
    }}

    .subscription-details-grid{{
        grid-template-columns:1fr;
    }}

    .payment-history-head{{
        flex-direction:column;
    }}

    .coming-soon-badge{{
        min-width:0;
    }}
}}

@media(hover:none){{
    .subscription-main-action:hover,
    .subscription-secondary-action:hover{{
        transform:none;
    }}
}}

/* SUBSCRIPTION PRO END */


.auth-shell{{
    min-height:calc(100vh - 70px);
    display:grid;
    place-items:center;
    padding:40px 0;
}}

.auth-layout{{
    width:min(950px,100%);
    display:grid;
    grid-template-columns:.92fr 1.08fr;
    overflow:hidden;
    border:1px solid rgba(108,60,255,.13);
    border-radius:29px;
    background:#fff;
    box-shadow:0 27px 75px rgba(47,24,104,.15);
}}

.auth-visual{{
    min-height:540px;
    display:flex;
    flex-direction:column;
    justify-content:center;
    padding:42px;
    color:#fff;
    background:
        radial-gradient(
            circle at 12% 88%,
            rgba(173,130,255,.36),
            transparent 36%
        ),
        linear-gradient(
            145deg,
            #7b46f6,
            #4d1db7 56%,
            #2b0e69
        );
}}

.auth-visual h1{{
    margin:0 0 13px;
    font-size:32px;
    line-height:1.5;
}}

.auth-visual p{{
    margin:0;
    color:rgba(255,255,255,.78);
    font-size:11px;
    line-height:2;
}}

.auth-points{{
    display:grid;
    gap:9px;
    margin-top:25px;
}}

.auth-point{{
    display:flex;
    align-items:center;
    gap:9px;
    padding:10px 11px;
    border:1px solid rgba(255,255,255,.10);
    border-radius:12px;
    background:rgba(255,255,255,.07);
    font-size:9px;
}}

.auth-point::before{{
    content:"✓";
    width:24px;
    height:24px;
    display:grid;
    place-items:center;
    border-radius:8px;
    background:rgba(255,255,255,.14);
    font-weight:950;
}}

.auth-card{{
    display:flex;
    flex-direction:column;
    justify-content:center;
    padding:40px;
}}

.auth-card h2{{
    margin:0 0 8px;
    font-size:26px;
}}

.auth-card > p{{
    margin:0 0 23px;
    color:var(--muted);
    font-size:10px;
    line-height:1.9;
}}

.field{{
    display:grid;
    gap:7px;
    margin-bottom:13px;
}}

.field label{{
    font-size:10px;
    font-weight:900;
}}

.field input{{
    width:100%;
    height:47px;
    padding:10px 13px;
    border:1px solid var(--line);
    border-radius:13px;
    outline:none;
    direction:ltr;
}}

.field input:focus{{
    border-color:rgba(108,60,255,.62);
    box-shadow:0 0 0 4px rgba(108,60,255,.09);
}}

.submit{{
    width:100%;
    min-height:48px;
    margin-top:5px;
    border:0;
    border-radius:13px;
    color:#fff;
    background:linear-gradient(
        135deg,
        #8150ff,
        #551fc5
    );
    font-size:10px;
    font-weight:950;
    cursor:pointer;
}}

.app-register{{
    margin-top:18px;
    padding-top:16px;
    border-top:1px solid var(--line);
    color:var(--muted);
    font-size:9px;
    line-height:1.9;
    text-align:center;
}}

@media(max-width:900px){{
    .stats{{
        grid-template-columns:repeat(2,1fr);
    }}

    .content-grid{{
        grid-template-columns:1fr;
    }}

    .hero{{
        grid-template-columns:1fr;
    }}

    .plan-box{{
        justify-self:stretch;
        width:100%;
    }}

    .shortcuts{{
        grid-template-columns:repeat(2,1fr);
    }}

    .auth-layout{{
        grid-template-columns:1fr;
    }}

    .auth-visual{{
        min-height:auto;
        padding:30px;
    }}
}}

@media(max-width:620px){{
    .dashboard-head{{
        align-items:flex-start;
        flex-direction:column;
    }}

    .head-actions{{
        width:100%;
    }}

    .head-actions > *{{
        flex:1;
    }}

    .stats{{
        grid-template-columns:1fr;
    }}

    .shortcuts{{
        grid-template-columns:1fr 1fr;
    }}

    .subscription-card{{
        grid-template-columns:1fr;
    }}

    .subscription-card .actions{{
        display:grid;
        grid-template-columns:1fr;
    }}

    .auth-card{{
        padding:25px 20px;
    }}

    .auth-visual{{
        padding:25px 20px;
    }}

    .auth-visual h1{{
        font-size:25px;
    }}

    .top-btn.primary{{
        display:none;
    }}
}}
</style>
</head>

<body>

<header class="topbar">
    <div class="topbar-inner">
        <a class="brand" href="/">
            <img
                src="/assets/rashdyar-logo.png"
                alt="رشدیار"
            >
            <span>رشدیار</span>
        </a>

        <div class="top-actions">
            <a class="top-btn" href="/">صفحه اصلی</a>
            <a class="top-btn primary" href="/#plans">
                خرید اشتراک
            </a>
        </div>
    </div>
</header>

{body}

</body>
</html>"""


def panel_layout(
    *,
    title: str,
    subtitle: str,
    active: str,
    content: str,
    notice: str = "",
) -> str:
    body = f"""
<main class="account-shell">
    <div class="container">

        <div class="dashboard-head">
            <div>
                <h1>{esc(title)}</h1>
                <p>{esc(subtitle)}</p>
            </div>

            <div class="head-actions">
                <a class="upgrade-btn" href="/#plans">
                    ارتقای اشتراک
                </a>

                <a class="logout-btn" href="/account/logout">
                    خروج از حساب
                </a>
            </div>
        </div>

        <nav class="account-nav">
            <a
                class="{active_nav(active, 'dashboard')}"
                href="/account"
            >
                🏠 داشبورد
            </a>

            <a
                class="{active_nav(active, 'profile')}"
                href="/account/profile"
            >
                👤 حساب کاربری
            </a>

            <a
                class="{active_nav(active, 'subscription')}"
                href="/account/subscription"
            >
                💳 اشتراک
            </a>

            <a
                class="{active_nav(active, 'activity')}"
                href="/account/activity"
            >
                📊 فعالیت
            </a>

            <a
                class="{active_nav(active, 'settings')}"
                href="/account/settings"
            >
                ⚙️ تنظیمات
            </a>
        </nav>

        {notice}
        {content}

    </div>
</main>
"""

    return base_page(
        title=title,
        body=body,
    )


def build_notice(request: Request) -> str:
    success = request.query_params.get("success", "")
    error = request.query_params.get("error", "")

    if success:
        return (
            '<div class="notice success">'
            + esc(success)
            + "</div>"
        )

    if error:
        return (
            '<div class="notice error">'
            + esc(error)
            + "</div>"
        )

    return ""


# ---------------------------------------------------------
# Login
# ---------------------------------------------------------

def login_html(
    *,
    error: str = "",
    email: str = "",
) -> str:
    error_html = (
        f'<div class="notice error">{esc(error)}</div>'
        if error
        else ""
    )

    body = f"""
<main class="auth-shell">
    <div class="container">
        <section class="auth-layout">

            <div class="auth-visual">
                <h1>به حساب رشدیار وارد شو</h1>

                <p>
                    با همان ایمیل و رمزی که داخل اپلیکیشن
                    ثبت کرده‌ای وارد پنل وب شو.
                </p>

                <div class="auth-points">
                    <div class="auth-point">
                        مشاهده پلن و اعتبار حساب
                    </div>

                    <div class="auth-point">
                        مدیریت رمز عبور
                    </div>

                    <div class="auth-point">
                        دسترسی به بخش اشتراک
                    </div>
                </div>
            </div>

            <form
                class="auth-card"
                method="post"
                action="/account/login"
            >
                <h2>ورود کاربران</h2>

                <p>
                    اطلاعات ورود همان اطلاعات ثبت‌نام داخل اپ است.
                </p>

                {error_html}

                <div class="field">
                    <label for="email">ایمیل</label>
                    <input
                        id="email"
                        name="email"
                        type="email"
                        value="{esc(email)}"
                        autocomplete="email"
                        required
                    >
                </div>

                <div class="field">
                    <label for="password">رمز عبور</label>
                    <input
                        id="password"
                        name="password"
                        type="password"
                        autocomplete="current-password"
                        minlength="6"
                        required
                    >
                </div>

                <button class="submit" type="submit">
                    ورود به پنل کاربری
                </button>

                <div class="app-register">
                    ثبت‌نام حساب جدید از داخل اپلیکیشن رشدیار
                    انجام می‌شود.
                </div>
            </form>

        </section>
    </div>
</main>
"""

    return base_page(
        title="ورود کاربران",
        body=body,
    )


@router.get(
    "/account/login",
    response_class=HTMLResponse,
)
async def login_page(request: Request):
    token = get_token(request)

    if token:
        status, data = await api_get(
            "/v1/auth/me",
            token=token,
        )

        if status == 200 and data.get("success"):
            return RedirectResponse(
                "/account",
                status_code=303,
            )

    return HTMLResponse(
        login_html(
            error=request.query_params.get("error", ""),
        )
    )


@router.post("/account/login")
async def login_submit(request: Request):
    form = await request.form()

    email = str(
        form.get("email", "")
    ).strip().lower()

    password = str(
        form.get("password", "")
    )

    if not email or not password:
        return HTMLResponse(
            login_html(
                error="ایمیل و رمز عبور را کامل وارد کن.",
                email=email,
            ),
            status_code=400,
        )

    status, data = await api_post(
        "/v1/auth/login",
        json_data={
            "email": email,
            "password": password,
        },
    )

    if (
        status != 200
        or not data.get("success")
        or not data.get("token")
    ):
        message = (
            data.get("message")
            or "ایمیل یا رمز عبور اشتباه است."
        )

        return HTMLResponse(
            login_html(
                error=message,
                email=email,
            ),
            status_code=401,
        )

    response = RedirectResponse(
        "/account",
        status_code=303,
    )

    response.set_cookie(
        key=COOKIE_NAME,
        value=str(data["token"]),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )

    return response


# ---------------------------------------------------------
# Dashboard
# ---------------------------------------------------------

@router.get(
    "/account",
    response_class=HTMLResponse,
)
async def dashboard(request: Request):
    auth = await require_user(request)

    if isinstance(auth, RedirectResponse):
        return auth

    _, user = auth

    name = user.get("name") or "کاربر رشدیار"
    email = user.get("email") or ""
    plan = normalize_plan(
        str(user.get("plan") or "free")
    )
    credits = int(user.get("credits") or 0)

    created_at = normalize_date(
        str(
            user.get("created_at")
            or user.get("createdAt")
            or ""
        )
    )

    content = f"""
<section class="hero">
    <div>
        <h2>سلام {esc(name)} 👋</h2>

        <p>
            حساب وب و اپلیکیشن رشدیار به یکدیگر متصل‌اند.
            تغییرات پلن، اعتبار و رمز عبور در هر دو محیط
            اعمال می‌شوند.
        </p>
    </div>

    <div class="plan-box">
        <small>پلن فعال حساب</small>
        <strong>{esc(plan)}</strong>

        <a href="/account/subscription">
            مشاهده وضعیت اشتراک
        </a>
    </div>
</section>

<section class="stats">
    <div class="stat">
        <div class="stat-icon">⭐</div>
        <span>اعتبار باقی‌مانده</span>
        <strong>{to_persian_digits(credits)}</strong>
    </div>

    <div class="stat">
        <div class="stat-icon">🟢</div>
        <span>وضعیت حساب</span>
        <strong>فعال</strong>
    </div>

    <div class="stat email">
        <div class="stat-icon">✉️</div>
        <span>ایمیل حساب</span>
        <strong>{esc(email)}</strong>
    </div>

    <div class="stat">
        <div class="stat-icon">📅</div>
        <span>تاریخ عضویت</span>
        <strong>{esc(created_at)}</strong>
    </div>
</section>

<div class="content-grid">

    <section class="card app-download-card">
        <div class="app-download-head">
            <img
                src="/assets/rashdyar-logo.png"
                alt="اپلیکیشن رشدیار"
            >

            <div>
                <h3>دانلود اپلیکیشن رشدیار</h3>

                <p class="card-subtitle">
                    تحلیل پیج، تولید محتوا، ساخت تصویر،
                    هشتگ هوشمند و تقویم محتوا داخل اپلیکیشن
                    رشدیار انجام می‌شوند.
                </p>
            </div>
        </div>

        <div class="app-feature-list">
            <div>📊 تحلیل و بررسی پیج</div>
            <div>✍️ تولید محتوای هوشمند</div>
            <div>🎨 ساخت و ویرایش تصویر</div>
            <div>🏷️ هشتگ و ایده محتوا</div>
        </div>

        <div class="app-download-actions">
            <a
                class="download-btn primary"
                href="/site-assets/apk/app-release.apk"
                download
            >
                دانلود مستقیم APK
            </a>

            <a
                class="download-btn"
                href="/#download"
            >
                دریافت از بازار
            </a>

            <a
                class="download-btn"
                href="/#download"
            >
                Google Play
            </a>
        </div>
    </section>

    <section class="card">
        <h3>فعالیت‌های اخیر</h3>

        <p class="card-subtitle">
            تاریخچه استفاده حساب در این بخش نمایش داده خواهد شد.
        </p>

        <div class="empty-state">
            <i>📭</i>
            <strong>هنوز فعالیتی برای نمایش وجود ندارد</strong>

            <p>
                بعد از اتصال API تاریخچه، تحلیل‌ها، تولید محتوا
                و مصرف اعتبار در این قسمت نمایش داده می‌شوند.
            </p>
        </div>
    </section>

</div>
"""

    return HTMLResponse(
        panel_layout(
            title="پنل کاربری",
            subtitle="نمای کلی حساب و دسترسی سریع",
            active="dashboard",
            notice=build_notice(request),
            content=content,
        )
    )


# ---------------------------------------------------------
# Profile
# ---------------------------------------------------------

@router.get(
    "/account/profile",
    response_class=HTMLResponse,
)
async def profile_page(request: Request):
    auth = await require_user(request)

    if isinstance(auth, RedirectResponse):
        return auth

    _, user = auth

    name = user.get("name") or "ثبت نشده"
    email = user.get("email") or ""
    plan = normalize_plan(str(user.get("plan") or "free"))
    credits = int(user.get("credits") or 0)
    user_id = user.get("id") or "ثبت نشده"

    created_at = normalize_date(
        str(
            user.get("created_at")
            or user.get("createdAt")
            or ""
        )
    )

    content = f"""
<div class="content-grid">

    <section class="card">
        <h3>اطلاعات حساب</h3>

        <p class="card-subtitle">
            اطلاعات زیر مستقیماً از حساب مرکزی رشدیار دریافت شده‌اند.
        </p>

        <div class="info-list">
            <div class="info-row">
                <span>نام</span>
                <strong>{esc(name)}</strong>
            </div>

            <div class="info-row">
                <span>ایمیل</span>
                <strong>{esc(email)}</strong>
            </div>

            <div class="info-row">
                <span>شناسه کاربر</span>
                <strong>{esc(user_id)}</strong>
            </div>

            <div class="info-row">
                <span>تاریخ عضویت</span>
                <strong>{esc(created_at)}</strong>
            </div>
        </div>
    </section>

    <section class="card">
        <h3>وضعیت سرویس</h3>

        <p class="card-subtitle">
            وضعیت فعلی پلن و اعتبار حساب
        </p>

        <div class="info-list">
            <div class="info-row">
                <span>وضعیت حساب</span>
                <strong>فعال</strong>
            </div>

            <div class="info-row">
                <span>پلن فعلی</span>
                <strong>{esc(plan)}</strong>
            </div>

            <div class="info-row">
                <span>اعتبار باقی‌مانده</span>
                <strong>{to_persian_digits(credits)}</strong>
            </div>
        </div>
    </section>

</div>
"""

    return HTMLResponse(
        panel_layout(
            title="حساب کاربری",
            subtitle="اطلاعات هویتی و وضعیت حساب",
            active="profile",
            notice=build_notice(request),
            content=content,
        )
    )


# ---------------------------------------------------------
# Subscription
# ---------------------------------------------------------

@router.get(
    "/account/subscription",
    response_class=HTMLResponse,
)
async def subscription_page(request: Request):
    auth = await require_user(request)

    if isinstance(auth, RedirectResponse):
        return auth

    _, user = auth

    raw_plan = str(
        user.get("plan") or "free"
    ).strip().lower()

    plan = normalize_plan(raw_plan)
    credits = int(user.get("credits") or 0)

    def first_value(*keys: str) -> str:
        for key in keys:
            value = user.get(key)

            if value is not None and str(value).strip():
                return str(value).strip()

        return ""

    def parse_date(value: str):
        if not value:
            return None

        clean = (
            value.strip()
            .replace("Z", "+00:00")
        )

        try:
            return datetime.fromisoformat(clean)
        except ValueError:
            return None

    start_raw = first_value(
        "subscription_started_at",
        "subscription_start",
        "starts_at",
        "plan_started_at",
    )

    expires_raw = first_value(
        "subscription_expires_at",
        "subscription_end",
        "expires_at",
        "plan_expires_at",
    )

    start_date = parse_date(start_raw)
    expires_date = parse_date(expires_raw)

    start_text = (
        normalize_date(start_raw)
        if start_raw
        else "ثبت نشده"
    )

    expires_text = (
        normalize_date(expires_raw)
        if expires_raw
        else (
            "بدون تاریخ انقضا"
            if raw_plan == "free"
            else "از API دریافت نشده"
        )
    )

    remaining_days = None
    progress_percent = None

    if expires_date is not None:
        now = datetime.now(
            expires_date.tzinfo
        ) if expires_date.tzinfo else datetime.now()

        remaining_seconds = (
            expires_date - now
        ).total_seconds()

        remaining_days = max(
            0,
            int(
                (
                    remaining_seconds
                    + 86399
                ) // 86400
            ),
        )

        if start_date is not None:
            total_seconds = (
                expires_date - start_date
            ).total_seconds()

            if total_seconds > 0:
                passed_seconds = (
                    now - start_date
                ).total_seconds()

                progress_percent = max(
                    0,
                    min(
                        100,
                        int(
                            passed_seconds
                            / total_seconds
                            * 100
                        ),
                    ),
                )

    explicit_active = user.get(
        "subscription_active"
    )

    if explicit_active is None:
        explicit_active = user.get(
            "is_subscription_active"
        )

    if raw_plan == "free":
        status_text = "فعال — پلن رایگان"
        status_class = "status-active"

    elif remaining_days is not None:
        if remaining_days > 0:
            status_text = "فعال"
            status_class = "status-active"
        else:
            status_text = "منقضی‌شده"
            status_class = "status-expired"

    elif explicit_active is False:
        status_text = "غیرفعال"
        status_class = "status-expired"

    else:
        status_text = "فعال"
        status_class = "status-active"

    remaining_text = (
        to_persian_digits(
            f"{remaining_days} روز"
        )
        if remaining_days is not None
        else (
            "نامحدود"
            if raw_plan == "free"
            else "اطلاعات موجود نیست"
        )
    )

    progress_html = ""

    if progress_percent is not None:
        progress_html = f"""
        <div class="subscription-progress">
            <div class="subscription-progress-head">
                <span>مدت سپری‌شده اشتراک</span>
                <strong>
                    {to_persian_digits(progress_percent)}٪
                </strong>
            </div>

            <div class="subscription-progress-track">
                <span
                    style="width:{progress_percent}%"
                ></span>
            </div>
        </div>
        """

    current_plan_key = raw_plan

    def active_badge(
        *plan_keys: str,
    ) -> str:
        if current_plan_key in plan_keys:
            return (
                '<span class="current-plan-badge">'
                'پلن فعلی'
                '</span>'
            )

        return ""

    content = f"""
<section class="subscription-hero">

    <div class="subscription-hero-copy">
        <span class="subscription-eyebrow">
            اشتراک فعال حساب
        </span>

        <h2>{esc(plan)}</h2>

        <p>
            وضعیت اشتراک و اعتبار این حساب به‌صورت مرکزی
            بین سایت و اپلیکیشن رشدیار همگام می‌شود.
        </p>

        <div class="subscription-hero-actions">
            <a
                class="subscription-main-action"
                href="#account-plans"
            >
                تمدید یا ارتقای اشتراک
            </a>

            <a
                class="subscription-secondary-action"
                href="/"
            >
                بازگشت به سایت
            </a>
        </div>
    </div>

    <div class="subscription-hero-status">
        <div class="subscription-status-top">
            <span class="subscription-status-dot"></span>

            <strong class="{status_class}">
                {esc(status_text)}
            </strong>
        </div>

        <div class="subscription-credit-number">
            {to_persian_digits(credits)}
        </div>

        <small>اعتبار باقی‌مانده حساب</small>

        {progress_html}
    </div>

</section>

<section class="subscription-details-grid">

    <article class="subscription-detail-card">
        <i>💳</i>
        <span>پلن فعلی</span>
        <strong>{esc(plan)}</strong>
    </article>

    <article class="subscription-detail-card">
        <i>🗓️</i>
        <span>تاریخ شروع</span>
        <strong>{esc(start_text)}</strong>
    </article>

    <article class="subscription-detail-card">
        <i>⏳</i>
        <span>تاریخ پایان</span>
        <strong>{esc(expires_text)}</strong>
    </article>

    <article class="subscription-detail-card">
        <i>⌛</i>
        <span>زمان باقی‌مانده</span>
        <strong>{esc(remaining_text)}</strong>
    </article>

</section>

<section
    id="account-plans"
    class="card account-plans-section"
>
    <div class="plans-header">
        <div>
            <h3>انتخاب و ارتقای پلن</h3>

            <p class="card-subtitle">
                پس از پرداخت موفق، اشتراک روی همین حساب
                واردشده فعال می‌شود و نیازی به ورود دوباره
                ایمیل نیست.
            </p>
        </div>
    </div>

    <div class="account-plans">

        <article class="account-plan">
            {active_badge("free")}

            <div class="account-plan-head">
                <small>برای آشنایی با رشدیار</small>
                <h3>رایگان</h3>
            </div>

            <div class="account-plan-price">
                رایگان
            </div>

            <div class="account-plan-old-price"></div>

            <div class="account-plan-meta">
                حساب پایه
            </div>

            <ul>
                <li>۳ اعتبار اولیه</li>
                <li>تحلیل پایه پیج</li>
                <li>دسترسی محدود به ابزارها</li>
                <li>امکان ارتقا در هر زمان</li>
            </ul>

            <span class="account-plan-btn disabled">
                پلن پایه
            </span>
        </article>

        <article class="account-plan featured">
            {active_badge(
                "monthly",
                "pro",
                "professional",
            )}

            <span class="popular-badge">
                پرفروش‌ترین
            </span>

            <div class="account-plan-head">
                <small>
                    مناسب تولیدکنندگان محتوا
                </small>

                <h3>حرفه‌ای ماهانه</h3>
            </div>

            <div class="account-plan-price">
                ۲۹۹,۰۰۰
                <small>تومان</small>
            </div>

            <div class="account-plan-old-price">
                ۳۹۹,۰۰۰ تومان
            </div>

            <div class="account-plan-meta">
                ۳۰ روز اعتبار
            </div>

            <ul>
                <li>تحلیل کامل پیج</li>
                <li>تولید محتوای هوشمند</li>
                <li>سهمیه بیشتر ساخت تصویر</li>
                <li>برنامه رشد اختصاصی</li>
            </ul>

            <a
                class="account-plan-btn primary"
                href="/account/buy/monthly"
            >
                خرید اشتراک ماهانه
            </a>
        </article>

        <article class="account-plan">
            {active_badge("quarterly")}

            <span class="saving-badge">
                اقتصادی
            </span>

            <div class="account-plan-head">
                <small>صرفه‌جویی بیشتر</small>
                <h3>حرفه‌ای سه‌ماهه</h3>
            </div>

            <div class="account-plan-price">
                ۷۴۹,۰۰۰
                <small>تومان</small>
            </div>

            <div class="account-plan-old-price">
                ۱,۱۹۷,۰۰۰ تومان
            </div>

            <div class="account-plan-meta">
                ۹۰ روز اعتبار
            </div>

            <ul>
                <li>تمام امکانات حرفه‌ای</li>
                <li>اعتبار ۹۰ روزه</li>
                <li>اولویت پشتیبانی</li>
                <li>هزینه ماهانه کمتر</li>
            </ul>

            <a
                class="account-plan-btn"
                href="/account/buy/quarterly"
            >
                خرید اشتراک سه‌ماهه
            </a>
        </article>

    </div>
</section>

<section class="card payment-history-card">
    <div class="payment-history-head">
        <div>
            <h3>تاریخچه پرداخت‌ها</h3>

            <p class="card-subtitle">
                خریدهای موفق، ناموفق و در انتظار پرداخت
                این حساب در این بخش نمایش داده می‌شوند.
            </p>
        </div>

        <span class="coming-soon-badge">
            اتصال API در مرحله بعد
        </span>
    </div>

    <div class="empty-state compact-empty">
        <i>🧾</i>
        <strong>هنوز تراکنشی ثبت نشده است</strong>

        <p>
            بعد از اتصال تاریخچه پرداخت، مبلغ، پلن،
            درگاه، شماره پیگیری و تاریخ خرید نمایش
            داده خواهد شد.
        </p>
    </div>
</section>
"""

    return HTMLResponse(
        panel_layout(
            title="اشتراک",
            subtitle="مدیریت پلن، اعتبار و پرداخت‌ها",
            active="subscription",
            notice=build_notice(request),
            content=content,
        )
    )


# ---------------------------------------------------------
# Activity
# ---------------------------------------------------------

@router.get(
    "/account/activity",
    response_class=HTMLResponse,
)
async def activity_page(request: Request):
    auth = await require_user(request)

    if isinstance(auth, RedirectResponse):
        return auth

    content = """
<section class="card">
    <h3>تاریخچه فعالیت حساب</h3>

    <p class="card-subtitle">
        تحلیل‌ها، تولید محتوا، تصاویر و مصرف اعتبار
    </p>

    <div class="empty-state">
        <i>📊</i>
        <strong>هنوز تاریخچه فعالیت متصل نشده است</strong>

        <p>
            این صفحه آماده است، اما برای نمایش داده واقعی باید
            Endpoint تاریخچه استفاده و پروژه‌های کاربر به API
            مرکزی اضافه شود.
        </p>
    </div>
</section>
"""

    return HTMLResponse(
        panel_layout(
            title="فعالیت",
            subtitle="تاریخچه استفاده از ابزارهای رشدیار",
            active="activity",
            notice=build_notice(request),
            content=content,
        )
    )


# ---------------------------------------------------------
# Settings
# ---------------------------------------------------------

@router.get(
    "/account/settings",
    response_class=HTMLResponse,
)
async def settings_page(request: Request):
    auth = await require_user(request)

    if isinstance(auth, RedirectResponse):
        return auth

    content = """
<div class="content-grid">

    <section class="card">
        <h3>تغییر رمز عبور</h3>

        <p class="card-subtitle">
            رمز جدید در اپلیکیشن و پنل وب هم‌زمان تغییر می‌کند.
        </p>

        <form
            class="password-form"
            method="post"
            action="/account/change-password"
        >
            <input
                type="password"
                name="current_password"
                placeholder="رمز عبور فعلی"
                autocomplete="current-password"
                minlength="6"
                required
            >

            <input
                type="password"
                name="new_password"
                placeholder="رمز عبور جدید"
                autocomplete="new-password"
                minlength="6"
                required
            >

            <input
                type="password"
                name="confirm_password"
                placeholder="تکرار رمز عبور جدید"
                autocomplete="new-password"
                minlength="6"
                required
            >

            <button type="submit">
                ذخیره رمز عبور جدید
            </button>
        </form>
    </section>

    <section class="card">
        <h3>امنیت حساب</h3>

        <p class="card-subtitle">
            مدیریت نشست‌ها و دستگاه‌های متصل
        </p>

        <div class="empty-state">
            <i>🔐</i>
            <strong>مدیریت دستگاه‌ها هنوز فعال نیست</strong>

            <p>
                برای خروج از همه دستگاه‌ها باید سیستم نشست‌های
                کاربر و ابطال Tokenها به API اضافه شود.
            </p>
        </div>
    </section>

</div>
"""

    return HTMLResponse(
        panel_layout(
            title="تنظیمات",
            subtitle="رمز عبور و امنیت حساب",
            active="settings",
            notice=build_notice(request),
            content=content,
        )
    )


@router.post("/account/change-password")
async def change_password(request: Request):
    auth = await require_user(request)

    if isinstance(auth, RedirectResponse):
        return auth

    token, _ = auth
    form = await request.form()

    current_password = str(
        form.get("current_password", "")
    )

    new_password = str(
        form.get("new_password", "")
    )

    confirm_password = str(
        form.get("confirm_password", "")
    )

    if len(new_password) < 6:
        return RedirectResponse(
            "/account/settings?error="
            + quote_plus(
                "رمز جدید باید حداقل ۶ کاراکتر باشد."
            ),
            status_code=303,
        )

    if new_password != confirm_password:
        return RedirectResponse(
            "/account/settings?error="
            + quote_plus(
                "تکرار رمز عبور با رمز جدید مطابقت ندارد."
            ),
            status_code=303,
        )

    status, data = await api_post(
        "/v1/auth/change-password",
        token=token,
        json_data={
            "current_password": current_password,
            "new_password": new_password,
        },
    )

    if status != 200 or not data.get("success"):
        message = (
            data.get("message")
            or "تغییر رمز عبور انجام نشد."
        )

        return RedirectResponse(
            "/account/settings?error="
            + quote_plus(message),
            status_code=303,
        )

    response = RedirectResponse(
        "/account/settings?success="
        + quote_plus(
            "رمز عبور با موفقیت تغییر کرد."
        ),
        status_code=303,
    )

    new_token = str(data.get("token") or token)

    response.set_cookie(
        key=COOKIE_NAME,
        value=new_token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )

    return response



@router.get("/account/buy/monthly")
async def account_buy_monthly(request: Request):
    auth = await require_user(request)

    if isinstance(auth, RedirectResponse):
        return auth

    _, user = auth

    email = str(user.get("email") or "").strip()

    if not email:
        return RedirectResponse(
            "/account/subscription?error="
            + quote_plus("ایمیل حساب پیدا نشد."),
            status_code=303,
        )

    return RedirectResponse(
        "/buy/pro-monthly?email=" + quote_plus(email),
        status_code=303,
    )


@router.get("/account/buy/quarterly")
async def account_buy_quarterly(request: Request):
    auth = await require_user(request)

    if isinstance(auth, RedirectResponse):
        return auth

    _, user = auth

    email = str(user.get("email") or "").strip()

    if not email:
        return RedirectResponse(
            "/account/subscription?error="
            + quote_plus("ایمیل حساب پیدا نشد."),
            status_code=303,
        )

    return RedirectResponse(
        "/buy/pro-quarterly?email=" + quote_plus(email),
        status_code=303,
    )


@router.get("/account/logout")
async def logout():
    response = RedirectResponse(
        "/account/login",
        status_code=303,
    )

    response.delete_cookie(
        COOKIE_NAME,
        path="/",
    )

    return response

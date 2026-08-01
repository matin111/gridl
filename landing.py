from __future__ import annotations

import html
import json
import urllib.parse

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from subscription_admin_api import database, isoformat, utc_now


router = APIRouter()


DEFAULT_SETTINGS = {
    "site_title": "دستیار هوشمند رشد و تولید محتوا",
    "site_subtitle": "تحلیل پیج، کشف ترند، ساخت سناریو و تصویر، برنامه‌ریزی انتشار و مدیریت رشد؛ در یک اپ فارسی.",
    "primary_button_text": "شروع رایگان",
    "secondary_button_text": "مشاهده امکانات",
    "download_url": "#plans",
    "announcement": "",
    "show_announcement": "0",
    "about_title": "رشدیار برای اجرای بهتر محتوا ساخته شده",
    "about_text": "رشدیار ابزارهای پراکنده تولید محتوا را در یک مسیر ساده و فارسی کنار هم قرار می‌دهد؛ تا تصمیم‌گیری، ساخت و انتشار محتوا سریع‌تر و منظم‌تر شود.",
    "about_mission": "از تحلیل وضعیت فعلی تا پیشنهاد قدم بعدی، تمرکز رشدیار روی خروجی قابل اجراست.",
    "contact_title": "برای انتخاب پلن نیاز به راهنمایی داری؟",
    "contact_text": "پیامت مستقیم در پنل مدیریت ثبت می‌شود و تیم رشدیار پاسخ می‌دهد.",
    "support_phone": "",
    "support_email": "",
    "support_telegram": "",
    "support_instagram": "",
    "support_hours": "پاسخ‌گویی هر روز از ساعت ۹ تا ۲۱",
    "footer_text": "رشدیار؛ ابزار هوشمند رشد و تولید محتوا",
}


def esc(value) -> str:
    return html.escape(str(value or ""))


def ensure_landing_tables(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS landing_settings(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS subscription_plans(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            subtitle TEXT NOT NULL DEFAULT '',
            price INTEGER NOT NULL DEFAULT 0,
            compare_price INTEGER NOT NULL DEFAULT 0,
            duration_days INTEGER NOT NULL DEFAULT 30,
            badge TEXT NOT NULL DEFAULT '',
            features_json TEXT NOT NULL DEFAULT '[]',
            button_text TEXT NOT NULL DEFAULT 'انتخاب پلن',
            is_featured INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            display_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS landing_contact_messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT '',
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            ip_address TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    now = isoformat(utc_now())
    for key, value in DEFAULT_SETTINGS.items():
        connection.execute(
            """
            INSERT INTO landing_settings(key,value,updated_at)
            VALUES(?,?,?)
            ON CONFLICT(key) DO NOTHING
            """,
            (key, value, now),
        )


def load_landing_data():
    with database() as connection:
        ensure_landing_tables(connection)
        settings_rows = connection.execute(
            "SELECT key,value FROM landing_settings"
        ).fetchall()
        plans = connection.execute(
            """
            SELECT * FROM subscription_plans
            WHERE is_active=1
            ORDER BY display_order,id
            """
        ).fetchall()

    settings = DEFAULT_SETTINGS.copy()
    settings.update(
        {
            str(row["key"]): str(row["value"] or "")
            for row in settings_rows
        }
    )
    return settings, plans


def plan_features(raw_value) -> list[str]:
    try:
        value = json.loads(raw_value or "[]")
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
    except Exception:
        pass
    return []


def money(value) -> str:
    return f"{int(value or 0):,}".replace(",", "٬")


def build_plans_html(plans) -> str:
    result = []

    for plan in plans:
        featured = " featured" if int(plan["is_featured"] or 0) else ""
        badge = (
            f'<span class="plan-badge">{esc(plan["badge"])}</span>'
            if plan["badge"]
            else ""
        )
        price = (
            "رایگان"
            if int(plan["price"] or 0) == 0
            else f'{money(plan["price"])} <small>تومان</small>'
        )
        old_price = (
            f'<del>{money(plan["compare_price"])} تومان</del>'
            if int(plan["compare_price"] or 0) > int(plan["price"] or 0)
            else ""
        )
        items = "".join(
            f"<li><span>✓</span>{esc(item)}</li>"
            for item in plan_features(plan["features_json"])
        )

        result.append(
            f"""
            <article class="price-card{featured}">
              {badge}
              <p class="plan-eyebrow">{esc(plan["subtitle"])}</p>
              <h3>{esc(plan["title"])}</h3>
              <div class="plan-price">{price}</div>
              <div class="old-price">{old_price}</div>
              <p class="plan-duration">{int(plan["duration_days"] or 30)} روز اعتبار</p>
              <ul>{items}</ul>
              <a href="/buy/{esc(plan["slug"])}">{esc(plan["button_text"])}</a>
            </article>
            """
        )

    return "".join(result)


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page(request: Request):

    s = {}

    try:
        s = get_landing_settings()
    except Exception:
        pass


    # Load download links from app_settings
    try:
        with database() as connection:
            rows = connection.execute(
                '''
                SELECT key,value
                FROM app_settings
                WHERE key IN (
                    'apk_url',
                    'market_url',
                    'google_play_url'
                )
                '''
            ).fetchall()

        for row in rows:
            s[row["key"]] = row["value"]

    except Exception:
        pass
    settings, plans = load_landing_data()

    announcement = (
        f'<div class="announcement">{esc(settings["announcement"])}</div>'
        if settings["show_announcement"] == "1" and settings["announcement"]
        else ""
    )
    flash = (
        '<div class="flash">پیامت ثبت شد؛ به‌زودی پاسخ می‌دهیم.</div>'
        if request.query_params.get("sent") == "1"
        else ""
    )

    support_links = []
    if settings["support_phone"]:
        support_links.append(
            f'<a href="tel:{esc(settings["support_phone"])}">☎ {esc(settings["support_phone"])}</a>'
        )
    if settings["support_email"]:
        support_links.append(
            f'<a href="mailto:{esc(settings["support_email"])}">✉ {esc(settings["support_email"])}</a>'
        )
    if settings["support_telegram"]:
        support_links.append(
            f'<a href="{esc(settings["support_telegram"])}" target="_blank" rel="noopener">تلگرام پشتیبانی ↗</a>'
        )
    if settings["support_instagram"]:
        support_links.append(
            f'<a href="{esc(settings["support_instagram"])}" target="_blank" rel="noopener">اینستاگرام رشدیار ↗</a>'
        )

    return HTMLResponse(
        f"""<!doctype html>
<html lang="fa" dir="rtl">
<head><link rel="icon" type="image/png" href="/assets/rashdyar-logo.png">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="{esc(settings["site_subtitle"])}">
<meta property="og:title" content="{esc(settings["site_title"])} | رشدیار">
<meta property="og:description" content="{esc(settings["site_subtitle"])}">
<meta property="og:type" content="website">
<meta property="og:url" content="{esc(str(request.url))}">
<meta name="theme-color" content="#6c3cff">
<title>{esc(settings["site_title"])} | رشدیار</title>
<script type="application/ld+json">
{{
  "@context":"https://schema.org",
  "@type":"SoftwareApplication",
  "name":"رشدیار",
  "applicationCategory":"BusinessApplication",
  "operatingSystem":"Android",
  "description":{json.dumps(settings["site_subtitle"], ensure_ascii=False)}
}}
</script>
<style>
:root {{
  --ink:#14111b;
  --muted:#736d7b;
  --page:#fbfaff;
  --card:#ffffff;
  --card-2:#f7f4fd;
  --line:#e9e4f2;
  --purple:#6c3cff;
  --purple-2:#8b63ff;
  --purple-dark:#3f168f;
  --purple-soft:#f1ecff;
  --lime:#dfff8f;
  --green:#1ab87a;
  --danger:#e14f6d;
  --shadow:0 24px 80px rgba(55,31,110,.11);
  --shadow-soft:0 14px 42px rgba(55,31,110,.065);
}}
html[data-theme="dark"] {{
  --ink:#f6f2ff;
  --muted:#b8afc6;
  --page:#0f0c15;
  --card:#17121f;
  --card-2:#21192d;
  --line:#2c2438;
  --purple-soft:#261c3a;
  --shadow:0 24px 80px rgba(0,0,0,.28);
  --shadow-soft:0 14px 42px rgba(0,0,0,.20);
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{
  margin:0;color:var(--ink);
  background:
    radial-gradient(circle at 82% 1%,rgba(108,60,255,.12),transparent 24%),
    radial-gradient(circle at 8% 30%,rgba(182,158,255,.10),transparent 20%),
    var(--page);
  font-family:Tahoma,"Segoe UI",Arial,sans-serif;
  line-height:1.15;overflow-x:hidden;transition:background .25s,color .25s
}}
a{{color:inherit;text-decoration:none}}
img{{display:block;max-width:100%}}
button,input,textarea,select{{font:inherit}}
.container{{width:min(1180px,calc(100% - 48px));margin-inline:auto;}}
.announcement{{padding:8px 16px;background:#14111b;color:#fff;text-align:center;font-size:12px}}
.site-header{{
  position:sticky;top:0;z-index:80;
  background:color-mix(in srgb,var(--card) 84%,transparent);
  border-bottom:1px solid color-mix(in srgb,var(--line) 84%,transparent);
  backdrop-filter:blur(20px)
}}
.nav{{min-height:74px;display:flex;align-items:center;justify-content:space-between;gap:24px}}
.brand{{display:flex;align-items:center;gap:10px;font-size:20px;font-weight:950}}
.brand-mark{{
  width:43px;height:43px;display:grid;place-items:center;border-radius:15px;color:#fff;
  background:linear-gradient(145deg,var(--purple),var(--purple-dark));box-shadow:0 12px 28px rgba(108,60,255,.24)
}}
.nav-links{{display:flex;align-items:center;gap:23px;font-size:12px;font-weight:850}}
.nav-links a:hover{{color:var(--purple)}}
.nav-actions{{display:flex;align-items:center;gap:8px}}
.nav-login,.theme-toggle{{
  padding:9px 13px;border:1px solid var(--line);border-radius:12px;background:var(--card);color:var(--ink);font-size:12px;font-weight:850
}}
.theme-toggle{{width:42px;height:42px;padding:0;cursor:pointer}}
.nav-start{{padding:10px 17px;border-radius:12px;color:#fff;background:linear-gradient(135deg,var(--purple),var(--purple-dark));font-size:12px;font-weight:900}}
.menu-button{{display:none;width:42px;height:42px;border:1px solid var(--line);border-radius:13px;background:var(--card);color:var(--ink)}}

.hero{{padding:42px 0 28px;padding-top:18px;}}
.hero-shell{{
  position:relative;overflow:visible;
  display:grid;grid-template-columns:minmax(0,1.02fr) minmax(410px,.98fr);
  min-height:480px;border:1px solid rgba(108,60,255,.14);border-radius:40px;
  background:radial-gradient(circle at 76% 22%,rgba(124,92,255,.27),transparent 43%),radial-gradient(circle at 18% 82%,rgba(108,60,255,.15),transparent 48%),linear-gradient(135deg,#faf8ff 0%,#efe9ff 55%,#e7ddff 100%);
  box-shadow:var(--shadow);isolation:isolate;margin-top:34px;}}
.hero-shell:before{{
  content:"";position:absolute;inset:0;
  background-image:radial-gradient(rgba(108,60,255,.18) 1px,transparent 1px);
  background-size:24px 24px;opacity:.17;mask-image:linear-gradient(90deg,transparent,#000,transparent)
}}
.hero-copy{{position:relative;z-index:4;display:flex;flex-direction:column;justify-content:center;padding:18px 42px;align-self:center;height:auto;}}
.hero-kicker{{
  width:max-content;max-width:100%;display:inline-flex;align-items:center;gap:8px;padding:7px 11px;border-radius:999px;
  color:var(--purple);background:var(--purple-soft);font-size:11px;font-weight:900
}}
.hero h1{{margin:13px 0 11px;font-size:clamp(28px,2.35vw,40px);font-weight:900;line-height:1.22;letter-spacing:-.6px;max-width:530px;}}
.hero h1 strong{{display:block;color:var(--purple)}}
.hero-lead{{max-width:530px;margin:0;color:var(--muted);font-size:13px;line-height:1.9;}}
.hero-actions{{display:flex;gap:9px;flex-wrap:wrap;margin-top:17px;}}
.btn-primary,.btn-secondary{{min-height:43px;display:inline-flex;align-items:center;justify-content:flex-start;padding:9px 16px;border-radius:12px;font-size:12px;font-weight:900}}
.btn-primary{{color:#fff;background:linear-gradient(135deg,var(--purple),var(--purple-dark));box-shadow:0 16px 36px rgba(108,60,255,.23)}}
.btn-secondary{{border:1px solid var(--line);background:var(--card)}}
.hero-trust{{display:flex;flex-wrap:wrap;gap:11px;margin-top:15px;color:var(--muted);font-size:10px;font-weight:800}}
.hero-trust span:before{{content:"✓";margin-left:5px;color:var(--green)}}

.visual-stage{{position:relative;z-index:5;min-height:480px;direction:ltr;perspective:1300px;overflow:visible;transform-style:preserve-3d;isolation:isolate;}}
.visual-glow{{position:absolute;inset:18% 4% 4%;border-radius:50%;background:radial-gradient(circle,rgba(108,60,255,.30),transparent 65%);filter:blur(12px);animation:pulse 4s ease-in-out infinite}}
.phone{{
  position:absolute;bottom:26px;padding:8px;border-radius:42px;background:#15121a;box-shadow:0 28px 65px rgba(34,22,57,.25);overflow:hidden;
  transition:transform .25s ease;transform-style:preserve-3d;}}
.phone img{{width:100%;border-radius:34px}}
.phone-main{{z-index:8!important;left:50%;width:232px;transform:translateX(-50%) translateY(0);bottom:-8px;filter:drop-shadow(0 26px 38px rgba(56,32,140,.28));}}
.phone-left{{z-index:3!important;left:2%;bottom:12px;width:182px;transform:rotate(-9deg) rotateY(7deg) translateY(6px);filter:drop-shadow(0 18px 28px rgba(40,22,110,.20));}}
.phone-right{{z-index:3!important;right:0;bottom:12px;width:182px;transform:rotate(9deg) rotateY(-7deg) translateY(6px);filter:drop-shadow(0 18px 28px rgba(40,22,110,.20));}}
.float-note{{
  position:absolute;z-index:60!important;min-width:150px;padding:13px 15px;border:1px solid rgba(108,60,255,.25);
  border-radius:16px;background:linear-gradient(145deg,rgba(255,255,255,.98) 0%,rgba(240,233,255,.98) 100%);backdrop-filter:blur(12px);box-shadow:0 16px 38px rgba(76,42,175,.22);cursor:pointer;overflow:visible;pointer-events:auto;transition:transform .22s ease,box-shadow .22s ease,background .22s ease;}}
.float-note b{{display:block;color:var(--purple);font-size:17px}}
.float-note span{{color:var(--muted);font-size:10px}}
.note-one{{top:85px;left:0}}.note-two{{top:180px;right:-4px}}
.hero-metrics{{display:grid;grid-template-columns:repeat(4,1fr);margin-top:16px;border:1px solid var(--line);border-radius:22px;background:var(--card);box-shadow:var(--shadow-soft)}}
.metric{{padding:20px;text-align:center}}.metric + .metric{{border-right:1px solid var(--line)}}
.metric b{{display:block;color:var(--purple);font-size:21px}}.metric span{{color:var(--muted);font-size:10px}}

.section{{padding:58px 0;}}
.section-head{{max-width:760px;margin:0 auto 31px;text-align:center;margin-bottom:26px;}}
.section-head small{{color:var(--purple);font-size:11px;font-weight:900}}
.section-head h2{{margin:7px 0 8px;font-size:clamp(25px,2.15vw,34px);line-height:1.28;letter-spacing:-.4px;}}
.section-head p{{margin:0;color:var(--muted);font-size:12px;line-height:1.85;max-width:650px;}}

.story{{display:grid;grid-template-columns:.78fr 1.22fr;gap:18px;align-items:stretch}}
.story-copy{{padding:30px;border:1px solid var(--line);border-radius:28px;background:var(--card);box-shadow:var(--shadow-soft)}}
.story-copy small{{color:var(--purple);font-weight:900}}.story-copy h2{{margin:8px 0 10px;font-size:clamp(25px,2.15vw,34px);line-height:1.3;}}
.story-copy p{{margin:0;color:var(--muted);font-size:12px;line-height:1.85;}}
.story-points{{display:grid;gap:9px;margin-top:20px}}
.story-point{{display:flex;gap:10px;align-items:flex-start;padding:12px;border-radius:15px;background:var(--card-2)}}
.story-point b{{width:28px;height:28px;display:grid;place-items:center;flex:0 0 auto;border-radius:9px;background:var(--purple);color:#fff}}
.story-point span{{font-size:11px}}
.story-visual{{position:relative;overflow:hidden;min-height:420px;border-radius:28px;background:linear-gradient(145deg,#231633,#0e0b13);box-shadow:var(--shadow)}}
.story-visual:before{{content:"";position:absolute;width:330px;height:330px;left:-80px;bottom:-110px;border-radius:50%;background:radial-gradient(circle,#6c3cff,transparent 68%)}}
.story-visual img{{position:absolute;bottom:-30px;left:50%;width:255px;padding:7px;border-radius:38px;background:#17131e;transform:translateX(-50%);box-shadow:0 30px 60px rgba(0,0,0,.4)}}
.story-card{{position:absolute;padding:13px 14px;border-radius:17px;background:rgba(255,255,255,.90);border:1px solid rgba(255,255,255,.28);box-shadow:var(--shadow-soft)}}
.story-card b{{display:block;color:var(--purple);font-size:14px}}.story-card span{{color:#736d7b;font-size:9px}}
.story-a{{top:45px;right:35px}}.story-b{{bottom:45px;left:32px}}

.bento{{display:grid;grid-template-columns:1.05fr .95fr .95fr;grid-template-rows:250px 220px;gap:16px}}
.bento-card{{position:relative;overflow:hidden;padding:20px;border:1px solid var(--line);border-radius:25px;background:var(--card);box-shadow:var(--shadow-soft)}}
.bento-card h3{{margin:12px 0 6px;font-size:17px;line-height:1.45;}}.bento-card p{{max-width:420px;margin:0;color:var(--muted);font-size:11px;line-height:1.8;}}
.bento-label{{color:var(--purple);font-size:10px;font-weight:950}}
.bento-main{{grid-row:1/3;color:#fff;background:linear-gradient(155deg,#211630,#0e0b13)}}
.bento-main p{{color:#cfc8d8}}.bento-main img{{position:absolute;left:-18px;bottom:-90px;width:260px;padding:7px;border-radius:36px;background:#17131e;transform:rotate(-6deg);box-shadow:0 25px 50px rgba(0,0,0,.34)}}
.bento-accent{{background:linear-gradient(145deg,var(--lime),#f0ffc7);color:#14111b}}
.bento-purple{{color:#fff;background:linear-gradient(145deg,#7548ff,#4218b1)}}.bento-purple p{{color:#e6ddff}}
.bento-mini-visual{{position:absolute;left:20px;bottom:18px;width:95px;height:68px;border-radius:14px;background:linear-gradient(145deg,#f0ebff,#fff);box-shadow:0 10px 25px rgba(80,45,150,.09)}}
.bento-mini-visual:before,.bento-mini-visual:after{{content:"";position:absolute;bottom:12px;width:12px;border-radius:5px 5px 0 0;background:var(--purple)}}
.bento-mini-visual:before{{height:25px;left:24px}}.bento-mini-visual:after{{height:42px;left:47px}}

.demo-shell{{display:grid;grid-template-columns:.85fr 1.15fr;gap:18px;padding:21px;border:1px solid var(--line);border-radius:30px;
  background:linear-gradient(145deg,var(--card),var(--card-2));box-shadow:var(--shadow-soft)}}
.demo-controls,.demo-output{{padding:23px;border-radius:22px;background:var(--card);border:1px solid var(--line)}}
.demo-controls h3,.demo-output h3{{margin:0 0 15px;font-size:22px}}
.demo-controls label{{display:block;margin:12px 0 5px;font-size:11px;font-weight:900}}
.demo-controls input,.demo-controls select{{width:100%;padding:11px 12px;border:1px solid var(--line);border-radius:11px;background:var(--card);color:var(--ink)}}
.demo-controls button{{width:100%;margin-top:14px;min-height:46px;border:0;border-radius:12px;color:#fff;background:linear-gradient(135deg,var(--purple),var(--purple-dark));font-weight:900;cursor:pointer}}
.demo-output-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}
.demo-result{{min-height:110px;padding:14px;border-radius:15px;background:var(--card-2)}}
.demo-result b{{display:block;color:var(--purple);font-size:11px}}.demo-result p{{margin:7px 0 0;color:var(--muted);font-size:11px}}

.gallery-shell{{position:relative;padding:31px;border:1px solid var(--line);border-radius:31px;background:radial-gradient(circle at 50% 110%,rgba(108,60,255,.16),transparent 42%),var(--card);box-shadow:var(--shadow-soft);overflow:hidden}}
.gallery-track{{display:grid;grid-template-columns:repeat(5,minmax(170px,1fr));gap:14px;align-items:end}}
.gallery-phone{{padding:7px;border-radius:29px;background:#17131e;box-shadow:0 18px 40px rgba(36,23,59,.14);transition:.24s;cursor:pointer}}
.gallery-phone:hover{{transform:translateY(-10px) scale(1.015);box-shadow:0 27px 58px rgba(67,35,135,.20)}}
.gallery-phone:nth-child(3){{transform:translateY(-18px)}}.gallery-phone:nth-child(3):hover{{transform:translateY(-28px) scale(1.015)}}
.gallery-phone img{{border-radius:23px}}
.lightbox{{position:fixed;inset:0;z-index:120;display:none;align-items:center;justify-content:flex-start;padding:20px;background:rgba(10,8,15,.84);backdrop-filter:blur(8px)}}
.lightbox.open{{display:flex}}.lightbox img{{max-height:88vh;border-radius:28px;box-shadow:0 30px 90px rgba(0,0,0,.45)}}
.lightbox-close{{position:absolute;top:20px;left:20px;width:44px;height:44px;border:0;border-radius:50%;background:#fff;color:#111;font-size:20px;cursor:pointer}}

.timeline-wrap{{display:grid;grid-template-columns:1.06fr .94fr;gap:18px}}
.timeline-card,.outcome-card{{border:1px solid var(--line);border-radius:27px;background:var(--card);box-shadow:var(--shadow-soft)}}
.timeline-card{{padding:29px}}.timeline-card h3,.outcome-card h3{{margin:0 0 20px;font-size:24px}}
.timeline{{position:relative;display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}
.timeline:before{{content:"";position:absolute;top:20px;right:11%;left:11%;height:2px;background:linear-gradient(90deg,#d9ccff,var(--purple),#d9ccff)}}
.timeline-step{{position:relative;z-index:2;text-align:center}}.timeline-number{{width:40px;height:40px;display:grid;place-items:center;margin:0 auto 10px;border-radius:50%;color:#fff;background:var(--purple);box-shadow:0 0 0 7px color-mix(in srgb,var(--purple-soft) 82%,transparent);font-weight:950}}
.timeline-step b{{display:block;font-size:12px}}.timeline-step span{{color:var(--muted);font-size:9px}}
.outcome-card{{position:relative;overflow:hidden;padding:30px;color:#fff;background:radial-gradient(circle at 15% 90%,rgba(255,255,255,.21),transparent 27%),linear-gradient(145deg,#7344fa,#3c159e)}}
.outcome-card p{{color:#e8e0f5;font-size:12px}}.outcome-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:24px}}
.outcome-grid div{{padding:15px 9px;border-radius:15px;background:rgba(255,255,255,.12);text-align:center}}.outcome-grid b{{display:block;font-size:19px}}.outcome-grid span{{font-size:9px;opacity:.75}}

.compare-wrap{{overflow:auto;border:1px solid var(--line);border-radius:26px;background:var(--card);box-shadow:var(--shadow-soft)}}
.compare-table{{width:100%;min-width:760px;border-collapse:collapse}}
.compare-table th,.compare-table td{{padding:11px;text-align:center;border-bottom:1px solid var(--line);font-size:10px;}}
.compare-table th:first-child,.compare-table td:first-child{{text-align:right;font-weight:900}}
.compare-table th{{background:var(--card-2);font-size:10px;padding:11px;}}.compare-table .best{{color:#fff;background:linear-gradient(145deg,#7548ff,#4218b1)}}
.yes{{color:var(--green);font-weight:950}}.no{{color:var(--danger);font-weight:950}}

.recommender{{display:grid;grid-template-columns:.9fr 1.1fr;gap:18px;padding:21px;border:1px solid var(--line);border-radius:28px;background:var(--card);box-shadow:var(--shadow-soft)}}
.recommender h3{{margin:0 0 12px;font-size:18px;}}.range-row{{margin:15px 0}}.range-row label{{display:flex;justify-content:space-between;font-size:11px;font-weight:900}}
.range-row input{{width:100%;accent-color:var(--purple)}}.recommendation{{display:flex;flex-direction:column;justify-content:flex-start;padding:22px;border-radius:20px;color:#fff;background:linear-gradient(145deg,#6c3cff,#3b148f)}}
.recommendation small{{opacity:.8}}.recommendation b{{display:block;margin:5px 0;font-size:28px}}.recommendation p{{margin:0;color:#e8e0f5;font-size:11px}}

.pricing{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;align-items:stretch}}
.price-card{{position:relative;display:flex;flex-direction:column;min-height:490px;padding:22px 19px;border:1px solid var(--line);border-radius:25px;background:var(--card);box-shadow:var(--shadow-soft)}}
.price-card.featured{{color:#fff;border-color:transparent;background:radial-gradient(circle at 50% 0,rgba(255,255,255,.15),transparent 30%),linear-gradient(160deg,#34214e,#17131e);box-shadow:var(--shadow);transform:translateY(-9px)}}
.plan-badge{{position:absolute;top:-13px;right:22px;padding:5px 11px;border-radius:999px;color:#fff;background:var(--purple);font-size:10px;font-weight:900}}
.plan-eyebrow{{min-height:42px;margin:0;color:var(--muted);font-size:11px}}.featured .plan-eyebrow,.featured .plan-duration,.featured .old-price{{color:#cfc6d8}}
.price-card h3{{margin:6px 0;font-size:18px;line-height:1.4;}}.plan-price{{color:var(--purple);font-size:31px;font-weight:950}}.featured .plan-price{{color:#fff}}
.plan-price small,.old-price,.plan-duration{{font-size:10px}}.old-price{{min-height:21px;color:#999}}.plan-duration{{color:var(--muted)}}
.price-card ul{{flex:1;display:grid;align-content:start;gap:9px;margin:21px 0;padding:0;list-style:none;font-size:12px}}
.price-card li span{{margin-left:7px;color:var(--purple)}}.featured li span{{color:#b895ff}}
.price-card>a{{min-height:47px;display:grid;place-items:center;border-radius:13px;color:#fff;background:var(--ink);font-size:12px;font-weight:900}}.featured>a{{background:linear-gradient(135deg,#8d5cff,#6331e0)}}

.trust-faq{{display:grid;grid-template-columns:.9fr 1.1fr;gap:18px}}
.trust-card,.faq-card{{padding:27px;border:1px solid var(--line);border-radius:25px;background:var(--card);box-shadow:var(--shadow-soft)}}
.trust-card h3,.faq-card h3{{margin:0 0 17px;font-size:23px}}
.trust-item{{padding:15px;border-radius:16px;background:var(--card-2)}}.trust-item + .trust-item{{margin-top:10px}}
.trust-item b{{display:block;margin-bottom:4px;font-size:12px}}.trust-item p{{margin:0;color:var(--muted);font-size:10px}}
details{{padding:13px 0;border-bottom:1px solid var(--line)}}details:last-child{{border-bottom:0}}summary{{cursor:pointer;font-size:12px;font-weight:900}}details p{{margin:8px 0 0;color:var(--muted);font-size:11px}}

.contact{{display:grid;grid-template-columns:.9fr 1.1fr;gap:25px;padding:26px;border-radius:31px;color:#fff;background:radial-gradient(circle at 90% 10%,rgba(255,255,255,.15),transparent 28%),linear-gradient(145deg,#6d3df5,#351285)}}
.contact h2{{margin:0 0 8px;font-size:clamp(25px,2.15vw,34px);line-height:1.3;}}.contact p{{margin:0 0 15px;color:#e4dcf3;font-size:11px;line-height:1.8;}}.contact-links{{display:grid;gap:7px;font-size:11px}}
.contact-form{{display:grid;gap:9px;padding:20px;border-radius:20px;background:#fff}}
.contact-form input,.contact-form textarea{{width:100%;padding:11px 12px;border:1px solid #e9e4f2;border-radius:11px;outline:none;color:#14111b;background:#fff}}
.contact-form textarea{{min-height:105px;resize:vertical}}.contact-form input:focus,.contact-form textarea:focus{{border-color:var(--purple);box-shadow:0 0 0 3px rgba(108,60,255,.1)}}
.contact-form button{{min-height:45px;border:0;border-radius:11px;color:#fff;background:var(--purple);font-weight:900;cursor:pointer}}
.flash{{margin-bottom:9px;padding:9px 11px;border-radius:11px;color:#14764a;background:#e9f8ef;font-size:11px;font-weight:900}}

footer{{margin-top:72px;padding:38px 0;color:#d7cfe1;background:#17131e;font-size:11px}}
.footer-grid{{display:grid;grid-template-columns:1.5fr repeat(3,1fr);gap:28px}}.footer-brand b{{display:block;margin-bottom:8px;color:#fff;font-size:19px}}
.footer-col strong{{display:block;margin-bottom:9px;color:#fff}}.footer-col a{{display:block;margin-top:5px}}
.reveal{{opacity:0;transform:translateY(26px);transition:opacity .65s ease,transform .65s ease}}.reveal.visible{{opacity:1;transform:none}}
@keyframes pulse{{0%,100%{{transform:scale(.96);opacity:.82}}50%{{transform:scale(1.05);opacity:1}}}}

@media(max-width:1020px){{
  .hero-shell{{grid-template-columns:1fr}}.hero-copy{{text-align:center;padding-bottom:30px}}.hero-kicker{{margin-inline:auto}}.hero-lead{{margin-inline:auto}}.hero-actions,.hero-trust{{justify-content:flex-start}}
  .visual-stage{{min-height:580px}}.story,.timeline-wrap,.trust-faq,.contact,.demo-shell,.recommender{{grid-template-columns:1fr}}
  .bento{{grid-template-columns:repeat(2,1fr);grid-template-rows:auto}}.bento-main{{grid-row:auto}}.gallery-track{{grid-template-columns:repeat(3,minmax(170px,1fr))}}
  .pricing{{grid-template-columns:repeat(2,1fr)}}.nav-links{{display:none}}.nav-login,.nav-start{{display:none}}.menu-button{{display:block}}.nav{{position:relative}}
  .nav-links.open{{position:absolute;top:65px;right:0;left:0;display:grid;gap:0;padding:10px;border:1px solid var(--line);border-radius:16px;background:var(--card);box-shadow:var(--shadow)}}
  .nav-links.open a{{padding:10px 12px;border-radius:10px}}
}}
@media(max-width:680px){{
  .container{{width:calc(100% - 22px)}}.nav{{min-height:65px}}.hero{{padding-top:28px}}.hero-shell{{border-radius:27px}}.hero-copy{{padding:42px 21px 28px}}
  .hero h1{{font-size:clamp(22px,7vw,30px)!important;line-height:1.28;letter-spacing:-.4px}}.hero-lead{{font-size:14px}}.hero-actions{{display:grid;grid-template-columns:1fr}}
  .btn-primary,.btn-secondary{{width:100%}}.visual-stage{{min-height:460px}}.phone-main{{width:230px}}.phone-left,.phone-right{{width:177px;bottom:48px}}.float-note{{display:none}}
  .hero-metrics{{grid-template-columns:repeat(2,1fr)}}.metric:nth-child(3),.metric:nth-child(4){{border-top:1px solid var(--line)}}.section{{padding:49px 0}}.section-head h2{{font-size:29px}}
  .story-copy{{padding:22px}}.story-copy h2{{font-size:28px}}.story-visual{{min-height:360px}}.bento,.pricing{{grid-template-columns:1fr}}.bento-card{{min-height:210px}}
  .gallery-shell{{padding:18px;overflow-x:auto}}.gallery-track{{min-width:980px;grid-template-columns:repeat(5,180px)}}.timeline{{grid-template-columns:repeat(2,1fr);gap:18px}}.timeline:before{{display:none}}
  .price-card.featured{{transform:none}}.contact{{padding:22px}}.footer-grid{{grid-template-columns:1fr 1fr}}.demo-output-grid{{grid-template-columns:1fr}}
}}
@media(max-width:390px){{.container{{width:calc(100% - 16px)}}.hero h1{{font-size:22px!important}}.visual-stage{{min-height:420px}}.phone-main{{width:205px}}.phone-left,.phone-right{{width:148px}}.footer-grid{{grid-template-columns:1fr}}}}



/* ===== RASHDYAR TYPOGRAPHY SYSTEM START ===== */

/* اندازه پایه متن‌های سایت */
body{{
    font-size:14px;
    line-height:1.75;
}}

/* نوار بالا و منو */
.announcement{{
    font-size:10px!important;
}}

.nav-links a,
.nav-login,
.nav-start{{
    font-size:12px!important;
}}

.brand-name{{
    font-size:20px!important;
}}

/* Hero */
.hero-copy{{
    padding:42px 46px!important;
}}

.hero-kicker{{
    font-size:10px!important;
    padding:6px 10px!important;
}}

.hero h1{{
    margin:14px 0 12px!important;
    font-size:clamp(29px,2.45vw,42px)!important;
    line-height:1.22!important;
    letter-spacing:-.7px!important;
    max-width:540px!important;
}}

.hero-lead{{
    max-width:540px!important;
    font-size:13px!important;
    line-height:1.95!important;
}}

.hero-actions{{
    margin-top:18px!important;
    gap:9px!important;
}}

.btn-primary,
.btn-secondary{{
    min-height:44px!important;
    padding:10px 17px!important;
    font-size:12px!important;
    border-radius:12px!important;
}}

.hero-trust{{
    margin-top:16px!important;
    gap:12px!important;
    font-size:10px!important;
}}

/* کارت آمار زیر Hero */
.metric strong{{
    font-size:24px!important;
}}

.metric span,
.metric small{{
    font-size:10px!important;
}}

/* فاصله استاندارد بخش‌ها */
.section{{
    padding:54px 0!important;
}}

.section-head{{
    margin-bottom:25px!important;
}}

.section-head .eyebrow,
.section-label{{
    font-size:10px!important;
}}

.section-head h2{{
    font-size:clamp(26px,2.4vw,36px)!important;
    line-height:1.28!important;
    letter-spacing:-.5px!important;
}}

.section-head p{{
    max-width:680px!important;
    font-size:13px!important;
    line-height:1.9!important;
}}

/* تیترهای اصلی بخش‌های مختلف */
.story-copy h2,
.demo-title,
.compare-title,
.pricing-title,
.contact h2,
.trust-faq h2,
.recommender h2{{font-size:clamp(24px,2vw,32px);
    line-height:1.3;
    letter-spacing:-.4px!important;}}

.story-copy p,
.demo-subtitle,
.compare-subtitle,
.pricing-subtitle,
.contact p,
.trust-faq p,
.recommender p{{
    font-size:13px!important;
    line-height:1.9!important;
}}

/* تیتر کارت‌ها */
.bento-card h3,
.price-card h3,
.story-card h3,
.demo-card h3,
.download-header h3{{font-size:17px;
    line-height:1.4;}}

.bento-card p,
.price-card p,
.story-card p,
.demo-card p,
.download-header p{{font-size:10px;
    line-height:1.75;}}

/* کارت‌های امکانات */
.bento-card{{
    padding:20px!important;
}}

.bento-card .icon{{
    width:42px!important;
    height:42px!important;
}}

/* مسیر رشد */
.timeline-step strong{{
    font-size:13px!important;
}}

.timeline-step span,
.timeline-step p{{
    font-size:10px!important;
}}

/* دمو */
.demo-shell{{
    padding:22px!important;
}}

.demo-output-card h3{{font-size:14px;}}

.demo-output-card p{{font-size:10px;
    line-height:1.75;}}

.demo-shell label{{
    font-size:11px!important;
}}

.demo-shell input,
.demo-shell select,
.demo-shell textarea{{
    font-size:12px!important;
    min-height:42px!important;
}}

/* جدول مقایسه */
.compare-table th{{
    font-size:11px!important;
}}

.compare-table td{{
    font-size:11px!important;
    padding:12px!important;
}}

/* پیشنهاد پلن */
.recommender{{
    padding:22px!important;
}}

.recommender h3{{
    font-size:20px!important;
}}

.recommender label{{font-size:10px;}}

/* دانلود اپ */

/* FLOAT NOTE CLICK FIX START */

.float-note{{
    z-index:40!important;
    overflow:visible!important;
    cursor:pointer!important;
    pointer-events:auto!important;
    transition:
        transform .22s ease,
        box-shadow .22s ease,
        z-index .01s linear!important;
    transform-origin:center!important;
}}

.float-note *{{
    overflow:visible!important;
}}

.float-note:hover{{
    z-index:80!important;
    transform:translateY(-5px) scale(1.04);
    box-shadow:0 22px 48px rgba(76,42,175,.30);background:linear-gradient(145deg,#ffffff 0%,#ebe2ff 100%);}}

.float-note.open{{
    z-index:100!important;
    transform:translateY(-7px) scale(1.07);
    box-shadow:0 26px 58px rgba(76,42,175,.34);background:linear-gradient(145deg,#ffffff 0%,#e5d8ff 100%);}}

.float-note:focus{{
    outline:3px solid rgba(108,60,255,.22)!important;
    outline-offset:3px!important;
}}

/* FLOAT NOTE CLICK FIX END */























/* STORY CLEAN FINAL START */

.story{{
    align-items:stretch!important;
    gap:16px!important;
}}

.story-visual{{
    position:relative!important;
    display:block!important;
    height:400px!important;
    min-height:400px!important;
    overflow:hidden!important;
    border-radius:24px!important;
    background:
        radial-gradient(
            circle at 50% 80%,
            rgba(108,60,255,.34),
            transparent 35%
        ),
        linear-gradient(
            145deg,
            #21142f 0%,
            #100b18 55%,
            #1f1230 100%
        )!important;
    box-shadow:
        inset 0 0 0 1px rgba(255,255,255,.06),
        0 18px 42px rgba(37,18,70,.14)!important;
}}

/* موبایل دقیقاً وسط و کامل داخل کادر */
.story-visual > img{{
    position:absolute!important;
    left:50%!important;
    top:50%!important;
    right:auto!important;
    bottom:auto!important;

    width:255px!important;
    height:auto!important;
    max-width:44%!important;
    max-height:88%!important;

    margin:0!important;
    padding:7px!important;
    object-fit:contain!important;

    border-radius:34px!important;
    background:#17131e!important;

    transform:translate(-50%,-50%) scale(1)!important;
    transform-origin:center!important;

    transition:
        transform .42s cubic-bezier(.2,.8,.2,1),
        filter .42s ease!important;

    z-index:10!important;
    cursor:pointer!important;
    will-change:transform!important;

    filter:
        drop-shadow(0 24px 34px rgba(0,0,0,.34))!important;
}}

/* حرکت فقط با رفتن موس روی موبایل */
.story-visual > img:hover{{
    transform:
        translate(-50%,-54%)
        scale(1.055)
        rotate(-1.1deg)!important;

    filter:
        drop-shadow(0 34px 46px rgba(0,0,0,.44))
        brightness(1.03)!important;
}}

/* کارت بالا سمت راست */
.story-card.story-a{{
    top:38px!important;
    right:32px!important;
    bottom:auto!important;
    left:auto!important;
    z-index:30!important;
    animation:storyCardTop 4s ease-in-out infinite!important;
}}

/* کارت پایین سمت چپ */
.story-card.story-b{{
    left:30px!important;
    bottom:34px!important;
    top:auto!important;
    right:auto!important;
    z-index:30!important;
    animation:storyCardBottom 4.6s ease-in-out infinite!important;
}}

.story-card{{
    padding:12px 14px!important;
    border-radius:16px!important;
    background:
        linear-gradient(
            145deg,
            rgba(255,255,255,.98),
            rgba(239,232,255,.97)
        )!important;
    border:1px solid rgba(108,60,255,.18)!important;
    box-shadow:0 14px 30px rgba(42,20,95,.20)!important;
    transition:
        transform .25s ease,
        box-shadow .25s ease!important;
}}

.story-card:hover{{
    animation-play-state:paused!important;
    transform:translateY(-4px) scale(1.04)!important;
    box-shadow:0 20px 42px rgba(70,36,170,.28)!important;
}}

.story-card b{{
    font-size:14px!important;
}}

.story-card span{{
    font-size:9px!important;
}}

@keyframes storyCardTop{{
    0%,100%{{
        transform:translateY(0);
    }}
    50%{{
        transform:translateY(-9px);
    }}
}}

@keyframes storyCardBottom{{
    0%,100%{{
        transform:translateY(0);
    }}
    50%{{
        transform:translateY(9px);
    }}
}}

@media(max-width:680px){{
    .story-visual{{
        height:350px!important;
        min-height:350px!important;
    }}

    .story-visual > img{{
        width:220px!important;
        max-width:56%!important;
        max-height:86%!important;
    }}

    .story-card.story-a{{
        top:25px!important;
        right:18px!important;
    }}

    .story-card.story-b{{
        left:18px!important;
        bottom:25px!important;
    }}
}}

/* STORY CLEAN FINAL END */



/* STORY EQUAL HEIGHT START */

.story{{
    align-items:stretch!important;
    gap:16px!important;
}}

.story-visual,
.story-copy{{
    height:400px!important;
    min-height:400px!important;
    box-sizing:border-box!important;
}}

.story-copy{{
    display:flex!important;
    flex-direction:column!important;
    justify-content:center!important;
    padding:24px 26px!important;
    overflow:hidden!important;
}}

.story-copy h2{{
    margin:7px 0 8px!important;
    font-size:30px!important;
    line-height:1.32!important;
}}

.story-copy p{{
    margin:0!important;
    font-size:12px!important;
    line-height:1.8!important;
}}

.story-points{{
    gap:8px!important;
    margin-top:16px!important;
}}

.story-point{{
    min-height:48px!important;
    padding:10px 11px!important;
    align-items:center!important;
}}

.story-point b{{
    width:27px!important;
    height:27px!important;
}}

.story-point span{{
    font-size:10px!important;
    line-height:1.65!important;
}}

@media(max-width:1020px){{
    .story-visual,
    .story-copy{{
        height:auto!important;
        min-height:390px!important;
    }}
}}

@media(max-width:680px){{
    .story-visual{{
        height:350px!important;
        min-height:350px!important;
    }}

    .story-copy{{
        min-height:auto!important;
        padding:21px!important;
    }}
}}

/* STORY EQUAL HEIGHT END */







/* BENTO REDESIGN START */

.bento{{
    display:grid!important;
    grid-template-columns:1.08fr .96fr .96fr!important;
    grid-template-rows:238px 218px!important;
    gap:16px!important;
    perspective:1200px!important;
}}

/* ساختار مشترک همه کارت‌ها */
.bento-card{{
    position:relative!important;
    isolation:isolate!important;
    overflow:hidden!important;
    padding:24px!important;

    border:1px solid rgba(108,60,255,.12)!important;
    border-radius:26px!important;

    background:
        linear-gradient(
            145deg,
            rgba(255,255,255,.96),
            rgba(247,244,255,.94)
        )!important;

    box-shadow:
        0 12px 34px rgba(49,30,95,.07),
        inset 0 1px 0 rgba(255,255,255,.9)!important;

    transform:translateY(0) rotateX(0) rotateY(0)!important;
    transform-style:preserve-3d!important;

    transition:
        transform .34s cubic-bezier(.2,.8,.2,1),
        box-shadow .34s ease,
        border-color .34s ease!important;
}}

/* هاله نور داخل کارت‌ها */
.bento-card::before{{
    content:""!important;
    position:absolute!important;
    width:180px!important;
    height:180px!important;
    left:-65px!important;
    bottom:-75px!important;
    border-radius:50%!important;

    background:
        radial-gradient(
            circle,
            rgba(108,60,255,.16),
            transparent 68%
        )!important;

    filter:blur(8px)!important;
    pointer-events:none!important;
    z-index:-1!important;
    transition:
        transform .4s ease,
        opacity .4s ease!important;
}}

/* درخشش ظریف بالا */
.bento-card::after{{
    content:""!important;
    position:absolute!important;
    inset:0!important;
    border-radius:inherit!important;

    background:
        linear-gradient(
            120deg,
            transparent 20%,
            rgba(255,255,255,.42) 48%,
            transparent 72%
        )!important;

    transform:translateX(115%)!important;
    pointer-events:none!important;
    z-index:0!important;
    transition:transform .7s ease!important;
}}

.bento-card:hover{{
    transform:
        translateY(-8px)
        rotateX(1.5deg)
        rotateY(-1.5deg)!important;

    border-color:rgba(108,60,255,.28)!important;

    box-shadow:
        0 24px 54px rgba(61,35,130,.15),
        inset 0 1px 0 rgba(255,255,255,.95)!important;
}}

.bento-card:hover::before{{
    transform:scale(1.18)!important;
    opacity:1!important;
}}

.bento-card:hover::after{{
    transform:translateX(-115%)!important;
}}

/* متن کارت‌ها */
.bento-card h3{{
    position:relative!important;
    z-index:2!important;

    max-width:420px!important;
    margin:12px 0 8px!important;

    font-size:18px!important;
    line-height:1.55!important;
    letter-spacing:-.15px!important;
}}

.bento-card p{{
    position:relative!important;
    z-index:2!important;

    max-width:410px!important;
    margin:0!important;

    color:var(--muted)!important;
    font-size:11px!important;
    line-height:1.9!important;
}}

.bento-label{{
    position:relative!important;
    z-index:3!important;

    display:inline-flex!important;
    align-items:center!important;
    min-height:26px!important;
    padding:5px 9px!important;

    border-radius:999px!important;
    background:rgba(108,60,255,.09)!important;

    color:var(--purple)!important;
    font-size:9px!important;
    font-weight:950!important;
}}

/* کارت اصلی تحلیل */
.bento-main{{
    grid-row:1 / 3!important;
    padding:27px!important;

    color:#fff!important;

    background:
        radial-gradient(
            circle at 20% 85%,
            rgba(126,78,255,.45),
            transparent 36%
        ),
        linear-gradient(
            155deg,
            #25143a 0%,
            #160d24 48%,
            #0d0913 100%
        )!important;

    border-color:rgba(255,255,255,.10)!important;

    box-shadow:
        0 20px 50px rgba(30,17,55,.25)!important;
}}

.bento-main::before{{
    width:250px!important;
    height:250px!important;
    left:-70px!important;
    bottom:-60px!important;

    background:
        radial-gradient(
            circle,
            rgba(115,65,255,.55),
            transparent 68%
        )!important;
}}

.bento-main .bento-label{{
    color:#dcd0ff!important;
    background:rgba(255,255,255,.10)!important;
    border:1px solid rgba(255,255,255,.10)!important;
}}

.bento-main h3{{
    max-width:320px!important;
    font-size:21px!important;
    line-height:1.55!important;
}}

.bento-main p{{
    max-width:310px!important;
    color:#d5cee0!important;
}}

/* تصویر داخل کارت اصلی */
.bento-main img{{
    position:absolute!important;
    left:-12px!important;
    bottom:-74px!important;

    width:250px!important;
    max-width:64%!important;

    padding:7px!important;
    border-radius:34px!important;
    background:#17131e!important;

    transform:rotate(-5deg) translateY(0)!important;
    transform-origin:center bottom!important;

    filter:drop-shadow(0 24px 34px rgba(0,0,0,.40))!important;

    transition:
        transform .42s cubic-bezier(.2,.8,.2,1),
        filter .42s ease!important;

    z-index:2!important;
}}

.bento-main:hover img{{
    transform:
        rotate(-2.5deg)
        translateY(-13px)
        scale(1.025)!important;

    filter:
        drop-shadow(0 34px 46px rgba(0,0,0,.48))
        brightness(1.03)!important;
}}

/* کارت سبز ترند */
.bento-accent{{
    color:#17131f!important;

    background:
        radial-gradient(
            circle at 86% 18%,
            rgba(255,255,255,.78),
            transparent 30%
        ),
        linear-gradient(
            145deg,
            #dfff84 0%,
            #eaffad 55%,
            #f4ffd3 100%
        )!important;

    border-color:rgba(131,177,42,.20)!important;
}}

.bento-accent .bento-label{{
    color:#527b00!important;
    background:rgba(255,255,255,.55)!important;
}}

.bento-accent p{{
    color:#637346!important;
}}

/* کارت سوم */
.bento-card:nth-child(3){{
    background:
        radial-gradient(
            circle at 15% 85%,
            rgba(108,60,255,.15),
            transparent 34%
        ),
        linear-gradient(
            145deg,
            #ffffff 0%,
            #f6f2ff 100%
        )!important;
}}

/* کارت چهارم */
.bento-card:nth-child(4){{
    background:
        radial-gradient(
            circle at 82% 18%,
            rgba(112,205,255,.16),
            transparent 36%
        ),
        linear-gradient(
            145deg,
            #ffffff 0%,
            #f2f9ff 100%
        )!important;
}}

/* کارت بنفش برنامه */
.bento-purple{{
    color:#fff!important;

    background:
        radial-gradient(
            circle at 20% 80%,
            rgba(176,137,255,.38),
            transparent 36%
        ),
        linear-gradient(
            145deg,
            #7548ff 0%,
            #5222cf 55%,
            #35118e 100%
        )!important;

    border-color:rgba(255,255,255,.12)!important;

    box-shadow:
        0 18px 42px rgba(75,36,176,.22)!important;
}}

.bento-purple .bento-label{{
    color:#eee7ff!important;
    background:rgba(255,255,255,.14)!important;
}}

.bento-purple p{{
    color:#e7deff!important;
}}

/* نمودار کوچک کارت ساخت */
.bento-mini-visual{{
    position:absolute!important;
    left:20px!important;
    bottom:18px!important;

    width:92px!important;
    height:65px!important;
    border-radius:16px!important;

    background:
        linear-gradient(
            145deg,
            rgba(245,241,255,.96),
            #fff
        )!important;

    border:1px solid rgba(108,60,255,.10)!important;

    box-shadow:
        0 13px 28px rgba(80,45,150,.12)!important;

    transform:translateY(0)!important;
    transition:
        transform .35s ease,
        box-shadow .35s ease!important;
}}

.bento-card:hover .bento-mini-visual{{
    transform:translateY(-7px) rotate(-2deg)!important;
    box-shadow:
        0 20px 38px rgba(80,45,150,.20)!important;
}}

.bento-mini-visual::before,
.bento-mini-visual::after{{
    background:
        linear-gradient(
            180deg,
            #8b62ff,
            #5b29e6
        )!important;
}}

/* تبلت */
@media(max-width:1020px){{
    .bento{{
        grid-template-columns:repeat(2,1fr)!important;
        grid-template-rows:auto!important;
    }}

    .bento-main{{
        grid-row:auto!important;
        min-height:350px!important;
    }}

    .bento-card{{
        min-height:230px!important;
    }}
}}

/* موبایل */
@media(max-width:680px){{
    .bento{{
        grid-template-columns:1fr!important;
        gap:13px!important;
    }}

    .bento-card{{
        min-height:215px!important;
        padding:20px!important;
        border-radius:22px!important;
    }}

    .bento-main{{
        min-height:370px!important;
    }}

    .bento-main img{{
        width:220px!important;
        bottom:-70px!important;
    }}

    .bento-card:hover{{
        transform:translateY(-4px)!important;
    }}
}}

@media(hover:none){{
    .bento-card:hover{{
        transform:none!important;
    }}
}}

@media(prefers-reduced-motion:reduce){{
    .bento-card,
    .bento-main img,
    .bento-mini-visual{{
        transition:none!important;
    }}
}}

/* BENTO REDESIGN END */



/* PRICING REDESIGN START */

.pricing{{
    display:grid!important;
    grid-template-columns:repeat(3,minmax(0,1fr))!important;
    align-items:stretch!important;
    gap:18px!important;
    margin-top:30px!important;
    perspective:1200px!important;
}}

.price-card{{
    position:relative!important;
    isolation:isolate!important;
    display:flex!important;
    flex-direction:column!important;
    min-height:480px!important;
    padding:27px 24px!important;
    overflow:visible!important;
    border:1px solid rgba(108,60,255,.13)!important;
    border-radius:28px!important;

    background:
        radial-gradient(
            circle at 15% 10%,
            rgba(108,60,255,.10),
            transparent 30%
        ),
        linear-gradient(
            145deg,
            rgba(255,255,255,.98),
            rgba(248,245,255,.97)
        )!important;

    box-shadow:
        0 15px 38px rgba(46,27,91,.08),
        inset 0 1px 0 rgba(255,255,255,.96)!important;

    transform:translateY(0)!important;
    transform-style:preserve-3d!important;

    transition:
        transform .34s cubic-bezier(.2,.8,.2,1),
        box-shadow .34s ease,
        border-color .34s ease!important;
}}

.price-card::before{{
    content:""!important;
    position:absolute!important;
    width:190px!important;
    height:190px!important;
    left:-65px!important;
    bottom:-65px!important;
    border-radius:50%!important;
    background:
        radial-gradient(
            circle,
            rgba(108,60,255,.15),
            transparent 68%
        )!important;
    filter:blur(8px)!important;
    pointer-events:none!important;
    z-index:-1!important;
    transition:transform .4s ease!important;
}}

.price-card:hover{{
    transform:translateY(-9px)!important;
    border-color:rgba(108,60,255,.30)!important;

    box-shadow:
        0 28px 62px rgba(56,31,121,.16),
        inset 0 1px 0 rgba(255,255,255,.98)!important;
}}

.price-card:hover::before{{
    transform:scale(1.18)!important;
}}

.price-card h3{{
    margin:8px 0 4px!important;
    font-size:21px!important;
    line-height:1.4!important;
    letter-spacing:-.2px!important;
}}

.price-card > small,
.price-card .plan-subtitle{{
    color:var(--muted)!important;
    font-size:10px!important;
    line-height:1.75!important;
}}

.price-card .price,
.price-card [class*="price"]{{
    margin-top:16px!important;
}}

.price-card .price{{
    color:var(--purple)!important;
    font-size:32px!important;
    line-height:1.15!important;
    font-weight:950!important;
    letter-spacing:-.8px!important;
}}

.price-card .price small,
.price-card .price span{{
    font-size:10px!important;
    font-weight:800!important;
    letter-spacing:0!important;
}}

.price-card ul{{
    display:grid!important;
    gap:10px!important;
    margin:22px 0 24px!important;
    padding:0!important;
    list-style:none!important;
}}

.price-card li{{
    position:relative!important;
    padding-right:20px!important;
    color:var(--ink)!important;
    font-size:10px!important;
    line-height:1.8!important;
}}

.price-card li::before{{
    content:"✓"!important;
    position:absolute!important;
    right:0!important;
    top:0!important;
    color:#27b974!important;
    font-weight:950!important;
}}

.price-card a,
.price-card button{{
    width:100%!important;
    min-height:46px!important;
    margin-top:auto!important;
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
    padding:10px 16px!important;
    border:0!important;
    border-radius:14px!important;
    color:#fff!important;
    background:#15111d!important;
    font-size:11px!important;
    font-weight:950!important;
    text-decoration:none!important;
    cursor:pointer!important;

    transition:
        transform .25s ease,
        box-shadow .25s ease,
        background .25s ease!important;
}}

.price-card a:hover,
.price-card button:hover{{
    transform:translateY(-2px)!important;
    background:#241833!important;
    box-shadow:0 14px 28px rgba(30,20,45,.20)!important;
}}

/* کارت ویژه */
.price-card.featured{{
    z-index:3!important;
    transform:translateY(-13px)!important;
    color:#fff!important;
    border-color:rgba(255,255,255,.13)!important;

    background:
        radial-gradient(
            circle at 18% 12%,
            rgba(153,107,255,.38),
            transparent 32%
        ),
        radial-gradient(
            circle at 85% 90%,
            rgba(93,47,207,.48),
            transparent 38%
        ),
        linear-gradient(
            155deg,
            #3c2852 0%,
            #251734 48%,
            #160f21 100%
        )!important;

    box-shadow:
        0 30px 72px rgba(37,20,66,.30)!important;
}}

.price-card.featured::before{{
    width:260px!important;
    height:260px!important;
    background:
        radial-gradient(
            circle,
            rgba(126,76,255,.52),
            transparent 68%
        )!important;
}}

.price-card.featured:hover{{
    transform:translateY(-21px)!important;
    box-shadow:
        0 38px 82px rgba(37,20,66,.38)!important;
}}

.price-card.featured h3,
.price-card.featured li{{
    color:#fff!important;
}}

.price-card.featured > small,
.price-card.featured .plan-subtitle{{
    color:#d8cfe3!important;
}}

.price-card.featured .price{{
    color:#fff!important;
}}

.price-card.featured li::before{{
    color:#b99cff!important;
}}

.price-card.featured a,
.price-card.featured button{{
    color:#fff!important;
    background:
        linear-gradient(
            135deg,
            #8b55ff,
            #6429e7
        )!important;
    box-shadow:0 16px 34px rgba(108,60,255,.30)!important;
}}

.price-card.featured a:hover,
.price-card.featured button:hover{{
    background:
        linear-gradient(
            135deg,
            #9868ff,
            #7135ef
        )!important;
    box-shadow:0 21px 42px rgba(108,60,255,.40)!important;
}}

/* برچسب کارت ویژه */
.price-card.featured::after{{
    content:"پرفروش‌ترین"!important;
    position:absolute!important;
    top:-14px!important;
    left:50%!important;
    transform:translateX(-50%)!important;
    min-width:105px!important;
    min-height:28px!important;
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
    padding:5px 13px!important;
    border-radius:999px!important;
    color:#fff!important;
    background:
        linear-gradient(
            135deg,
            #8b55ff,
            #5e24d8
        )!important;
    box-shadow:0 12px 25px rgba(108,60,255,.30)!important;
    font-size:9px!important;
    font-weight:950!important;
    z-index:6!important;
}}

/* کارت اول و سوم */
.price-card:not(.featured){{
    margin-top:13px!important;
}}

.price-card:not(.featured):first-child{{
    background:
        radial-gradient(
            circle at 80% 10%,
            rgba(109,214,255,.12),
            transparent 32%
        ),
        linear-gradient(
            145deg,
            #fff,
            #f5faff
        )!important;
}}

.price-card:not(.featured):last-child{{
    background:
        radial-gradient(
            circle at 18% 12%,
            rgba(152,108,255,.12),
            transparent 32%
        ),
        linear-gradient(
            145deg,
            #fff,
            #f7f2ff
        )!important;
}}

/* تبلت */
@media(max-width:1020px){{
    .pricing{{
        grid-template-columns:repeat(2,minmax(0,1fr))!important;
    }}

    .price-card.featured{{
        transform:none!important;
    }}

    .price-card.featured:hover{{
        transform:translateY(-8px)!important;
    }}

    .price-card:not(.featured){{
        margin-top:0!important;
    }}
}}

/* موبایل */
@media(max-width:680px){{
    .pricing{{
        grid-template-columns:1fr!important;
        gap:20px!important;
    }}

    .price-card{{
        min-height:440px!important;
        padding:24px 21px!important;
        border-radius:24px!important;
        margin-top:0!important;
    }}

    .price-card.featured{{
        order:-1!important;
        transform:none!important;
    }}

    .price-card:hover,
    .price-card.featured:hover{{
        transform:translateY(-5px)!important;
    }}
}}

@media(hover:none){{
    .price-card:hover,
    .price-card.featured:hover{{
        transform:none!important;
    }}
}}

@media(prefers-reduced-motion:reduce){{
    .price-card,
    .price-card a,
    .price-card button{{
        transition:none!important;
    }}
}}

/* PRICING REDESIGN END */



/* FAQ REDESIGN START */

#faq{{
    position:relative!important;
}}

#faq .section-head{{
    margin-bottom:28px!important;
}}

#faq .faq-list,
#faq .faq-items,
#faq .faqs,
#faq .accordion{{
    display:grid!important;
    gap:11px!important;
    max-width:900px!important;
    margin-inline:auto!important;
}}

/* خود آیتم سؤال */
#faq details,
#faq .faq-item{{
    position:relative!important;
    overflow:hidden!important;

    margin:0!important;
    padding:0!important;

    border:1px solid rgba(108,60,255,.12)!important;
    border-radius:18px!important;

    background:
        radial-gradient(
            circle at 95% 0%,
            rgba(108,60,255,.08),
            transparent 34%
        ),
        linear-gradient(
            145deg,
            rgba(255,255,255,.98),
            rgba(248,245,255,.97)
        )!important;

    box-shadow:
        0 9px 25px rgba(48,28,95,.055),
        inset 0 1px 0 rgba(255,255,255,.95)!important;

    transition:
        border-color .28s ease,
        box-shadow .28s ease,
        transform .28s ease,
        background .28s ease!important;
}}

#faq details:hover,
#faq .faq-item:hover{{
    transform:translateY(-2px)!important;
    border-color:rgba(108,60,255,.25)!important;

    box-shadow:
        0 16px 34px rgba(58,32,125,.10),
        inset 0 1px 0 rgba(255,255,255,.98)!important;
}}

/* حالت باز */
#faq details[open],
#faq .faq-item.open{{
    border-color:rgba(108,60,255,.32)!important;

    background:
        radial-gradient(
            circle at 95% 0%,
            rgba(108,60,255,.15),
            transparent 38%
        ),
        linear-gradient(
            145deg,
            #ffffff,
            #f4efff
        )!important;

    box-shadow:
        0 18px 42px rgba(66,35,145,.13),
        inset 0 1px 0 rgba(255,255,255,.98)!important;
}}

/* عنوان سؤال */
#faq summary,
#faq .faq-question{{
    position:relative!important;

    display:flex!important;
    align-items:center!important;
    justify-content:space-between!important;
    gap:18px!important;

    min-height:62px!important;
    margin:0!important;
    padding:15px 19px 15px 62px!important;

    color:var(--ink)!important;
    font-size:12px!important;
    line-height:1.7!important;
    font-weight:900!important;

    list-style:none!important;
    cursor:pointer!important;
    user-select:none!important;
}}

#faq summary::-webkit-details-marker{{
    display:none!important;
}}

#faq summary::marker{{
    content:""!important;
}}

/* آیکون + */
#faq summary::after,
#faq .faq-question::after{{
    content:"+"!important;

    position:absolute!important;
    left:16px!important;
    top:50%!important;

    width:31px!important;
    height:31px!important;

    display:grid!important;
    place-items:center!important;

    border:1px solid rgba(108,60,255,.16)!important;
    border-radius:10px!important;

    color:var(--purple)!important;
    background:
        linear-gradient(
            145deg,
            #ffffff,
            #eee7ff
        )!important;

    box-shadow:0 7px 16px rgba(78,43,170,.10)!important;

    font-size:20px!important;
    line-height:1!important;
    font-weight:500!important;

    transform:translateY(-50%) rotate(0deg)!important;

    transition:
        transform .3s cubic-bezier(.2,.8,.2,1),
        color .3s ease,
        background .3s ease,
        box-shadow .3s ease!important;
}}

/* آیکون هنگام بازشدن */
#faq details[open] summary::after,
#faq .faq-item.open .faq-question::after{{
    content:"×"!important;

    color:#fff!important;

    background:
        linear-gradient(
            135deg,
            #8b55ff,
            #5d25d8
        )!important;

    box-shadow:
        0 10px 22px rgba(108,60,255,.25)!important;

    transform:
        translateY(-50%)
        rotate(90deg)!important;
}}

/* پاسخ */
#faq details > :not(summary),
#faq .faq-answer{{
    margin:0!important;
    padding:0 19px 17px!important;

    color:var(--muted)!important;
    font-size:11px!important;
    line-height:2!important;
}}

/* خط جداکننده پاسخ */
#faq details[open] summary::before,
#faq .faq-item.open .faq-question::before{{
    content:""!important;

    position:absolute!important;
    right:19px!important;
    left:19px!important;
    bottom:0!important;

    height:1px!important;

    background:
        linear-gradient(
            90deg,
            transparent,
            rgba(108,60,255,.16),
            transparent
        )!important;
}}

/* انیمیشن پاسخ details */
#faq details[open] > :not(summary){{
    animation:faqAnswerIn .32s ease both!important;
}}

@keyframes faqAnswerIn{{
    from{{
        opacity:0;
        transform:translateY(-7px);
    }}

    to{{
        opacity:1;
        transform:translateY(0);
    }}
}}

/* کارت راهنمای کنار FAQ در صورت وجود */
#faq .faq-side,
#faq .faq-help{{
    padding:24px!important;
    border:1px solid rgba(108,60,255,.12)!important;
    border-radius:22px!important;

    background:
        radial-gradient(
            circle at 15% 85%,
            rgba(108,60,255,.14),
            transparent 38%
        ),
        linear-gradient(
            145deg,
            #ffffff,
            #f6f2ff
        )!important;

    box-shadow:0 14px 34px rgba(48,28,95,.07)!important;
}}

#faq .faq-side h3,
#faq .faq-help h3{{
    margin:0 0 8px!important;
    font-size:19px!important;
    line-height:1.45!important;
}}

#faq .faq-side p,
#faq .faq-help p{{
    margin:0!important;
    color:var(--muted)!important;
    font-size:11px!important;
    line-height:1.9!important;
}}

/* موبایل */
@media(max-width:680px){{
    #faq .section-head{{
        margin-bottom:22px!important;
    }}

    #faq .faq-list,
    #faq .faq-items,
    #faq .faqs,
    #faq .accordion{{
        gap:9px!important;
    }}

    #faq details,
    #faq .faq-item{{
        border-radius:16px!important;
    }}

    #faq summary,
    #faq .faq-question{{
        min-height:58px!important;
        padding:14px 15px 14px 55px!important;
        font-size:11px!important;
    }}

    #faq summary::after,
    #faq .faq-question::after{{
        left:13px!important;
        width:29px!important;
        height:29px!important;
        border-radius:9px!important;
    }}

    #faq details > :not(summary),
    #faq .faq-answer{{
        padding:0 15px 15px!important;
        font-size:10px!important;
    }}
}}

@media(hover:none){{
    #faq details:hover,
    #faq .faq-item:hover{{
        transform:none!important;
    }}
}}

@media(prefers-reduced-motion:reduce){{
    #faq details,
    #faq .faq-item,
    #faq summary::after,
    #faq .faq-question::after,
    #faq details[open] > :not(summary){{
        animation:none!important;
        transition:none!important;
    }}
}}

/* FAQ REDESIGN END */































/* CONTACT CLEAN FINAL START */

/*
.contact خودش هم‌زمان کلاس container دارد:
<div class="container contact reveal">
بنابراین باید دقیقاً از همان عرض عمومی container استفاده کند.
*/

.contact{{
    width:min(1180px,calc(100% - 48px))!important;
    max-width:1180px!important;
    margin-inline:auto!important;
    box-sizing:border-box!important;

    display:grid!important;
    grid-template-columns:minmax(0,.95fr) minmax(0,1.05fr)!important;
    align-items:center!important;
    gap:30px!important;

    min-height:360px!important;
    padding:26px 38px!important;

    overflow:hidden!important;
    isolation:isolate!important;

    border:1px solid rgba(108,60,255,.16)!important;
    border-radius:28px!important;

    color:#fff!important;

    background:
        radial-gradient(
            circle at 10% 88%,
            rgba(146,91,255,.25),
            transparent 36%
        ),
        radial-gradient(
            circle at 90% 12%,
            rgba(164,124,255,.16),
            transparent 33%
        ),
        linear-gradient(
            135deg,
            #7340f2 0%,
            #5524ca 54%,
            #35127f 100%
        )!important;

    box-shadow:
        0 24px 60px rgba(54,25,130,.20)!important;
}}

/* ستون توضیحات */
.contact > div:first-child{{
    width:100%!important;
    max-width:500px!important;
    justify-self:end!important;
    align-self:center!important;
    padding:0!important;
}}

.contact h2{{
    max-width:500px!important;
    margin:0 0 10px!important;

    color:#fff!important;
    font-size:30px!important;
    line-height:1.38!important;
}}

.contact p{{
    max-width:500px!important;
    margin:0 0 12px!important;

    color:rgba(255,255,255,.80)!important;
    font-size:10px!important;
    line-height:1.9!important;
}}

.contact-links{{
    display:grid!important;
    gap:6px!important;
    margin-top:10px!important;

    color:rgba(255,255,255,.94)!important;
    font-size:9px!important;
    line-height:1.7!important;
}}

/* ستون فرم */
.contact > div:nth-child(2){{
    width:100%!important;
    max-width:500px!important;
    justify-self:start!important;
transform:translateX(-28px)!important;
    align-self:center!important;
}}

.contact-form{{
    display:grid!important;
    grid-template-columns:1fr!important;
    gap:8px!important;

    width:100%!important;
    max-width:500px!important;
    margin:0!important;
    padding:16px!important;

    border:1px solid rgba(255,255,255,.72)!important;
    border-radius:20px!important;

    background:
        linear-gradient(
            145deg,
            rgba(255,255,255,.99),
            rgba(248,246,255,.98)
        )!important;

    box-shadow:
        0 20px 48px rgba(30,14,78,.22)!important;
}}

/* فیلدهای کوتاه */
.contact-form input{{
    display:block!important;

    width:100%!important;
    height:40px!important;
    min-height:40px!important;
    max-height:40px!important;

    margin:0!important;
    padding:8px 12px!important;

    border:1px solid #ddd7ec!important;
    border-radius:11px!important;
    outline:none!important;

    color:#21182d!important;
    background:#fff!important;

    font-family:inherit!important;
    font-size:10px!important;
    line-height:1.4!important;

    box-sizing:border-box!important;
}}

/* کادر پیام */
.contact-form textarea{{
    display:block!important;

    width:100%!important;
    height:96px!important;
    min-height:96px!important;
    max-height:150px!important;

    margin:0!important;
    padding:10px 12px!important;

    resize:vertical!important;

    border:1px solid #ddd7ec!important;
    border-radius:11px!important;
    outline:none!important;

    color:#21182d!important;
    background:#fff!important;

    font-family:inherit!important;
    font-size:10px!important;
    line-height:1.75!important;

    box-sizing:border-box!important;
}}

.contact-form input::placeholder,
.contact-form textarea::placeholder{{
    color:#9d94aa!important;
    opacity:1!important;
}}

.contact-form input:focus,
.contact-form textarea:focus{{
    border-color:#8150ff!important;
    box-shadow:0 0 0 3px rgba(108,60,255,.10)!important;
}}

/* دکمه */
.contact-form button{{
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;

    width:100%!important;
    height:40px!important;
    min-height:40px!important;

    margin:0!important;
    padding:8px 15px!important;

    border:0!important;
    border-radius:11px!important;

    color:#fff!important;

    background:
        linear-gradient(
            135deg,
            #7d49ff,
            #5c25da
        )!important;

    box-shadow:
        0 11px 25px rgba(108,60,255,.23)!important;

    font-family:inherit!important;
    font-size:10px!important;
    font-weight:950!important;
    cursor:pointer!important;

    transition:
        transform .22s ease,
        box-shadow .22s ease!important;
}}

.contact-form button:hover{{
    transform:translateY(-2px)!important;
    box-shadow:0 16px 32px rgba(108,60,255,.32)!important;
}}

/* فاصله سکشن */
section:has(> .contact){{
    padding-top:42px!important;
    padding-bottom:42px!important;
}}

/* تبلت */
@media(max-width:1020px){{
    .contact{{
        width:calc(100% - 22px)!important;
        max-width:none!important;

        grid-template-columns:1fr!important;
        gap:20px!important;

        padding:24px!important;
    }}

    .contact > div:first-child,
    .contact > div:nth-child(2),
    .contact-form{{
        width:100%!important;
        max-width:none!important;
        justify-self:stretch!important;
    }}
}}

/* موبایل */
@media(max-width:680px){{
    .contact{{
        width:calc(100% - 22px)!important;
        min-height:auto!important;

        padding:18px!important;
        gap:17px!important;

        border-radius:22px!important;
    }}

    .contact h2{{
        font-size:24px!important;
    }}

    .contact-form{{
        padding:14px!important;
        border-radius:17px!important;
    }}
}}

@media(max-width:390px){{
    .contact{{
        width:calc(100% - 16px)!important;
    }}
}}

/* CONTACT CLEAN FINAL END */



/* CONTACT DETAILS FINAL START */

/* فرم همچنان کمی متمایل به چپ بماند */
.contact > div:nth-child(2){{
    transform:translateX(-28px)!important;
}}

/* حرکت نرم خود فرم */
.contact-form{{
    position:relative!important;

    transition:
        transform .28s cubic-bezier(.2,.8,.2,1),
        box-shadow .28s ease,
        border-color .28s ease!important;
}}

.contact-form:hover{{
    transform:translateY(-4px)!important;
    border-color:rgba(255,255,255,.95)!important;

    box-shadow:
        0 28px 62px rgba(28,12,75,.30),
        0 0 0 1px rgba(139,85,255,.08),
        inset 0 1px 0 #fff!important;
}}

/* درخشش ظریف روی فرم */
.contact-form::before{{
    content:""!important;
    position:absolute!important;
    inset:-1px!important;

    border-radius:inherit!important;

    background:
        linear-gradient(
            120deg,
            transparent 20%,
            rgba(139,85,255,.12) 48%,
            transparent 75%
        )!important;

    opacity:0!important;
    pointer-events:none!important;
    z-index:0!important;

    transition:opacity .28s ease!important;
}}

.contact-form:hover::before{{
    opacity:1!important;
}}

.contact-form > *{{
    position:relative!important;
    z-index:1!important;
}}

/* حرکت و Glow دکمه */
.contact-form button{{
    position:relative!important;
    overflow:hidden!important;

    transition:
        transform .20s ease,
        box-shadow .24s ease,
        filter .24s ease!important;
}}

.contact-form button::before{{
    content:""!important;
    position:absolute!important;
    top:0!important;
    bottom:0!important;
    left:-55%!important;

    width:42%!important;

    background:
        linear-gradient(
            90deg,
            transparent,
            rgba(255,255,255,.32),
            transparent
        )!important;

    transform:skewX(-20deg)!important;
    transition:left .55s ease!important;
}}

.contact-form button:hover{{
    transform:translateY(-2px)!important;
    filter:brightness(1.06)!important;

    box-shadow:
        0 17px 36px rgba(108,60,255,.38),
        0 0 22px rgba(129,80,255,.18)!important;
}}

.contact-form button:hover::before{{
    left:120%!important;
}}

.contact-form button:active{{
    transform:translateY(0) scale(.98)!important;
}}

/* لینک‌های تماس */
.contact-links{{
    display:flex!important;
    align-items:center!important;
    flex-wrap:wrap!important;
    gap:8px!important;
    margin-top:13px!important;
}}

.contact-links span,
.contact-links a{{
    min-height:34px!important;

    display:inline-flex!important;
    align-items:center!important;
    justify-content:center!important;
    gap:6px!important;

    padding:7px 11px!important;

    border:1px solid rgba(255,255,255,.13)!important;
    border-radius:11px!important;

    color:rgba(255,255,255,.92)!important;
    background:rgba(255,255,255,.075)!important;

    backdrop-filter:blur(8px)!important;

    font-size:9px!important;
    line-height:1.5!important;
    text-decoration:none!important;

    transition:
        transform .22s ease,
        background .22s ease,
        border-color .22s ease!important;
}}

.contact-links a:hover{{
    transform:translateY(-2px)!important;
    border-color:rgba(255,255,255,.30)!important;
    background:rgba(255,255,255,.14)!important;
}}

/* اتصال بصری دو سمت کادر تماس */
.contact::after{{
    content:""!important;
    position:absolute!important;

    width:320px!important;
    height:320px!important;

    left:50%!important;
    top:50%!important;

    border-radius:50%!important;

    background:
        radial-gradient(
            circle,
            rgba(174,138,255,.13),
            transparent 68%
        )!important;

    filter:blur(13px)!important;
    transform:translate(-50%,-50%)!important;

    pointer-events:none!important;
    z-index:-1!important;
}}

/* موبایل و تبلت */
@media(max-width:1020px){{
    .contact > div:nth-child(2){{
        transform:none!important;
    }}

    .contact-links{{
        justify-content:flex-start!important;
    }}
}}

@media(hover:none){{
    .contact-form:hover,
    .contact-form button:hover,
    .contact-links a:hover{{
        transform:none!important;
    }}
}}

@media(prefers-reduced-motion:reduce){{
    .contact-form,
    .contact-form button,
    .contact-form button::before,
    .contact-links a{{
        transition:none!important;
    }}
}}

/* CONTACT DETAILS FINAL END */


/* FOOTER REDESIGN FINAL START */

footer{{
    position:relative!important;
    overflow:hidden!important;

    margin-top:0!important;
    padding:48px 0 24px!important;

    color:#cfc7da!important;

    background:
        radial-gradient(
            circle at 12% 10%,
            rgba(108,60,255,.20),
            transparent 28%
        ),
        radial-gradient(
            circle at 88% 90%,
            rgba(126,76,255,.13),
            transparent 30%
        ),
        linear-gradient(
            155deg,
            #191320 0%,
            #120e18 55%,
            #0c0911 100%
        )!important;

    border-top:1px solid rgba(255,255,255,.06)!important;
}}

/* نور بالای فوتر */
footer::before{{
    content:""!important;
    position:absolute!important;
    top:0!important;
    right:12%!important;
    left:12%!important;

    height:1px!important;

    background:
        linear-gradient(
            90deg,
            transparent,
            rgba(139,85,255,.70),
            transparent
        )!important;
}}

/* شبکه اصلی فوتر */
.footer-grid{{
    position:relative!important;
    z-index:2!important;

    display:grid!important;
    grid-template-columns:1.55fr .85fr .85fr .75fr!important;
    align-items:start!important;
    gap:34px!important;
}}

/* برند */
.footer-brand{{
    max-width:390px!important;
}}

.footer-brand b{{
    display:flex!important;
    align-items:center!important;
    gap:9px!important;

    margin:0 0 9px!important;

    color:#fff!important;
    font-size:21px!important;
    line-height:1.4!important;
}}

.footer-brand b::before{{
    content:"ر"!important;

    width:38px!important;
    height:38px!important;

    display:grid!important;
    place-items:center!important;

    border:1px solid rgba(255,255,255,.13)!important;
    border-radius:12px!important;

    color:#fff!important;

    background:
        linear-gradient(
            145deg,
            #8b55ff,
            #4f1fc4
        )!important;

    box-shadow:
        0 12px 25px rgba(108,60,255,.25)!important;

    font-size:19px!important;
    font-weight:950!important;
}}

.footer-brand span{{
    display:block!important;
    max-width:360px!important;

    color:#a9a0b4!important;
    font-size:10px!important;
    line-height:1.9!important;
}}

/* ستون‌ها */
.footer-col strong{{
    position:relative!important;

    display:block!important;
    margin:0 0 14px!important;
    padding-bottom:9px!important;

    color:#fff!important;
    font-size:12px!important;
    line-height:1.5!important;
}}

.footer-col strong::after{{
    content:""!important;
    position:absolute!important;
    right:0!important;
    bottom:0!important;

    width:28px!important;
    height:2px!important;

    border-radius:999px!important;

    background:
        linear-gradient(
            90deg,
            #8b55ff,
            transparent
        )!important;
}}

.footer-col a{{
    position:relative!important;

    display:block!important;
    width:max-content!important;
    max-width:100%!important;

    margin-top:7px!important;
    padding-right:0!important;

    color:#aaa1b5!important;
    font-size:10px!important;
    line-height:1.7!important;
    text-decoration:none!important;

    transition:
        color .22s ease,
        transform .22s ease!important;
}}

.footer-col a::before{{
    content:""!important;

    position:absolute!important;
    right:0!important;
    top:50%!important;

    width:0!important;
    height:1px!important;

    background:#8b55ff!important;
    transform:translateY(-50%)!important;

    transition:width .22s ease!important;
}}

.footer-col a:hover{{
    color:#fff!important;
    transform:translateX(-8px)!important;
}}

.footer-col a:hover::before{{
    width:5px!important;
}}

/* جای نماد اعتماد */
.trust-badge{{
    min-height:78px!important;

    display:flex!important;
    align-items:center!important;
    justify-content:center!important;

    padding:10px!important;

    border:1px solid rgba(255,255,255,.08)!important;
    border-radius:16px!important;

    background:rgba(255,255,255,.045)!important;
    backdrop-filter:blur(8px)!important;
}}

.trust-badge:empty{{
    display:none!important;
}}

.trust-badge img{{
    max-width:84px!important;
    max-height:84px!important;
    object-fit:contain!important;
}}

/* خط و متن کپی‌رایت */
footer::after{{
    content:"© ۱۴۰۵ رشدیار — همه حقوق محفوظ است."!important;

    position:relative!important;
    z-index:2!important;

    display:block!important;

    width:min(1180px,calc(100% - 48px))!important;
    margin:30px auto 0!important;
    padding-top:18px!important;

    border-top:1px solid rgba(255,255,255,.07)!important;

    color:#756d80!important;
    font-size:9px!important;
    text-align:center!important;
}}

/* تبلت */
@media(max-width:1020px){{
    .footer-grid{{
        grid-template-columns:1.4fr 1fr 1fr!important;
        gap:25px!important;
    }}

    .trust-badge{{
        grid-column:1 / -1!important;
    }}
}}

/* موبایل */
@media(max-width:680px){{
    footer{{
        padding:38px 0 20px!important;
    }}

    .footer-grid{{
        grid-template-columns:1fr 1fr!important;
        gap:26px 18px!important;
    }}

    .footer-brand{{
        grid-column:1 / -1!important;
        max-width:none!important;
    }}

    .footer-brand span{{
        max-width:none!important;
    }}

    footer::after{{
        width:calc(100% - 22px)!important;
        margin-top:24px!important;
    }}
}}

@media(max-width:390px){{
    .footer-grid{{
        grid-template-columns:1fr!important;
    }}

    .footer-brand,
    .trust-badge{{
        grid-column:auto!important;
    }}
}}

@media(hover:none){{
    .footer-col a:hover{{
        transform:none!important;
    }}
}}

/* FOOTER REDESIGN FINAL END */



/* CONTACT FOOTER POLISH START */

/* =========================
   CONTACT FINAL POLISH
   ========================= */

.contact{{
    align-items:center!important;
}}

.contact > div:first-child,
.contact > div:nth-child(2){{
    align-self:center!important;
}}

.contact > div:first-child{{
    display:flex!important;
    flex-direction:column!important;
    justify-content:center!important;
}}

.contact > div:nth-child(2){{
    display:flex!important;
    align-items:center!important;
    justify-content:flex-start!important;
}}

/* فرم سمت چپ حفظ شود */
.contact-form{{
    width:100%!important;
    transform:translateX(-28px)!important;

    transition:
        transform .30s cubic-bezier(.2,.8,.2,1),
        box-shadow .30s ease,
        border-color .30s ease!important;
}}

.contact-form:hover{{
    transform:
        translateX(-28px)
        translateY(-4px)!important;

    border-color:rgba(255,255,255,.96)!important;

    box-shadow:
        0 28px 64px rgba(28,12,75,.30),
        0 0 30px rgba(129,80,255,.12),
        inset 0 1px 0 #fff!important;
}}

/* دکمه فرم */
.contact-form button{{
    position:relative!important;
    isolation:isolate!important;
    overflow:hidden!important;

    transition:
        transform .20s ease,
        filter .22s ease,
        box-shadow .22s ease!important;
}}

.contact-form button::after{{
    content:""!important;

    position:absolute!important;
    top:0!important;
    bottom:0!important;
    left:-60%!important;

    width:42%!important;

    background:
        linear-gradient(
            90deg,
            transparent,
            rgba(255,255,255,.34),
            transparent
        )!important;

    transform:skewX(-22deg)!important;
    transition:left .55s ease!important;

    z-index:-1!important;
}}

.contact-form button:hover{{
    transform:translateY(-2px)!important;
    filter:brightness(1.06)!important;

    box-shadow:
        0 17px 36px rgba(108,60,255,.38),
        0 0 24px rgba(129,80,255,.17)!important;
}}

.contact-form button:hover::after{{
    left:120%!important;
}}

.contact-form button:active{{
    transform:scale(.98)!important;
}}

/* لینک‌های تماس */
.contact-links{{
    display:flex!important;
    align-items:center!important;
    justify-content:flex-start!important;
    flex-wrap:wrap!important;

    gap:8px!important;
    margin-top:12px!important;
}}

/* حذف کادر خالی ساعت پشتیبانی */
.contact-links span:empty{{
    display:none!important;
}}

.contact-links span,
.contact-links a{{
    position:relative!important;

    min-height:34px!important;

    display:inline-flex!important;
    align-items:center!important;
    justify-content:center!important;
    gap:7px!important;

    margin:0!important;
    padding:7px 11px!important;

    border:1px solid rgba(255,255,255,.14)!important;
    border-radius:11px!important;

    color:rgba(255,255,255,.94)!important;
    background:rgba(255,255,255,.075)!important;

    backdrop-filter:blur(9px)!important;

    font-size:9px!important;
    line-height:1.5!important;
    text-decoration:none!important;

    transition:
        transform .22s ease,
        background .22s ease,
        border-color .22s ease!important;
}}

.contact-links a[href^="tel:"]::before{{
    content:"☎"!important;

    width:20px!important;
    height:20px!important;

    display:grid!important;
    place-items:center!important;

    border-radius:7px!important;
    background:rgba(255,255,255,.13)!important;

    font-size:10px!important;
}}

.contact-links a[href^="mailto:"]::before{{
    content:"✉"!important;

    width:20px!important;
    height:20px!important;

    display:grid!important;
    place-items:center!important;

    border-radius:7px!important;
    background:rgba(255,255,255,.13)!important;

    font-size:10px!important;
}}

.contact-links a:hover{{
    transform:translateY(-2px)!important;
    border-color:rgba(255,255,255,.32)!important;
    background:rgba(255,255,255,.14)!important;
}}


/* =========================
   FOOTER FINAL POLISH
   ========================= */

footer{{
    position:relative!important;
    overflow:hidden!important;

    margin-top:0!important;
    padding:46px 0 0!important;

    color:#cfc7da!important;

    background:
        radial-gradient(
            circle at 8% 8%,
            rgba(108,60,255,.20),
            transparent 30%
        ),
        radial-gradient(
            circle at 92% 92%,
            rgba(126,76,255,.13),
            transparent 31%
        ),
        linear-gradient(
            155deg,
            #191320 0%,
            #110d17 58%,
            #0b0910 100%
        )!important;

    border-top:1px solid rgba(255,255,255,.06)!important;
}}

footer::before{{
    content:""!important;

    position:absolute!important;
    top:0!important;
    right:12%!important;
    left:12%!important;

    height:1px!important;

    background:
        linear-gradient(
            90deg,
            transparent,
            rgba(139,85,255,.72),
            transparent
        )!important;
}}

/* چهار ستون اصلی */
.footer-grid{{
    position:relative!important;
    z-index:2!important;

    display:grid!important;

    grid-template-columns:
        minmax(260px,1.55fr)
        minmax(130px,.72fr)
        minmax(130px,.72fr)
        minmax(145px,.78fr)!important;

    align-items:start!important;
    gap:34px!important;
}}

/* برند */
.footer-brand{{
    max-width:390px!important;
}}

.footer-logo-row{{
    display:flex!important;
    align-items:center!important;
    gap:10px!important;
    margin-bottom:11px!important;
}}

.footer-logo-row img{{
    width:45px!important;
    height:45px!important;
    object-fit:cover!important;

    border-radius:13px!important;

    box-shadow:
        0 14px 30px rgba(108,60,255,.28)!important;
}}

.footer-logo-row b{{
    margin:0!important;

    color:#fff!important;
    font-size:22px!important;
    line-height:1.3!important;
}}

.footer-brand > span{{
    display:block!important;
    max-width:370px!important;

    color:#a9a0b4!important;
    font-size:10px!important;
    line-height:1.95!important;
}}

.footer-status{{
    width:max-content!important;

    display:inline-flex!important;
    align-items:center!important;
    gap:7px!important;

    margin-top:14px!important;
    padding:6px 10px!important;

    border:1px solid rgba(255,255,255,.07)!important;
    border-radius:999px!important;

    color:#a9a0b4!important;
    background:rgba(255,255,255,.035)!important;

    font-size:9px!important;
}}

.footer-status i{{
    width:7px!important;
    height:7px!important;

    display:block!important;

    border-radius:50%!important;
    background:#38d98a!important;

    box-shadow:
        0 0 0 4px rgba(56,217,138,.10),
        0 0 13px rgba(56,217,138,.45)!important;
}}

/* عنوان ستون‌ها */
.footer-col strong{{
    position:relative!important;

    display:block!important;

    margin:4px 0 15px!important;
    padding-bottom:10px!important;

    color:#fff!important;
    font-size:12px!important;
    line-height:1.5!important;
}}

.footer-col strong::after{{
    content:""!important;

    position:absolute!important;
    right:0!important;
    bottom:0!important;

    width:30px!important;
    height:2px!important;

    border-radius:999px!important;

    background:
        linear-gradient(
            90deg,
            #8b55ff,
            transparent
        )!important;
}}

/* لینک‌های فوتر */
.footer-col a{{
    position:relative!important;

    display:block!important;
    width:max-content!important;
    max-width:100%!important;

    margin-top:8px!important;

    color:#aaa1b5!important;

    font-size:10px!important;
    line-height:1.65!important;

    text-decoration:none!important;

    transition:
        color .22s ease,
        transform .22s ease!important;
}}

.footer-col a::before{{
    content:""!important;

    position:absolute!important;
    right:-9px!important;
    top:50%!important;

    width:4px!important;
    height:4px!important;

    border-radius:50%!important;
    background:#7040e8!important;

    opacity:0!important;
    transform:translateY(-50%) scale(.4)!important;

    transition:
        opacity .22s ease,
        transform .22s ease!important;
}}

.footer-col a:hover{{
    color:#fff!important;
    transform:translateX(-6px)!important;
}}

.footer-col a:hover::before{{
    opacity:1!important;
    transform:translateY(-50%) scale(1)!important;
}}

/* نماد اعتماد */
.trust-badge{{
    grid-column:1 / -1!important;

    min-height:0!important;

    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
    flex-wrap:wrap!important;
    gap:10px!important;

    margin-top:4px!important;
    padding:0!important;

    border:0!important;
    background:transparent!important;
}}

.trust-badge:empty{{
    display:none!important;
}}

.trust-badge:not(:empty){{
    padding-top:20px!important;
    border-top:1px solid rgba(255,255,255,.055)!important;
}}

.trust-badge a{{
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;

    min-width:88px!important;
    min-height:88px!important;

    padding:8px!important;

    border:1px solid rgba(255,255,255,.08)!important;
    border-radius:16px!important;

    background:rgba(255,255,255,.045)!important;
    backdrop-filter:blur(8px)!important;
}}

.trust-badge img{{
    max-width:72px!important;
    max-height:72px!important;
    object-fit:contain!important;
}}

/* پایین فوتر */
.footer-bottom{{
    position:relative!important;
    z-index:2!important;

    display:flex!important;
    align-items:center!important;
    justify-content:space-between!important;
    gap:15px!important;

    margin-top:31px!important;
    padding-top:18px!important;
    padding-bottom:20px!important;

    border-top:1px solid rgba(255,255,255,.065)!important;

    color:#777080!important;
    font-size:9px!important;
    line-height:1.7!important;
}}


/* تبلت */
@media(max-width:1020px){{
    .contact-form{{
        transform:none!important;
    }}

    .contact-form:hover{{
        transform:translateY(-4px)!important;
    }}

    .footer-grid{{
        grid-template-columns:
            minmax(240px,1.4fr)
            repeat(3,minmax(110px,1fr))!important;

        gap:25px!important;
    }}
}}


/* موبایل */
@media(max-width:680px){{
    footer{{
        padding-top:38px!important;
    }}

    .footer-grid{{
        grid-template-columns:1fr 1fr!important;
        gap:28px 20px!important;
    }}

    .footer-brand{{
        grid-column:1 / -1!important;
        max-width:none!important;
    }}

    .footer-legal{{
        grid-column:auto!important;
    }}

    .trust-badge{{
        grid-column:1 / -1!important;
    }}

    .footer-bottom{{
        flex-direction:column!important;
        align-items:center!important;
        justify-content:center!important;

        text-align:center!important;
    }}
}}

@media(max-width:420px){{
    .footer-grid{{
        grid-template-columns:1fr!important;
    }}

    .footer-brand,
    .trust-badge,
    .footer-legal{{
        grid-column:auto!important;
    }}

    .contact-links{{
        display:grid!important;
        grid-template-columns:1fr!important;
    }}

    .contact-links span,
    .contact-links a{{
        width:100%!important;
    }}
}}

@media(hover:none){{
    .contact-form:hover,
    .contact-form button:hover,
    .contact-links a:hover,
    .footer-col a:hover{{
        transform:none!important;
    }}
}}

@media(prefers-reduced-motion:reduce){{
    .contact-form,
    .contact-form button,
    .contact-form button::after,
    .contact-links a,
    .footer-col a{{
        transition:none!important;
    }}
}}

/* CONTACT FOOTER POLISH END */



/* FOOTER CLEANUP FINAL START */

/* حذف مربع حرف ر؛ فقط لوگوی اصلی بماند */
.footer-brand b::before,
.footer-logo-row b::before{{
    display:none!important;
    content:none!important;
}}

/* لوگو و نام برند مرتب‌تر */
.footer-logo-row{{
    gap:9px!important;
}}

.footer-logo-row img{{
    width:42px!important;
    height:42px!important;
}}

.footer-logo-row b{{
    font-size:21px!important;
}}

/* نماد اعتماد اگر محتوای واقعی ندارد، حذف شود */
.trust-badge:empty,
.trust-badge:not(:has(img)):not(:has(a)):not(:has(iframe)){{
    display:none!important;
    min-height:0!important;
    margin:0!important;
    padding:0!important;
    border:0!important;
}}

/* جلوگیری از باقی‌ماندن خط خالی بزرگ */
.trust-badge{{
    min-height:0!important;
}}

.trust-badge:not(:empty){{
    margin-top:18px!important;
    padding-top:16px!important;
}}

/* فوتر کمی جمع‌وجورتر */
footer{{
    padding-top:40px!important;
}}

.footer-grid{{
    gap:28px!important;
}}

.footer-bottom{{
    display:flex!important;
    visibility:visible!important;
    opacity:1!important;

    margin-top:24px!important;
    padding-top:15px!important;
    padding-bottom:17px!important;

    color:#938a9d!important;
    font-size:9px!important;
}}

/* اگر قانون قدیمی pseudo-element کپی‌رایت دارد، حذف شود */
footer::after{{
    display:none!important;
    content:none!important;
}}

/* جلوگیری از ارتفاع اضافه پایین فوتر */
.public-footer{{
    padding-bottom:0!important;
}}

/* موبایل */
@media(max-width:680px){{
    footer{{
        padding-top:34px!important;
    }}

    .footer-grid{{
        gap:24px 18px!important;
    }}

    .footer-bottom{{
        margin-top:21px!important;
        padding-bottom:15px!important;
    }}
}}

/* FOOTER CLEANUP FINAL END */


.app-download-box{{padding:18px;
    gap:15px;}}

.download-icon,
.download-app-icon{{
    width:56px!important;
    height:56px!important;
}}

.download-header h3{{
    margin-bottom:4px!important;
}}

.download-btn{{min-height:40px;
    padding:8px 13px;
    font-size:10px;}}

/* کارت‌های پلن */
.pricing{{
    gap:15px!important;
}}

.price-card{{
    padding:24px 20px!important;
}}

.price-card h3{{
    font-size:20px!important;
}}

.price-card .price{{font-size:30px;line-height:1.2;}}

.price-card .old-price,
.price-card .duration,
.price-card li{{font-size:10px;line-height:1.8;}}

.price-card .btn,
.price-card button,
.price-card a{{
    min-height:43px!important;
    font-size:12px!important;
}}

/* FAQ */
.faq-item summary{{font-size:11px;
    padding:13px 0;}}

.faq-item p{{font-size:10px;
    line-height:1.8;}}

/* تماس */
.contact{{
    padding:28px!important;
}}

.contact h2{{
    font-size:32px!important;
}}

.contact input,
.contact textarea{{font-size:11px;
    padding:10px 12px;min-height:96px;}}

.contact textarea{{
    min-height:105px!important;
}}

.contact button{{
    min-height:43px!important;
    font-size:12px!important;
}}

/* فوتر */

/* CONTACT FORM FIELD FIX START */

.contact form input{{
    width:100%!important;
    height:44px!important;
    min-height:44px!important;
    padding:10px 13px!important;
    font-size:12px!important;
    line-height:1.4!important;
    border-radius:12px!important;
    resize:none!important;
}}

.contact form textarea{{
    width:100%!important;
    height:118px!important;
    min-height:118px!important;
    padding:12px 13px!important;
    font-size:12px!important;
    line-height:1.8!important;
    border-radius:12px!important;
    resize:vertical!important;
}}

.contact form button{{
    width:100%!important;
    min-height:44px!important;
    padding:10px 16px!important;
    font-size:12px!important;
    border-radius:12px!important;
}}

.contact form{{
    gap:10px!important;
}}

/* CONTACT FORM FIELD FIX END */


.footer{{font-size:10px;padding:42px 0;}}

.footer h3,
.footer h4{{font-size:12px;}}

.footer a,
.footer p{{font-size:9px;line-height:1.75;}}

/* تبلت */
@media(max-width:1020px){{
    .hero-copy{{
        padding:38px 32px 26px!important;
    }}

    .hero h1{{
        font-size:clamp(28px,5vw,38px)!important;
        margin-inline:auto!important;
    }}

    .hero-lead{{
        margin-inline:auto!important;
    }}
}}

/* موبایل */
@media(max-width:680px){{
    .hero-copy{{
        padding:34px 19px 24px!important;
    }}

    .hero h1{{
        font-size:clamp(24px,7.8vw,30px)!important;
        line-height:1.32!important;
    }}

    .hero-lead{{
        font-size:12px!important;
    }}

    .section{{
        padding:42px 0!important;
    }}

    .section-head h2,
    .story-copy h2,
    .demo-title,
    .compare-title,
    .pricing-title,
    .contact h2,
    .trust-faq h2,
    .recommender h2{{
        font-size:25px!important;
    }}

    .section-head p{{
        font-size:12px!important;
    }}

    .contact{{
        padding:20px!important;
    }}
}}

/* ===== RASHDYAR TYPOGRAPHY SYSTEM END ===== */


.app-download-box{{
display:flex;
align-items:center;
gap:20px;
margin-top:25px;
padding:25px;
border-radius:28px;
background:#fff;
border:1px solid #ece6ff;
box-shadow:0 15px 40px rgba(108,60,255,.08);
}}

.download-icon{{
width:70px;
height:70px;
border-radius:22px;
background:#6c3cff;
color:white;
display:flex;
align-items:center;
justify-content:flex-start;
font-size:36px;
}}

.download-info h3{{
margin:0 0 8px;
font-size:18px;
}}

.download-info p{{
margin:0 0 15px;
color:#777;
max-width:520px;
line-height:1.8;
}}

.download-card{{
background:#fff;
border:1px solid #eee;
border-radius:28px;
padding:28px;
margin-top:25px;
}}

.download-header{{
display:flex;
align-items:center;
gap:18px;
}}

.download-header img{{
width:70px;
height:70px;
border-radius:20px;
}}

.download-actions{{
display:flex;
gap:12px;
margin-top:20px;
flex-wrap:wrap;
}}

.download-btn{{
display:flex;
align-items:center;
justify-content:flex-start;
gap:10px;
padding:11px 18px;
border-radius:16px;
background:#ffffff;
border:1px solid #e9e3ff;
color:#171725;
text-decoration:none;
font-weight:900;
transition:.2s;
min-width:145px;
}}

.download-btn:hover{{
transform:translateY(-2px);
box-shadow:0 10px 25px rgba(108,60,255,.15);
}}

.download-btn img{{
width:28px;
height:28px;
object-fit:contain;
}}

.download-btn.primary{{
background:linear-gradient(135deg,#6c3cff,#4d22d8);
color:white;
border:none;
}}

.download-actions{{
display:flex;
gap:10px;
flex-wrap:nowrap;
align-items:center;
margin-top:0;
justify-content:flex-start;
transform:translateX(-10px);
}}

.download-card{{
background:#fff;
border:1px solid #ebe7ff;
border-radius:26px;
padding:20px 30px;
box-shadow:0 18px 45px rgba(108,60,255,.08);
display:flex;
align-items:center;
justify-content:space-between;
gap:24px;
direction:rtl;
min-height:110px;
}}

.download-header{{
display:flex;
align-items:center;
justify-content:space-between;
gap:20px;
flex:1;
}}

.download-app-icon{{
width:56px;
height:56px;
border-radius:16px;
object-fit:cover;
box-shadow:0 10px 25px rgba(108,60,255,.22);
}}

.download-header h3{{
margin:0 0 8px;
font-size:22px;
}}

.download-header p{{
margin:0;
color:#777;
font-size:14px;
}}

.download-actions{{
margin-top:14px;
display:flex;
justify-content:flex-start;
gap:12px;
flex-wrap:wrap;
}}

.download-btn{{
height:46px;
min-width:150px;
border-radius:15px;
font-size:14px;
}}

.download-btn img{{
width:24px;
height:24px;
}}

@media(max-width:600px){{
.download-header{{
align-items:flex-start;
}}
.download-actions{{
flex-direction:column;
}}
.download-btn{{
width:100%;
}}
}}

@media(max-width:600px){{
.download-actions{{
flex-direction:column;
}}
.download-btn{{
width:100%;
}}
}}

.brand-logo{{
width:42px;
height:42px;
border-radius:12px;
object-fit:cover;
vertical-align:middle;
}}

.plans-section{{
padding-top:35px;
}}

#download{{
padding-bottom:25px;
}}

#download + .section{{
padding-top:35px;
}}

.download-card{{
}}
@media(max-width:800px){{
.download-card{{
flex-direction:column;
align-items:stretch;
}}
.download-actions{{
flex-wrap:wrap;
}}
}}
</style>
</head>
<body>
{announcement}
<header class="site-header">
  <div class="container">
    <nav class="nav">
      <a class="brand" href="/"><img src="/assets/rashdyar-logo.png" class="brand-logo"><span>رشدیار</span></a>
      <div class="nav-links" id="navLinks">
        <a href="#story">چرا رشدیار</a><a href="#features">امکانات</a><a href="#demo">دموی هوشمند</a><a href="#screens">محیط اپ</a><a href="#plans">قیمت‌ها</a><a href="#faq">سؤالات</a>
      </div>
      <div class="nav-actions">
        <button class="theme-toggle" id="themeToggle" type="button" aria-label="تغییر حالت نمایش">☾</button>
        <a class="nav-login" href="#contact">ورود</a>
        <a class="nav-start" href="{esc(settings["download_url"])}">{esc(settings["primary_button_text"])}</a>
        <button class="menu-button" id="menuButton" type="button" aria-label="نمایش منو">☰</button>
      </div>
    </nav>
  </div>
</header>

<main>
<section class="hero">
  <div class="container">
    <div class="hero-shell">
      <div class="hero-copy">
        <span class="hero-kicker">✦ هوش مصنوعی فارسی برای تصمیم و اجرای بهتر محتوا</span>
        <h1>{esc(settings["site_title"])}<strong>در یک اپلیکیشن</strong></h1>
        <p class="hero-lead">{esc(settings["site_subtitle"])}</p>
        <div class="hero-actions">
          <a class="btn-primary" href="{esc(settings["download_url"])}">🚀 {esc(settings["primary_button_text"])}</a>
          <a class="btn-secondary" href="#demo">دموی هوشمند را امتحان کن</a>
        </div>
        <div class="hero-trust"><span>شروع با پلن رایگان</span><span>رابط کاملاً فارسی</span><span>مدیریت مرکزی اشتراک</span></div>
      </div>
      <div class="visual-stage" id="visualStage">
        <div class="visual-glow"></div>
        <div class="float-note note-one"><b>تحلیل پیج</b><span>ضعف‌ها و فرصت‌های رشد</span></div>
        <div class="float-note note-two"><b>AI Studio</b><span>هوک، سناریو، تصویر و CTA</span></div>
        <div class="phone phone-left" data-depth="10"><img src="/assets/screen-3.webp" loading="eager" alt="AI Studio رشدیار"></div>
        <div class="phone phone-main" data-depth="18"><img src="/assets/screen-1.webp" loading="eager" alt="داشبورد رشدیار"></div>
        <div class="phone phone-right" data-depth="12"><img src="/assets/screen-2.webp" loading="eager" alt="مرکز ترندهای رشدیار"></div>
      </div>
    </div>
    <div class="hero-metrics reveal">
      <div class="metric"><b>۵</b><span>بخش اصلی اپ</span></div><div class="metric"><b>۱۲+</b><span>ابزار هوشمند</span></div><div class="metric"><b>۲۴/۷</b><span>دسترسی به ابزارها</span></div><div class="metric"><b>RTL</b><span>تجربه کاملاً فارسی</span></div>
    </div>
  </div>
</section>

<section class="section" id="why"><div class="container story reveal">
  <div class="story-copy">
    <small>مسئله‌ای که رشدیار حل می‌کند</small><h2>کمتر بین ابزارها جابه‌جا شو؛ بیشتر اجرا کن.</h2>
    <p>وقتی تحلیل، ایده، سناریو، تصویر و برنامه انتشار از هم جدا باشند، زمان زیادی صرف تصمیم‌گیری و هماهنگ‌کردن خروجی‌ها می‌شود.</p>
    <div class="story-points">
      <div class="story-point"><b>۱</b><span>وضعیت پیج را در یک نمای روشن تحلیل کن.</span></div>
      <div class="story-point"><b>۲</b><span>ترند و ایده مناسب حوزه‌ات را پیدا کن.</span></div>
      <div class="story-point"><b>۳</b><span>خروجی آماده اجرا برای انتشار بعدی بگیر.</span></div>
    </div>
  </div>
  <div class="story-visual"><div class="story-card story-a"><b>یک جریان یکپارچه</b><span>از تصمیم تا انتشار</span></div><div class="story-card story-b"><b>خروجی قابل اجرا</b><span>نه پیشنهادهای مبهم</span></div><img src="/assets/screen-4.webp" loading="lazy" alt="برنامه‌ریز رشدیار"></div>
</div></section>

<section class="section">
  <div class="container">
    <div class="section-head reveal"><small>امکانات اصلی</small><h2>یک جعبه‌ابزار منسجم برای رشد محتوا.</h2><p>چیدمان امکانات براساس مسیر واقعی کاربر طراحی شده است.</p></div>
    <div class="bento reveal">
      <article class="bento-card bento-main"><span class="bento-label">۰۱ / تحلیل</span><h3>بفهم چه چیزی جلوی رشد پیج را گرفته است.</h3><p>رشد، تعامل، زمان مناسب انتشار و فرصت‌های قابل اجرا را در یک نمای روشن ببین.</p><img src="/assets/screen-1.webp" loading="lazy" alt="داشبورد تحلیل رشدیار"></article>
      <article class="bento-card bento-accent"><span class="bento-label">۰۲ / ترند</span><h3>قبل از اشباع‌شدن، موضوع مناسب را پیدا کن.</h3><p>ترندها و فرصت‌های مرتبط با حوزه فعالیتت را سریع‌تر کشف کن.</p></article>
      <article class="bento-card"><span class="bento-label">۰۳ / ساخت</span><h3>هوک، سناریو، کپشن و CTA را یک‌جا بساز.</h3><p>خروجی‌های یکپارچه برای تولید محتوای سریع‌تر.</p><span class="bento-mini-visual"></span></article>
      <article class="bento-card"><span class="bento-label">۰۴ / تصویر</span><h3>برای هر محتوا تصویر اختصاصی آماده کن.</h3><p>ساخت و ویرایش تصویر با هوش مصنوعی در همان جریان کاری.</p></article>
      <article class="bento-card bento-purple"><span class="bento-label">۰۵ / برنامه</span><h3>قدم بعدی را دقیق بدان.</h3><p>هدف، مخاطب و مدت برنامه را مشخص کن و مسیر اجرایی بگیر.</p></article>
    </div>
  </div>
</section>

<section class="section" id="demo">
  <div class="container">
    <div class="section-head reveal"><small>دموی تعاملی</small><h2>یک نمونه خروجی را همین‌جا ببین.</h2><p>این دمو برای نمایش تجربه محصول است و درخواست واقعی API ارسال نمی‌کند.</p></div>
    <div class="demo-shell reveal">
      <div class="demo-controls">
        <h3>موضوع محتوایت چیست؟</h3>
        <label for="demoTopic">موضوع</label><input id="demoTopic" value="فروش کفش زنانه" maxlength="80">
        <label for="demoGoal">هدف</label><select id="demoGoal"><option>افزایش فروش</option><option>افزایش تعامل</option><option>افزایش فالوور</option><option>برندسازی</option></select>
        <label for="demoTone">لحن</label><select id="demoTone"><option>صمیمی و حرفه‌ای</option><option>انرژی‌بخش</option><option>آموزشی</option><option>مینیمال</option></select>
        <button id="runDemo" type="button">ساخت نمونه خروجی</button>
      </div>
      <div class="demo-output">
        <h3>خروجی پیشنهادی رشدیار</h3>
        <div class="demo-output-grid">
          <div class="demo-result"><b>HOOK</b><p id="demoHook">قبل از خرید کفش بعدی، این ۳ نکته را ببین.</p></div>
          <div class="demo-result"><b>CTA</b><p id="demoCta">مدل موردعلاقه‌ات را پیام بده تا راهنمایی‌ات کنیم.</p></div>
          <div class="demo-result"><b>سناریو</b><p id="demoScript">شروع با یک اشتباه رایج، نمایش سه انتخاب و پایان با پیشنهاد خرید.</p></div>
          <div class="demo-result"><b>هشتگ</b><p id="demoTags">#کفش_زنانه #استایل #خرید_آنلاین</p></div>
        </div>
      </div>
    </div>
  </div>
</section>

<section class="section" id="screens">
  <div class="container">
    <div class="section-head reveal"><small>محیط واقعی اپ اندروید</small><h2>قبل از نصب، صفحه‌های اصلی رشدیار را ببین.</h2><p>برای بزرگ‌نمایی روی هر تصویر کلیک کن.</p></div>
    <div class="gallery-shell reveal">
      <div class="gallery-track">
        <div class="gallery-phone" data-full="/assets/screen-5.webp"><img src="/assets/screen-5.webp" loading="lazy" alt="پروفایل رشدیار"></div>
        <div class="gallery-phone" data-full="/assets/screen-4.webp"><img src="/assets/screen-4.webp" loading="lazy" alt="برنامه‌ریز رشدیار"></div>
        <div class="gallery-phone" data-full="/assets/screen-3.webp"><img src="/assets/screen-3.webp" loading="lazy" alt="AI Studio رشدیار"></div>
        <div class="gallery-phone" data-full="/assets/screen-2.webp"><img src="/assets/screen-2.webp" loading="lazy" alt="ترندهای رشدیار"></div>
        <div class="gallery-phone" data-full="/assets/screen-1.webp"><img src="/assets/screen-1.webp" loading="lazy" alt="داشبورد رشدیار"></div>
      </div>
    </div>
  </div>
</section>

<section class="section"><div class="container timeline-wrap reveal">
  <div class="timeline-card"><h3>مسیر رشد در رشدیار</h3><div class="timeline">
    <div class="timeline-step"><span class="timeline-number">۱</span><b>تحلیل کن</b><span>وضعیت فعلی پیج</span></div>
    <div class="timeline-step"><span class="timeline-number">۲</span><b>ایده بگیر</b><span>ترند و پیشنهاد هوشمند</span></div>
    <div class="timeline-step"><span class="timeline-number">۳</span><b>محتوا بساز</b><span>هوک، سناریو و تصویر</span></div>
    <div class="timeline-step"><span class="timeline-number">۴</span><b>منتشر کن</b><span>برنامه و قدم بعدی</span></div>
  </div></div>
  <div class="outcome-card"><h3>خروجی‌های قابل استفاده، نه پیشنهادهای مبهم</h3><p>هر مرحله به یک اقدام روشن تبدیل می‌شود.</p><div class="outcome-grid"><div><b>Hook</b><span>شروع جذاب</span></div><div><b>CTA</b><span>دعوت به اقدام</span></div><div><b>Plan</b><span>برنامه انتشار</span></div></div></div>
</div></section>

<section class="section" id="comparison">
  <div class="container">
    <div class="section-head reveal"><small>مقایسه کاربردی</small><h2>چرا رشدیار فقط یک ابزار عمومی نیست؟</h2><p>این مقایسه بر مبنای نوع قابلیت‌هاست، نه ادعای برتری مطلق.</p></div>
    <div class="compare-wrap reveal"><table class="compare-table">
      <thead><tr><th>قابلیت</th><th>ابزار گفت‌وگوی عمومی</th><th>ابزار طراحی عمومی</th><th class="best">رشدیار</th></tr></thead>
      <tbody>
        <tr><td>تحلیل اختصاصی پیج</td><td class="no">—</td><td class="no">—</td><td class="yes">✓</td></tr>
        <tr><td>مرکز ترندها</td><td class="no">—</td><td class="no">—</td><td class="yes">✓</td></tr>
        <tr><td>سناریو و کپشن</td><td class="yes">✓</td><td class="no">—</td><td class="yes">✓</td></tr>
        <tr><td>ساخت و ویرایش تصویر</td><td class="no">—</td><td class="yes">✓</td><td class="yes">✓</td></tr>
        <tr><td>برنامه انتشار</td><td class="no">—</td><td class="no">—</td><td class="yes">✓</td></tr>
      </tbody>
    </table></div>
  </div>
</section>

<section class="section">
  <div class="container recommender reveal">
    <div>
      <h3>کدام پلن برای تو مناسب‌تر است؟</h3>
      <div class="range-row"><label><span>تعداد محتوا در هفته</span><b id="postCountLabel">۴</b></label><input id="postCount" type="range" min="1" max="21" value="4"></div>
      <div class="range-row"><label><span>تولید تصویر در ماه</span><b id="imageCountLabel">۸</b></label><input id="imageCount" type="range" min="0" max="60" value="8"></div>
    </div>
    <div class="recommendation"><small>پیشنهاد تقریبی سایت</small><b id="planSuggestion">پلن حرفه‌ای ماهانه</b><p id="planReason">برای تولید منظم محتوا و استفاده از ابزارهای هوشمند مناسب‌تر است.</p></div>
  </div>
</section>



<section class="section" id="download">
<div class="container">

<div class="download-card">

<div class="download-header">
<img src="/assets/rashdyar-logo.png" class="download-app-icon">

<div>
<h3>دانلود اپلیکیشن رشدیار</h3>
<p>
آخرین نسخه اندروید رشدیار را دریافت کنید و تولید محتوا و رشد پیج خود را شروع کنید.
</p>
</div>

</div>


<div class="download-actions">

<a class="download-btn primary" href="{esc(s.get('apk_url',''))}">
⬇️ دانلود مستقیم APK
</a>


<a class="download-btn" href="{esc(s.get('market_url','#'))}">
<img src="/assets/bazar.svg">
دریافت از بازار
</a>

<a class="download-btn" href="{esc(s.get('google_play_url','#'))}">
<img src="/assets/google-play.svg">
Google Play
</a>


</div>

</div>

</div>
</section>

<section class="section plans-section" id="pricing">
  <div class="container">
    <div class="section-head reveal"><small>پلن‌های اشتراک</small><h2>پلن مناسب کارت را انتخاب کن.</h2><p>قیمت و امکانات مستقیماً از پنل مدیریت کنترل می‌شوند.</p></div>
    <div class="pricing reveal">{build_plans_html(plans)}</div>
  </div>
</section>

<section class="section" id="faq"><div class="container trust-faq reveal">
  <div class="trust-card"><h3>چرا رشدیار؟</h3>
    <div class="trust-item"><b>یک مسیر یکپارچه</b><p>تحلیل، ساخت محتوا و برنامه‌ریزی در یک جریان انجام می‌شوند.</p></div>
    <div class="trust-item"><b>تجربه مناسب کاربر فارسی</b><p>رابط فارسی و راست‌چین بدون پیچیدگی اضافه.</p></div>
    <div class="trust-item"><b>مدیریت مرکزی اشتراک</b><p>پلن و سهمیه از سرور مدیریت می‌شود.</p></div>
  </div>
  <div class="faq-card"><h3>سؤالات متداول</h3>
    <details><summary>نسخه رایگان چه امکاناتی دارد؟</summary><p>امکانات نسخه رایگان براساس پلن فعال در بخش قیمت‌ها نمایش داده می‌شود.</p></details>
    <details><summary>آیا برای استفاده باید پیج را متصل کنم؟</summary><p>بعضی ابزارها بدون اتصال قابل استفاده‌اند؛ تحلیل اختصاصی به اطلاعات پیج نیاز دارد.</p></details>
    <details><summary>اشتراک چگونه فعال می‌شود؟</summary><p>پس از تکمیل پرداخت، فعال‌سازی از سیستم مرکزی اشتراک انجام می‌شود.</p></details>
    <details><summary>آیا تصاویر سایت واقعی‌اند؟</summary><p>بله؛ تصاویر بخش محیط اپ از نسخه واقعی اندروید رشدیار هستند.</p></details>
  </div>
</div></section>

<section class="section"><div class="container contact reveal">
  <div><h2>{esc(settings["contact_title"])}</h2><p>{esc(settings["contact_text"])}</p><div class="contact-links"><span>{esc(settings["support_hours"])}</span>{''.join(support_links)}</div></div>
  <div>{flash}<form class="contact-form" method="post" action="/contact">
    <input name="name" maxlength="100" required placeholder="نام شما"><input name="contact" maxlength="160" required placeholder="شماره تماس، ایمیل یا آیدی تلگرام"><input name="subject" maxlength="160" placeholder="موضوع پیام"><textarea name="message" maxlength="3000" required placeholder="پیام شما"></textarea><button type="submit">ارسال پیام برای تیم رشدیار</button>
  </form></div>
</div></section>
</main>

<footer>
  <div class="container footer-grid public-footer">

    <div class="footer-brand">
      <div class="footer-logo-row">
        <img src="/assets/rashdyar-logo.png" alt="لوگوی رشدیار">
        <b>رشدیار</b>
      </div>

      <span>{esc(settings["footer_text"])}</span>

      <div class="footer-status">
        <i></i>
        سرویس رشدیار فعال است
      </div>
    </div>

    <div class="footer-col">
      <strong>محصول</strong>
      <a href="#features">امکانات</a>
      <a href="#demo">دموی هوشمند</a>
      <a href="#screens">محیط اپ</a>
      <a href="#pricing">پلن‌ها</a>
    </div>

    <div class="footer-col">
      <strong>پشتیبانی</strong>
      <a href="#faq">سؤالات متداول</a>
      <a href="#contact">تماس با ما</a>
      <a href="/account/login">ورود کاربران</a>
    </div>

    <div class="footer-col footer-legal">
      <strong>قوانین</strong>
      <a href="/privacy">حریم خصوصی</a>
      <a href="/terms">شرایط استفاده</a>
      <a href="/refund-policy">قوانین بازگشت وجه</a>
    </div>

    <div class="trust-badge">
      {(globals().get('s') or {}).get('enamad_html','')}
    </div>

  </div>

  <div class="container footer-bottom">
    <span>© ۱۴۰۵ رشدیار؛ همه حقوق محفوظ است.</span>
    <span>نسخه وب ۱.۰</span>
  </div>
</footer>

<div class="lightbox" id="lightbox"><button class="lightbox-close" id="lightboxClose" type="button">×</button><img id="lightboxImage" alt="نمای بزرگ اپ"></div>

<script>
(function(){{
  const root=document.documentElement;
  const saved=localStorage.getItem("rashdyar-theme");
  if(saved) root.dataset.theme=saved;
  const themeToggle=document.getElementById("themeToggle");
  function refreshThemeIcon(){{themeToggle.textContent=root.dataset.theme==="dark"?"☀":"☾"}}
  refreshThemeIcon();
  themeToggle.addEventListener("click",()=>{{
    root.dataset.theme=root.dataset.theme==="dark"?"light":"dark";
    localStorage.setItem("rashdyar-theme",root.dataset.theme);
    refreshThemeIcon();
  }});

  const menuButton=document.getElementById("menuButton");
  const navLinks=document.getElementById("navLinks");
  if(menuButton&&navLinks){{
    menuButton.addEventListener("click",()=>navLinks.classList.toggle("open"));
    navLinks.querySelectorAll("a").forEach(link=>link.addEventListener("click",()=>navLinks.classList.remove("open")));
  }}

  const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{{if(entry.isIntersecting)entry.target.classList.add("visible")}}),{{threshold:.12}});
  document.querySelectorAll(".reveal").forEach(element=>observer.observe(element));

  const stage=document.getElementById("visualStage");
  if(stage && matchMedia("(pointer:fine)").matches){{
    stage.addEventListener("mousemove",event=>{{
      const rect=stage.getBoundingClientRect();
      const x=(event.clientX-rect.left)/rect.width-.5;
      const y=(event.clientY-rect.top)/rect.height-.5;
      stage.querySelectorAll("[data-depth]").forEach(item=>{{
        const depth=Number(item.dataset.depth||10);
        const base=item.classList.contains("phone-main")?"translateX(-50%) ":"";
        item.style.transform=base+"translate("+(x*depth)+"px,"+(y*depth)+"px) "+(item.classList.contains("phone-left")?"rotate(-8deg)":item.classList.contains("phone-right")?"rotate(8deg)":"");
      }});
    }});
    stage.addEventListener("mouseleave",()=>stage.querySelectorAll("[data-depth]").forEach(item=>item.style.transform=""));
  }}

  const demoTopic=document.getElementById("demoTopic");
  const demoGoal=document.getElementById("demoGoal");
  const demoTone=document.getElementById("demoTone");
  document.getElementById("runDemo").addEventListener("click",()=>{{
    const topic=(demoTopic.value||"موضوع شما").trim();
    const goal=demoGoal.value;
    const tone=demoTone.value;
    document.getElementById("demoHook").textContent="قبل از اینکه درباره «"+topic+"» تصمیم بگیری، این نکته را ببین.";
    document.getElementById("demoCta").textContent=goal==="افزایش فروش"?"برای دریافت پیشنهاد مناسب، همین حالا پیام بده.":"نظرت را بنویس و این محتوا را برای دوستت بفرست.";
    document.getElementById("demoScript").textContent="شروع "+tone+"، نمایش یک مشکل رایج، ارائه ۳ راه‌حل و پایان با دعوت به اقدام.";
    document.getElementById("demoTags").textContent="#"+topic.replaceAll(" ","_")+" #محتوای_هوشمند #رشدیار";
  }});

  const lightbox=document.getElementById("lightbox");
  const lightboxImage=document.getElementById("lightboxImage");
  document.querySelectorAll(".gallery-phone").forEach(card=>card.addEventListener("click",()=>{{lightboxImage.src=card.dataset.full;lightbox.classList.add("open")}}));
  function closeLightbox(){{lightbox.classList.remove("open");lightboxImage.src=""}}
  document.getElementById("lightboxClose").addEventListener("click",closeLightbox);
  lightbox.addEventListener("click",event=>{{if(event.target===lightbox)closeLightbox()}});
  document.addEventListener("keydown",event=>{{if(event.key==="Escape")closeLightbox()}});

  const postCount=document.getElementById("postCount");
  const imageCount=document.getElementById("imageCount");
  function recommend(){{
    const posts=Number(postCount.value),images=Number(imageCount.value);
    document.getElementById("postCountLabel").textContent=posts;
    document.getElementById("imageCountLabel").textContent=images;
    let title="پلن رایگان",reason="برای آشنایی و استفاده محدود مناسب است.";
    if(posts>5||images>10){{title="پلن حرفه‌ای ماهانه";reason="برای تولید منظم محتوا و استفاده بیشتر از ابزارهای هوشمند مناسب‌تر است."}}
    if(posts>14||images>35){{title="پلن حرفه‌ای سه‌ماهه";reason="برای استفاده مستمر، حجم خروجی بیشتر و صرفه اقتصادی بهتر پیشنهاد می‌شود."}}
    document.getElementById("planSuggestion").textContent=title;
    document.getElementById("planReason").textContent=reason;
  }}
  postCount.addEventListener("input",recommend);imageCount.addEventListener("input",recommend);recommend();
}})();
</script>

<!-- ANCHOR SCROLL FIX START -->
<script>
(function() {{
    function scrollToCurrentAnchor() {{
        const hash = window.location.hash;

        if (!hash || hash.length < 2) {{
            return;
        }}

        const target = document.getElementById(
            decodeURIComponent(hash.substring(1))
        );

        if (!target) {{
            return;
        }}

        const header =
            document.querySelector(".nav") ||
            document.querySelector("header");

        const headerHeight = header
            ? header.getBoundingClientRect().height
            : 72;

        const top =
            target.getBoundingClientRect().top +
            window.scrollY -
            headerHeight -
            20;

        window.scrollTo({{
            top: Math.max(0, top),
            behavior: "auto"
        }});
    }}

    window.addEventListener("load", function() {{
        setTimeout(scrollToCurrentAnchor, 300);
        setTimeout(scrollToCurrentAnchor, 900);
    }});

    window.addEventListener("hashchange", function() {{
        setTimeout(scrollToCurrentAnchor, 50);
    }});
}})();
</script>
<!-- ANCHOR SCROLL FIX END -->


<!-- FLOAT NOTE CLICK SCRIPT START -->
<script>
document.addEventListener("DOMContentLoaded", function() {{
    const notes = document.querySelectorAll(".float-note");

    notes.forEach(function(note) {{
        note.setAttribute("tabindex", "0");
        note.setAttribute("role", "button");

        function toggleNote(event) {{
            event.stopPropagation();

            notes.forEach(function(other) {{
                if (other !== note) {{
                    other.classList.remove("open");
                }}
            }});

            note.classList.toggle("open");
        }}

        note.addEventListener("click", toggleNote);

        note.addEventListener("keydown", function(event) {{
            if (event.key === "Enter" || event.key === " ") {{
                event.preventDefault();
                toggleNote(event);
            }}
        }});
    }});

    document.addEventListener("click", function() {{
        notes.forEach(function(note) {{
            note.classList.remove("open");
        }});
    }});
}});
</script>
<!-- FLOAT NOTE CLICK SCRIPT END -->





<!-- FAQ ACCORDION SCRIPT START -->
<script>
document.addEventListener("DOMContentLoaded", function() {{
    const faqSection = document.getElementById("faq");

    if (!faqSection) {{
        return;
    }}

    const detailItems = Array.from(
        faqSection.querySelectorAll("details")
    );

    detailItems.forEach(function(item) {{
        item.addEventListener("toggle", function() {{
            if (!item.open) {{
                return;
            }}

            detailItems.forEach(function(other) {{
                if (other !== item && other.open) {{
                    other.open = false;
                }}
            }});
        }});
    }});

    const customItems = Array.from(
        faqSection.querySelectorAll(".faq-item")
    );

    customItems.forEach(function(item) {{
        const question = item.querySelector(
            ".faq-question"
        );

        const answer = item.querySelector(
            ".faq-answer"
        );

        if (!question || !answer) {{
            return;
        }}

        question.setAttribute("role", "button");
        question.setAttribute("tabindex", "0");
        question.setAttribute("aria-expanded", "false");

        answer.hidden = true;

        function toggleItem() {{
            const willOpen =
                !item.classList.contains("open");

            customItems.forEach(function(other) {{
                other.classList.remove("open");

                const otherAnswer =
                    other.querySelector(".faq-answer");

                const otherQuestion =
                    other.querySelector(".faq-question");

                if (otherAnswer) {{
                    otherAnswer.hidden = true;
                }}

                if (otherQuestion) {{
                    otherQuestion.setAttribute(
                        "aria-expanded",
                        "false"
                    );
                }}
            }});

            if (willOpen) {{
                item.classList.add("open");
                answer.hidden = false;

                question.setAttribute(
                    "aria-expanded",
                    "true"
                );
            }}
        }}

        question.addEventListener(
            "click",
            toggleItem
        );

        question.addEventListener(
            "keydown",
            function(event) {{
                if (
                    event.key === "Enter"
                    || event.key === " "
                ) {{
                    event.preventDefault();
                    toggleItem();
                }}
            }}
        );
    }});
}});
</script>
<!-- FAQ ACCORDION SCRIPT END -->

</body>
</html>"""
    )
@router.post("/contact", include_in_schema=False)
async def submit_contact(request: Request):
    form = dict(
        urllib.parse.parse_qsl(
            (await request.body()).decode("utf-8", "ignore")
        )
    )

    name = (form.get("name") or "").strip()[:100]
    contact = (form.get("contact") or "").strip()[:160]
    subject = (form.get("subject") or "").strip()[:160]
    message = (form.get("message") or "").strip()[:3000]

    if not name or not contact or not message:
        return RedirectResponse("/#contact", status_code=303)

    now = isoformat(utc_now())
    ip_address = request.client.host if request.client else ""

    with database() as connection:
        ensure_landing_tables(connection)
        connection.execute(
            """
            INSERT INTO landing_contact_messages(
                name,contact,subject,message,status,
                ip_address,created_at,updated_at
            )
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                name,
                contact,
                subject,
                message,
                "new",
                ip_address,
                now,
                now,
            ),
        )

    return RedirectResponse("/?sent=1#contact", status_code=303)


@router.get(
    "/buy/{plan_slug}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def buy_plan(
    plan_slug: str,
    request: Request,
):
    with database() as connection:
        ensure_landing_tables(connection)

        plan = connection.execute(
            """
            SELECT *
            FROM subscription_plans
            WHERE slug = ?
              AND is_active = 1
            """,
            (plan_slug,),
        ).fetchone()

    if plan is None:
        return HTMLResponse(
            "<h2 dir='rtl'>پلن موردنظر پیدا نشد.</h2>",
            status_code=404,
        )

    error = request.query_params.get("error", "")

    account_email = (
        request.query_params.get("email", "")
        .strip()
        .lower()
    )

    email_from_account = bool(account_email)

    error_messages = {
        "invalid-email": "ایمیل واردشده معتبر نیست.",
        "email-not-found": (
            "این ایمیل داخل اپ رشدیار ثبت نشده است. "
            "ابتدا با همین ایمیل داخل اپ وارد شوید و سپس خرید را انجام دهید."
        ),
    }

    error_html = ""

    if error in error_messages:
        error_html = (
            '<div class="error">'
            + esc(error_messages[error])
            + '</div>'
        )

    is_free = int(plan["price"] or 0) <= 0

    if is_free:
        action_html = """
        <a class="submit free" href="/assets/apk/app-release.apk">
            دانلود اپ و شروع رایگان
        </a>
        """

    elif email_from_account:
        safe_email = esc(account_email)

        action_html = f"""
        <form method="post" action="/payment/create/{esc(plan["slug"])}">

            <div class="account-checkout-user">
                <span>خرید برای حساب واردشده</span>
                <strong>{safe_email}</strong>
            </div>

            <input
                type="hidden"
                name="email"
                value="{safe_email}">

            <small>
                اشتراک پس از پرداخت روی همین حساب فعال می‌شود.
            </small>

            <button class="submit" type="submit">
                پرداخت امن با زرین‌پال
            </button>
        </form>
        """

    else:
        action_html = f"""
        <form method="post" action="/payment/create/{esc(plan["slug"])}">
            <label for="email">ایمیل ثبت‌شده داخل اپ</label>

            <input
                id="email"
                name="email"
                type="email"
                inputmode="email"
                autocomplete="email"
                required
                placeholder="example@gmail.com">

            <small>
                اشتراک روی همین ایمیل در اپ رشدیار فعال می‌شود.
            </small>

            <button class="submit" type="submit">
                پرداخت امن با زرین‌پال
            </button>
        </form>
        """

    price_text = (
        "رایگان"
        if is_free
        else f'{money(plan["price"])} تومان'
    )

    return HTMLResponse(
        f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>خرید {esc(plan["title"])} | رشدیار</title>
<style>
*{{box-sizing:border-box}}
body{{
    margin:0;
    min-height:100vh;
    display:grid;
    place-items:center;
    padding:22px;
    color:#171725;
    font-family:Tahoma,"Segoe UI",Arial,sans-serif;
    background:
      radial-gradient(circle at 82% 5%,rgba(108,60,255,.18),transparent 30%),
      #f8f6ff;
}}
.checkout{{
    width:min(570px,100%);
    padding:32px;
    border:1px solid #e9e4f5;
    border-radius:30px;
    background:#fff;
    box-shadow:0 24px 75px rgba(64,35,125,.13);
}}
.brand{{
    display:flex;
    align-items:center;
    gap:12px;
    margin-bottom:24px;
}}
.brand img{{
    width:50px;
    height:50px;
    border-radius:15px;
}}
.brand b{{font-size:20px}}
.plan{{
    padding:20px;
    border-radius:20px;
    background:linear-gradient(145deg,#f3efff,#faf9ff);
}}
.plan small{{color:#6c3cff;font-weight:900}}
.plan h1{{margin:6px 0;font-size:26px}}
.price{{font-size:28px;font-weight:950;color:#6c3cff}}
.duration{{color:#777;font-size:12px}}
form{{display:grid;gap:10px;margin-top:23px}}
label{{font-weight:900;font-size:13px}}
input{{
    width:100%;
    padding:14px 15px;
    border:1px solid #ded7ee;
    border-radius:14px;
    outline:none;
    direction:ltr;
}}
input:focus{{
    border-color:#6c3cff;
    box-shadow:0 0 0 4px rgba(108,60,255,.10);
}}
form small{{color:#777;line-height:1.8}}
.submit{{
    width:100%;
    min-height:50px;
    display:grid;
    place-items:center;
    margin-top:10px;
    border:0;
    border-radius:15px;
    color:#fff;
    background:linear-gradient(135deg,#6c3cff,#431a9e);
    font-weight:950;
    text-decoration:none;
    cursor:pointer;
}}
.error{{
    margin:18px 0;
    padding:13px 15px;
    border-radius:14px;
    color:#a82743;
    background:#fff0f3;
    line-height:1.8;
    font-size:12px;
    font-weight:800;
}}
.back{{
    display:block;
    margin-top:20px;
    color:#6c3cff;
    text-align:center;
    text-decoration:none;
    font-size:12px;
    font-weight:900;
}}




.account-checkout-user{{
    display:grid;
    gap:5px;
    margin-bottom:14px;
    padding:13px 14px;
    border:1px solid rgba(108,60,255,.18);
    border-radius:13px;
    background:linear-gradient(
        145deg,
        #f7f2ff,
        #ffffff
    );
}}

.account-checkout-user span{{
    color:#777083;
    font-size:9px;
    line-height:1.6;
}}

.account-checkout-user strong{{
    direction:ltr;
    overflow-wrap:anywhere;
    color:#4f1db4;
    font-size:11px;
    line-height:1.6;
}}

</style>
</head>
<body>
<main class="checkout">
    <div class="brand">
        <img src="/assets/rashdyar-logo.png" alt="رشدیار">
        <b>خرید اشتراک رشدیار</b>
    </div>

    <section class="plan">
        <small>پلن انتخابی</small>
        <h1>{esc(plan["title"])}</h1>
        <div class="price">{price_text}</div>
        <div class="duration">
            {int(plan["duration_days"] or 30)} روز اعتبار
        </div>
    </section>

    {error_html}
    {action_html}

    <a class="back" href="/#plans">بازگشت به پلن‌ها</a>
</main>
</body>
</html>"""
    )

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .common import (
    database,
    esc,
    isoformat,
    page_layout,
    read_form,
    require_auth,
    utc_now,
    uuid,
)

router = APIRouter(prefix="/admin")
public_router = APIRouter(prefix="/v1", tags=["campaigns"])


def _value(row, key: str, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def _parse_datetime(value: str | None) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_datetime(value: str | None) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return "—"
    return parsed.strftime("%Y/%m/%d · %H:%M")


def _campaign_status(row, now: datetime) -> tuple[str, str]:
    enabled = bool(_value(row, "enabled", 0))
    starts_at = _parse_datetime(_value(row, "starts_at"))
    ends_at = _parse_datetime(_value(row, "ends_at"))

    if not enabled:
        return "متوقف", "off"
    if starts_at and starts_at > now:
        return "زمان‌بندی‌شده", "scheduled"
    if ends_at and ends_at <= now:
        return "پایان‌یافته", "ended"
    return "فعال", "active"


def _audience_title(value: str | None) -> str:
    return {
        "all": "همه کاربران",
        "free": "کاربران رایگان",
        "premium": "کاربران حرفه‌ای",
        "new_users": "کاربران جدید",
        "expired": "اشتراک منقضی",
        "inactive": "کاربران غیرفعال",
    }.get(value or "", value or "نامشخص")


def _type_title(value: str | None) -> str:
    return {
        "banner": "بنر",
        "card": "کارت",
        "dialog": "پنجره",
        "bottom_sheet": "Bottom Sheet",
        "full_screen": "تمام‌صفحه",
    }.get(value or "", value or "بنر")


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _campaign_payload(row) -> dict:
    return {
        "id": str(_value(row, "id", "")),
        "title": str(_value(row, "title", "")),
        "description": str(_value(row, "description", "")),
        "audience": str(_value(row, "audience", "all")),
        "startsAt": _value(row, "starts_at"),
        "endsAt": _value(row, "ends_at"),
        "badgeText": _value(row, "badge_text"),
        "buttonText": _value(row, "button_text"),
        "actionType": str(_value(row, "action_type", "none")),
        "actionValue": _value(row, "action_value"),
        "imageUrl": _value(row, "image_url"),
        "priority": _safe_int(_value(row, "priority", 0)),
        "dismissible": bool(_value(row, "dismissible", 1)),
        "showOnce": bool(_value(row, "show_once", 0)),
        "type": str(_value(row, "campaign_type", "banner")),
    }


@router.get("/campaigns", response_class=HTMLResponse)
async def campaigns_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    query = (request.query_params.get("q") or "").strip()
    status_filter = (request.query_params.get("status") or "all").strip()
    audience_filter = (request.query_params.get("audience") or "all").strip()

    with database() as connection:
        campaigns = connection.execute(
            """
            SELECT c.*,
                   COALESCE(SUM(CASE WHEN e.event_type='impression' THEN 1 ELSE 0 END),0) AS impressions,
                   COALESCE(SUM(CASE WHEN e.event_type='click' THEN 1 ELSE 0 END),0) AS clicks
            FROM campaigns c
            LEFT JOIN campaign_events e ON e.campaign_id = c.id
            GROUP BY c.id
            ORDER BY c.priority DESC, c.created_at DESC
            LIMIT 500
            """
        ).fetchall()

    now = utc_now()
    filtered = []
    totals = {"all": 0, "active": 0, "scheduled": 0, "ended": 0, "off": 0}
    total_impressions = 0
    total_clicks = 0

    for campaign in campaigns:
        status_title, status_key = _campaign_status(campaign, now)
        totals["all"] += 1
        totals[status_key] += 1
        impressions = _safe_int(_value(campaign, "impressions", 0))
        clicks = _safe_int(_value(campaign, "clicks", 0))
        total_impressions += impressions
        total_clicks += clicks

        haystack = " ".join(
            [
                str(_value(campaign, "title", "")),
                str(_value(campaign, "description", "")),
                str(_value(campaign, "badge_text", "")),
            ]
        ).lower()

        if query and query.lower() not in haystack:
            continue
        if status_filter != "all" and status_filter != status_key:
            continue
        if audience_filter != "all" and audience_filter != str(_value(campaign, "audience", "")):
            continue

        filtered.append((campaign, status_title, status_key, impressions, clicks))

    ctr = (total_clicks / total_impressions * 100.0) if total_impressions else 0.0

    campaign_cards = []
    for campaign, status_title, status_key, impressions, clicks in filtered:
        campaign_id = esc(_value(campaign, "id", ""))
        title = esc(_value(campaign, "title", "بدون عنوان"))
        description = esc(_value(campaign, "description", ""))
        image_url = esc(_value(campaign, "image_url", ""))
        button_text = esc(_value(campaign, "button_text", "مشاهده"))
        badge_text = esc(_value(campaign, "badge_text", ""))
        action_type = esc(_value(campaign, "action_type", "none"))
        action_value = esc(_value(campaign, "action_value", ""))
        audience = _audience_title(str(_value(campaign, "audience", "all")))
        campaign_type = _type_title(str(_value(campaign, "campaign_type", "banner")))
        campaign_ctr = (clicks / impressions * 100.0) if impressions else 0.0

        media = (
            f'<img class="campaign-cover" src="{image_url}" alt="{title}" loading="lazy">'
            if image_url
            else '<div class="campaign-cover campaign-cover-empty">✦</div>'
        )

        campaign_cards.append(
            f"""
<article class="campaign-item">
  <div class="campaign-media">{media}<span class="campaign-state state-{status_key}">{status_title}</span></div>
  <div class="campaign-main">
    <div class="campaign-head">
      <div>
        <div class="campaign-kicker">{esc(campaign_type)} · {esc(audience)}</div>
        <h3>{title}</h3>
      </div>
      <span class="priority-chip">اولویت {_safe_int(_value(campaign, 'priority', 0))}</span>
    </div>
    <p class="campaign-description">{description or 'برای این کمپین توضیحی ثبت نشده است.'}</p>
    <div class="campaign-meta-grid">
      <div><span>شروع</span><strong>{esc(_format_datetime(_value(campaign, 'starts_at')))}</strong></div>
      <div><span>پایان</span><strong>{esc(_format_datetime(_value(campaign, 'ends_at')))}</strong></div>
      <div><span>نمایش</span><strong>{impressions:,}</strong></div>
      <div><span>کلیک</span><strong>{clicks:,}</strong></div>
      <div><span>CTR</span><strong>{campaign_ctr:.1f}%</strong></div>
      <div><span>اقدام</span><strong>{action_type}</strong></div>
    </div>
    <div class="campaign-preview-line">
      {f'<span class="mini-badge">{badge_text}</span>' if badge_text else ''}
      <span>{button_text}</span>
      {f'<small>{action_value}</small>' if action_value else ''}
    </div>
    <div class="campaign-actions">
      <form method="post" action="/admin/campaigns/toggle">
        <input type="hidden" name="campaign_id" value="{campaign_id}">
        <button class="btn btn-secondary" type="submit">{'توقف کمپین' if status_key != 'off' else 'فعال‌سازی'}</button>
      </form>
      <form method="post" action="/admin/campaigns/duplicate">
        <input type="hidden" name="campaign_id" value="{campaign_id}">
        <button class="btn btn-secondary" type="submit">تکثیر</button>
      </form>
      <form method="post" action="/admin/campaigns/delete" onsubmit="return confirm('این کمپین حذف شود؟')">
        <input type="hidden" name="campaign_id" value="{campaign_id}">
        <button class="btn btn-danger" type="submit">حذف</button>
      </form>
    </div>
  </div>
</article>
"""
        )

    status_options = [
        ("all", "همه"),
        ("active", "فعال"),
        ("scheduled", "زمان‌بندی‌شده"),
        ("ended", "پایان‌یافته"),
        ("off", "متوقف"),
    ]
    status_tabs = "".join(
        f'<a class="filter-tab {"active" if status_filter == key else ""}" href="/admin/campaigns?status={key}&audience={esc(audience_filter)}&q={esc(query)}">{label}<span>{totals[key]}</span></a>'
        for key, label in status_options
    )

    body = f"""
<style>
.campaign-hero{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:18px}}
.campaign-hero h2{{margin:0 0 8px;font-size:27px}}.campaign-hero p{{margin:0;color:var(--muted);max-width:720px}}
.campaign-kpis{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin-bottom:18px}}
.campaign-kpi{{padding:18px;border:1px solid var(--border);border-radius:18px;background:var(--card);box-shadow:var(--shadow)}}
.campaign-kpi span{{display:block;color:var(--muted);font-size:12px;margin-bottom:10px}}.campaign-kpi strong{{font-size:25px;letter-spacing:-.5px}}
.campaign-toolbar{{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:16px}}
.filter-tabs{{display:flex;gap:7px;flex-wrap:wrap}}.filter-tab{{display:flex;gap:7px;align-items:center;padding:9px 12px;border:1px solid var(--border);border-radius:12px;text-decoration:none;color:var(--text);background:var(--card)}}
.filter-tab span{{font-size:11px;color:var(--muted)}}.filter-tab.active{{background:var(--primary);border-color:var(--primary);color:#fff}}.filter-tab.active span{{color:#fff}}
.campaign-filter-form{{display:flex;gap:8px;flex-wrap:wrap}}.campaign-filter-form input,.campaign-filter-form select{{min-width:170px}}
.campaign-layout{{display:grid;grid-template-columns:minmax(0,1fr) 390px;gap:18px;align-items:start}}
.campaign-list{{display:grid;gap:14px}}.campaign-item{{display:grid;grid-template-columns:190px minmax(0,1fr);overflow:hidden;border:1px solid var(--border);border-radius:20px;background:var(--card);box-shadow:var(--shadow)}}
.campaign-media{{position:relative;min-height:230px;background:linear-gradient(145deg,#ede9fe,#f5f3ff)}}.campaign-cover{{width:100%;height:100%;object-fit:cover;display:block}}.campaign-cover-empty{{display:grid;place-items:center;font-size:48px;color:#7c3aed}}
.campaign-state{{position:absolute;top:12px;right:12px;padding:7px 10px;border-radius:999px;font-size:11px;font-weight:800;background:#fff}}
.state-active{{color:#047857}}.state-scheduled{{color:#7c3aed}}.state-ended{{color:#64748b}}.state-off{{color:#dc2626}}
.campaign-main{{padding:18px}}.campaign-head{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}}.campaign-head h3{{margin:5px 0 0;font-size:20px}}.campaign-kicker{{font-size:11px;color:var(--muted)}}
.priority-chip{{padding:7px 9px;border-radius:10px;background:var(--soft);font-size:11px;white-space:nowrap}}.campaign-description{{color:var(--muted);line-height:1.9;min-height:36px}}
.campaign-meta-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}}.campaign-meta-grid div{{padding:10px;border-radius:12px;background:var(--soft)}}.campaign-meta-grid span{{display:block;color:var(--muted);font-size:10px;margin-bottom:4px}}.campaign-meta-grid strong{{font-size:12px}}
.campaign-preview-line{{display:flex;align-items:center;gap:8px;margin-top:12px;padding-top:12px;border-top:1px solid var(--border);color:var(--muted)}}.campaign-preview-line small{{direction:ltr;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.mini-badge{{padding:5px 8px;border-radius:8px;background:#ede9fe;color:#6d28d9;font-size:10px;font-weight:800}}
.campaign-actions{{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}}.campaign-actions form{{margin:0}}.btn-danger{{background:#fff1f2;color:#be123c;border:1px solid #fecdd3}}
.campaign-builder{{position:sticky;top:18px}}.builder-title{{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}}.builder-title h3{{margin:0}}.builder-section{{padding-top:14px;margin-top:14px;border-top:1px solid var(--border)}}.builder-section h4{{margin:0 0 12px;font-size:13px}}
.preview-box{{border-radius:18px;padding:16px;background:linear-gradient(135deg,#6d28d9,#8b5cf6);color:white;margin-bottom:16px;min-height:150px;display:flex;flex-direction:column;justify-content:flex-end}}.preview-box small{{opacity:.8}}.preview-box h3{{margin:8px 0}}.preview-box p{{margin:0 0 12px;opacity:.9}}.preview-button{{display:inline-flex;align-self:flex-start;padding:8px 12px;border-radius:10px;background:#fff;color:#6d28d9;font-size:12px;font-weight:800}}
.empty-state{{padding:48px 20px;text-align:center;border:1px dashed var(--border);border-radius:20px;background:var(--card);color:var(--muted)}}
@media(max-width:1180px){{.campaign-kpis{{grid-template-columns:repeat(3,1fr)}}.campaign-layout{{grid-template-columns:1fr}}.campaign-builder{{position:static}}}}
@media(max-width:720px){{.campaign-kpis{{grid-template-columns:repeat(2,1fr)}}.campaign-item{{grid-template-columns:1fr}}.campaign-media{{min-height:180px}}.campaign-meta-grid{{grid-template-columns:repeat(2,1fr)}}.campaign-hero{{display:block}}}}
</style>

<section class="campaign-hero">
  <div>
    <h2>مرکز کمپین‌ها</h2>
    <p>کمپین‌های داخل اپ را بساز، زمان‌بندی کن، روی گروه‌های مختلف کاربران نمایش بده و عملکرد هر کمپین را با نرخ نمایش و کلیک بررسی کن.</p>
  </div>
  <a class="btn btn-primary" href="#campaign-builder">＋ ساخت کمپین جدید</a>
</section>

<section class="campaign-kpis">
  <div class="campaign-kpi"><span>کل کمپین‌ها</span><strong>{totals['all']:,}</strong></div>
  <div class="campaign-kpi"><span>کمپین فعال</span><strong>{totals['active']:,}</strong></div>
  <div class="campaign-kpi"><span>زمان‌بندی‌شده</span><strong>{totals['scheduled']:,}</strong></div>
  <div class="campaign-kpi"><span>کل نمایش</span><strong>{total_impressions:,}</strong></div>
  <div class="campaign-kpi"><span>نرخ کلیک</span><strong>{ctr:.1f}%</strong></div>
</section>

<section class="campaign-toolbar">
  <div class="filter-tabs">{status_tabs}</div>
  <form class="campaign-filter-form" method="get" action="/admin/campaigns">
    <input type="hidden" name="status" value="{esc(status_filter)}">
    <input name="q" value="{esc(query)}" placeholder="جستجوی عنوان یا توضیح...">
    <select name="audience">
      <option value="all" {'selected' if audience_filter == 'all' else ''}>همه مخاطبان</option>
      <option value="free" {'selected' if audience_filter == 'free' else ''}>رایگان</option>
      <option value="premium" {'selected' if audience_filter == 'premium' else ''}>حرفه‌ای</option>
      <option value="new_users" {'selected' if audience_filter == 'new_users' else ''}>کاربران جدید</option>
    </select>
    <button class="btn btn-secondary" type="submit">اعمال فیلتر</button>
  </form>
</section>

<div class="campaign-layout">
  <section class="campaign-list">
    {''.join(campaign_cards) or '<div class="empty-state"><h3>کمپینی پیدا نشد</h3><p>فیلترها را تغییر بده یا یک کمپین جدید بساز.</p></div>'}
  </section>

  <aside id="campaign-builder" class="card campaign-builder">
    <div class="builder-title"><h3>ساخت کمپین</h3><span class="badge badge-active">Live</span></div>
    <div class="preview-box" id="campaign-preview">
      <small id="preview-badge">پیشنهاد ویژه</small>
      <h3 id="preview-title">عنوان کمپین</h3>
      <p id="preview-description">توضیح کوتاه کمپین در اپ اینجا نمایش داده می‌شود.</p>
      <span class="preview-button" id="preview-button">مشاهده</span>
    </div>
    <form method="post" action="/admin/campaigns/create" id="campaign-form">
      <label>عنوان کمپین</label>
      <input name="title" id="campaign-title" required maxlength="120" placeholder="مثلاً ۳۰٪ تخفیف اشتراک حرفه‌ای">
      <label>توضیح</label>
      <textarea name="description" id="campaign-description" maxlength="600" placeholder="پیام کوتاه و شفاف برای کاربر"></textarea>
      <div class="builder-section">
        <h4>نمایش و مخاطب</h4>
        <div class="form-grid">
          <div><label>نوع نمایش</label><select name="campaign_type"><option value="banner">بنر</option><option value="card">کارت</option><option value="dialog">پنجره</option><option value="bottom_sheet">Bottom Sheet</option><option value="full_screen">تمام‌صفحه</option></select></div>
          <div><label>مخاطب</label><select name="audience"><option value="all">همه کاربران</option><option value="free">رایگان</option><option value="premium">حرفه‌ای</option><option value="new_users">کاربران جدید</option><option value="expired">اشتراک منقضی</option><option value="inactive">غیرفعال</option></select></div>
          <div><label>شروع</label><input type="datetime-local" name="starts_at" required></div>
          <div><label>پایان</label><input type="datetime-local" name="ends_at" required></div>
          <div><label>اولویت</label><input type="number" name="priority" value="0" min="-1000" max="1000"></div>
          <div><label>نشان کوتاه</label><input name="badge_text" id="campaign-badge" maxlength="40" placeholder="پیشنهاد ویژه"></div>
        </div>
      </div>
      <div class="builder-section">
        <h4>اقدام کاربر</h4>
        <div class="form-grid">
          <div><label>متن دکمه</label><input name="button_text" id="campaign-button" maxlength="40" placeholder="مشاهده"></div>
          <div><label>نوع اقدام</label><select name="action_type"><option value="none">بدون اقدام</option><option value="url">لینک اینترنتی</option><option value="analyzer">تحلیل پیج</option><option value="planner">برنامه رشد</option><option value="ai_studio">AI Studio</option><option value="subscription">اشتراک</option><option value="trend">ترند</option><option value="hashtag">هشتگ</option><option value="route">مسیر داخلی</option></select></div>
          <div class="full"><label>مقدار اقدام یا لینک</label><input name="action_value" placeholder="https://... یا route داخل اپ"></div>
          <div class="full"><label>آدرس تصویر</label><input name="image_url" placeholder="https://..."></div>
        </div>
      </div>
      <div class="builder-section">
        <label><input type="checkbox" name="dismissible" value="1" checked style="width:auto"> کاربر بتواند کمپین را ببندد</label>
        <label><input type="checkbox" name="show_once" value="1" style="width:auto"> فقط یک‌بار برای هر کاربر نمایش داده شود</label>
      </div>
      <button class="btn btn-primary" style="width:100%;margin-top:16px" type="submit">ساخت و فعال‌سازی کمپین</button>
    </form>
  </aside>
</div>

<script>
(function(){{
  const bind = (inputId, outputId, fallback) => {{
    const input = document.getElementById(inputId);
    const output = document.getElementById(outputId);
    if (!input || !output) return;
    const update = () => output.textContent = input.value.trim() || fallback;
    input.addEventListener('input', update); update();
  }};
  bind('campaign-title','preview-title','عنوان کمپین');
  bind('campaign-description','preview-description','توضیح کوتاه کمپین در اپ اینجا نمایش داده می‌شود.');
  bind('campaign-badge','preview-badge','پیشنهاد ویژه');
  bind('campaign-button','preview-button','مشاهده');
}})();
</script>
"""

    return HTMLResponse(page_layout("مرکز کمپین‌ها", body))


@router.post("/campaigns/create")
async def create_campaign(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    form = await read_form(request)
    starts_at = _parse_datetime(form.get("starts_at"))
    ends_at = _parse_datetime(form.get("ends_at"))
    if starts_at is None or ends_at is None or ends_at <= starts_at:
        return RedirectResponse(url="/admin/campaigns?error=invalid_date", status_code=303)

    try:
        priority = max(-1000, min(1000, int(form.get("priority", "0") or 0)))
    except ValueError:
        priority = 0

    now = utc_now()
    with database() as connection:
        connection.execute(
            """
            INSERT INTO campaigns (
                id,title,description,audience,starts_at,ends_at,premium_access,enabled,
                badge_text,button_text,action_type,action_value,image_url,priority,
                dismissible,show_once,campaign_type,created_at,updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                (form.get("title") or "کمپین جدید").strip()[:120],
                (form.get("description") or "").strip()[:600],
                form.get("audience", "all"),
                isoformat(starts_at),
                isoformat(ends_at),
                (form.get("badge_text") or "").strip()[:40] or None,
                (form.get("button_text") or "").strip()[:40] or None,
                form.get("action_type", "none"),
                (form.get("action_value") or "").strip() or None,
                (form.get("image_url") or "").strip() or None,
                priority,
                1 if form.get("dismissible") == "1" else 0,
                1 if form.get("show_once") == "1" else 0,
                form.get("campaign_type", "banner"),
                isoformat(now),
                isoformat(now),
            ),
        )

    return RedirectResponse(url="/admin/campaigns?created=1", status_code=303)


@router.post("/campaigns/toggle")
async def toggle_campaign(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect
    form = await read_form(request)
    campaign_id = form.get("campaign_id", "")
    with database() as connection:
        row = connection.execute("SELECT enabled FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if row:
            connection.execute(
                "UPDATE campaigns SET enabled = ?, updated_at = ? WHERE id = ?",
                (0 if _value(row, "enabled", 0) else 1, isoformat(utc_now()), campaign_id),
            )
    return RedirectResponse(url="/admin/campaigns", status_code=303)


@router.post("/campaigns/delete")
async def delete_campaign(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect
    form = await read_form(request)
    campaign_id = form.get("campaign_id", "")
    with database() as connection:
        connection.execute("DELETE FROM campaign_events WHERE campaign_id = ?", (campaign_id,))
        connection.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
    return RedirectResponse(url="/admin/campaigns?deleted=1", status_code=303)


@router.post("/campaigns/duplicate")
async def duplicate_campaign(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect
    form = await read_form(request)
    campaign_id = form.get("campaign_id", "")
    now = utc_now()
    with database() as connection:
        source = connection.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if source:
            connection.execute(
                """
                INSERT INTO campaigns (
                    id,title,description,audience,starts_at,ends_at,premium_access,enabled,
                    badge_text,button_text,action_type,action_value,image_url,priority,
                    dismissible,show_once,campaign_type,created_at,updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    f"کپی {_value(source, 'title', 'کمپین')}",
                    _value(source, "description", ""),
                    _value(source, "audience", "all"),
                    _value(source, "starts_at"),
                    _value(source, "ends_at"),
                    _value(source, "premium_access", 1),
                    _value(source, "badge_text"),
                    _value(source, "button_text"),
                    _value(source, "action_type", "none"),
                    _value(source, "action_value"),
                    _value(source, "image_url"),
                    _safe_int(_value(source, "priority", 0)),
                    _safe_int(_value(source, "dismissible", 1)),
                    _safe_int(_value(source, "show_once", 0)),
                    _value(source, "campaign_type", "banner"),
                    isoformat(now),
                    isoformat(now),
                ),
            )
    return RedirectResponse(url="/admin/campaigns?duplicated=1", status_code=303)


@public_router.get("/campaigns/active")
async def active_campaigns(request: Request):
    now_text = isoformat(utc_now())
    plan = (request.query_params.get("plan") or "free").lower()
    limit = min(20, max(1, _safe_int(request.query_params.get("limit"), 10)))

    audiences = ["all"]
    if plan in {"premium", "pro"}:
        audiences.append("premium")
    else:
        audiences.append("free")

    placeholders = ",".join("?" for _ in audiences)
    with database() as connection:
        rows = connection.execute(
            f"""
            SELECT * FROM campaigns
            WHERE enabled = 1
              AND starts_at <= ?
              AND ends_at > ?
              AND audience IN ({placeholders})
            ORDER BY priority DESC, created_at DESC
            LIMIT ?
            """,
            (now_text, now_text, *audiences, limit),
        ).fetchall()

    return JSONResponse({"success": True, "items": [_campaign_payload(row) for row in rows]})


@public_router.post("/campaigns/{campaign_id}/events")
async def campaign_event(campaign_id: str, request: Request):
    try:
        payload = await request.json()
    except (json.JSONDecodeError, ValueError):
        payload = {}

    event_type = str(payload.get("eventType") or payload.get("event_type") or "").strip().lower()
    if event_type not in {"impression", "click", "dismiss"}:
        return JSONResponse({"success": False, "message": "invalid_event_type"}, status_code=400)

    with database() as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(campaign_events)").fetchall()}
        values = {
            "id": str(uuid.uuid4()),
            "campaign_id": campaign_id,
            "event_type": event_type,
            "user_id": payload.get("userId") or payload.get("user_id"),
            "created_at": isoformat(utc_now()),
        }
        insert_columns = [name for name in values if name in columns]
        if not insert_columns:
            return JSONResponse({"success": False, "message": "campaign_events_schema_missing"}, status_code=500)
        sql = f"INSERT INTO campaign_events ({','.join(insert_columns)}) VALUES ({','.join('?' for _ in insert_columns)})"
        connection.execute(sql, tuple(values[name] for name in insert_columns))

    return JSONResponse({"success": True})

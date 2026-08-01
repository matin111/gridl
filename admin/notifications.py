from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .common import database, esc, isoformat, page_layout, read_form, require_auth, utc_now, uuid

router = APIRouter(prefix="/admin")
public_router = APIRouter(prefix="/v1", tags=["notifications"])


def _value(row, key: str, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
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


def _audience_title(value: str | None) -> str:
    return {
        "all": "همه کاربران",
        "free": "کاربران رایگان",
        "premium": "کاربران حرفه‌ای",
        "expired": "اشتراک منقضی",
        "new_users": "کاربران جدید",
        "inactive": "کاربران غیرفعال",
    }.get(value or "", value or "نامشخص")


def _type_title(value: str | None) -> str:
    return {
        "in_app": "داخل اپ",
        "banner": "بنر",
        "dialog": "پنجره",
        "bottom_sheet": "Bottom Sheet",
        "push": "Push",
    }.get(value or "", value or "داخل اپ")


def _ensure_schema(connection) -> None:
    columns = {
        row["name"] if hasattr(row, "keys") else row[1]
        for row in connection.execute("PRAGMA table_info(notifications)").fetchall()
    }
    additions = {
        "notification_type": "TEXT NOT NULL DEFAULT 'in_app'",
        "priority": "INTEGER NOT NULL DEFAULT 0",
        "button_text": "TEXT",
        "action_type": "TEXT NOT NULL DEFAULT 'none'",
        "action_value": "TEXT",
        "dismissible": "INTEGER NOT NULL DEFAULT 1",
        "show_once": "INTEGER NOT NULL DEFAULT 0",
        "expires_at": "TEXT",
    }
    for name, definition in additions.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE notifications ADD COLUMN {name} {definition}")

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_events (
            id TEXT PRIMARY KEY,
            notification_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            user_id TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_notification_events_notification ON notification_events(notification_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_notification_events_user ON notification_events(user_id)"
    )


def _notification_status(row, now: datetime) -> tuple[str, str]:
    if not bool(_value(row, "enabled", 0)):
        return "متوقف", "off"
    sent_at = _parse_datetime(_value(row, "sent_at"))
    scheduled_at = _parse_datetime(_value(row, "scheduled_at"))
    expires_at = _parse_datetime(_value(row, "expires_at"))
    if expires_at and expires_at <= now:
        return "منقضی", "expired"
    if sent_at:
        return "ارسال‌شده", "sent"
    if scheduled_at and scheduled_at > now:
        return "زمان‌بندی‌شده", "scheduled"
    return "آماده ارسال", "ready"


def _notification_payload(row) -> dict:
    return {
        "id": str(_value(row, "id", "")),
        "title": str(_value(row, "title", "")),
        "body": str(_value(row, "body", "")),
        "audience": str(_value(row, "audience", "all")),
        "type": str(_value(row, "notification_type", "in_app")),
        "targetRoute": _value(row, "target_route"),
        "imageUrl": _value(row, "image_url"),
        "buttonText": _value(row, "button_text"),
        "actionType": str(_value(row, "action_type", "none")),
        "actionValue": _value(row, "action_value"),
        "priority": _safe_int(_value(row, "priority", 0)),
        "dismissible": bool(_value(row, "dismissible", 1)),
        "showOnce": bool(_value(row, "show_once", 0)),
        "scheduledAt": _value(row, "scheduled_at"),
        "expiresAt": _value(row, "expires_at"),
        "createdAt": _value(row, "created_at"),
    }


NOTIFICATIONS_CSS = """
<style>
.notification-hero{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:18px}
.notification-hero h2{margin:0 0 7px;font-size:27px}.notification-hero p{margin:0;color:var(--muted);max-width:760px}
.notification-kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin-bottom:18px}
.notification-kpi{padding:17px;border:1px solid var(--border);border-radius:18px;background:var(--card);box-shadow:var(--shadow)}
.notification-kpi span{display:block;color:var(--muted);font-size:12px;margin-bottom:9px}.notification-kpi strong{font-size:24px}
.notification-toolbar{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:15px}
.filter-tabs{display:flex;gap:7px;flex-wrap:wrap}.filter-tab{display:flex;gap:7px;align-items:center;padding:9px 12px;border:1px solid var(--border);border-radius:12px;text-decoration:none;color:var(--text);background:var(--card)}
.filter-tab.active{background:var(--primary);border-color:var(--primary);color:white}.filter-tab span{font-size:11px;opacity:.8}
.notification-list{display:grid;gap:13px}.notification-item{display:grid;grid-template-columns:82px 1fr;gap:16px;padding:16px;border:1px solid var(--border);border-radius:20px;background:var(--card);box-shadow:var(--shadow)}
.notification-icon{height:82px;border-radius:18px;display:grid;place-items:center;font-size:30px;background:linear-gradient(145deg,rgba(108,60,255,.18),rgba(79,70,229,.06));border:1px solid rgba(108,60,255,.18)}
.notification-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.notification-head h3{margin:2px 0 5px;font-size:18px}.notification-kicker{font-size:12px;color:var(--muted)}
.notification-state{font-size:11px;padding:6px 9px;border-radius:999px;font-weight:800}.state-ready{background:#dcfce7;color:#166534}.state-scheduled{background:#e0e7ff;color:#3730a3}.state-sent{background:#dbeafe;color:#1d4ed8}.state-off,.state-expired{background:#f1f5f9;color:#475569}
.notification-body{margin:9px 0 12px;color:var(--muted);line-height:1.85}.notification-meta{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-bottom:12px}.notification-meta div{padding:10px;background:var(--soft);border-radius:12px}.notification-meta span{display:block;color:var(--muted);font-size:11px;margin-bottom:4px}.notification-meta strong{font-size:12px}
.notification-actions{display:flex;gap:8px;flex-wrap:wrap}.notification-actions form{margin:0}.preview-shell{border:1px solid var(--border);background:var(--soft);border-radius:18px;padding:16px;position:sticky;top:18px}.preview-device{max-width:320px;margin:auto;border:8px solid #171725;border-radius:28px;background:white;min-height:420px;padding:18px;color:#171725}.preview-card{margin-top:55px;border:1px solid #e7e4f5;border-radius:18px;padding:16px;box-shadow:0 12px 35px rgba(23,23,37,.10)}.preview-card img{width:100%;height:125px;object-fit:cover;border-radius:12px;margin-bottom:12px}.preview-card h4{margin:0 0 8px}.preview-card p{font-size:13px;line-height:1.8;color:#626277}.preview-card button{width:100%;border:0;background:#6c3cff;color:white;padding:10px;border-radius:10px;font-weight:800}
.notification-editor{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(280px,.65fr);gap:18px}.empty-state{padding:45px 20px;text-align:center;border:1px dashed var(--border);border-radius:18px;color:var(--muted);background:var(--card)}
@media(max-width:1050px){.notification-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.notification-meta{grid-template-columns:repeat(2,minmax(0,1fr))}.notification-editor{grid-template-columns:1fr}.preview-shell{position:static}}
@media(max-width:680px){.notification-item{grid-template-columns:1fr}.notification-icon{height:58px}.notification-kpis{grid-template-columns:1fr 1fr}.notification-head{flex-direction:column}.notification-meta{grid-template-columns:1fr 1fr}}
</style>
"""


@router.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    query = (request.query_params.get("q") or "").strip()
    status_filter = (request.query_params.get("status") or "all").strip()

    with database() as connection:
        _ensure_schema(connection)
        notifications = connection.execute(
            """
            SELECT n.*,
                   COALESCE(SUM(CASE WHEN e.event_type='impression' THEN 1 ELSE 0 END),0) AS impressions,
                   COALESCE(SUM(CASE WHEN e.event_type='click' THEN 1 ELSE 0 END),0) AS clicks,
                   COALESCE(SUM(CASE WHEN e.event_type='dismiss' THEN 1 ELSE 0 END),0) AS dismisses
            FROM notifications n
            LEFT JOIN notification_events e ON e.notification_id = n.id
            GROUP BY n.id
            ORDER BY n.priority DESC, n.created_at DESC
            LIMIT 500
            """
        ).fetchall()

    now = utc_now()
    totals = {"all": 0, "ready": 0, "scheduled": 0, "sent": 0, "off": 0, "expired": 0}
    total_impressions = 0
    total_clicks = 0
    filtered = []

    for item in notifications:
        status_title, status_key = _notification_status(item, now)
        totals["all"] += 1
        totals[status_key] += 1
        impressions = _safe_int(_value(item, "impressions", 0))
        clicks = _safe_int(_value(item, "clicks", 0))
        dismisses = _safe_int(_value(item, "dismisses", 0))
        total_impressions += impressions
        total_clicks += clicks
        haystack = " ".join([str(_value(item, "title", "")), str(_value(item, "body", ""))]).lower()
        if query and query.lower() not in haystack:
            continue
        if status_filter != "all" and status_filter != status_key:
            continue
        filtered.append((item, status_title, status_key, impressions, clicks, dismisses))

    ctr = (total_clicks / total_impressions * 100) if total_impressions else 0.0
    cards = []
    icon_map = {"in_app": "🔔", "banner": "📣", "dialog": "💬", "bottom_sheet": "▰", "push": "📲"}

    for item, status_title, status_key, impressions, clicks, dismisses in filtered:
        item_id = esc(_value(item, "id", ""))
        item_type = str(_value(item, "notification_type", "in_app"))
        item_ctr = (clicks / impressions * 100) if impressions else 0.0
        cards.append(f"""
<article class="notification-item">
  <div class="notification-icon">{icon_map.get(item_type, '🔔')}</div>
  <div>
    <div class="notification-head">
      <div><div class="notification-kicker">{esc(_type_title(item_type))} · {esc(_audience_title(_value(item, 'audience', 'all')))}</div><h3>{esc(_value(item, 'title', 'بدون عنوان'))}</h3></div>
      <span class="notification-state state-{status_key}">{status_title}</span>
    </div>
    <p class="notification-body">{esc(_value(item, 'body', ''))}</p>
    <div class="notification-meta">
      <div><span>زمان ارسال</span><strong>{esc(_format_datetime(_value(item, 'scheduled_at')))}</strong></div>
      <div><span>نمایش</span><strong>{impressions:,}</strong></div>
      <div><span>کلیک</span><strong>{clicks:,}</strong></div>
      <div><span>CTR</span><strong>{item_ctr:.1f}%</strong></div>
      <div><span>بستن</span><strong>{dismisses:,}</strong></div>
    </div>
    <div class="notification-actions">
      <form method="post" action="/admin/notifications/send"><input type="hidden" name="notification_id" value="{item_id}"><button class="btn btn-primary" type="submit">ارسال/انتشار</button></form>
      <form method="post" action="/admin/notifications/toggle"><input type="hidden" name="notification_id" value="{item_id}"><button class="btn btn-secondary" type="submit">{'توقف' if bool(_value(item, 'enabled', 0)) else 'فعال‌سازی'}</button></form>
      <form method="post" action="/admin/notifications/duplicate"><input type="hidden" name="notification_id" value="{item_id}"><button class="btn btn-secondary" type="submit">تکثیر</button></form>
      <form method="post" action="/admin/notifications/delete" onsubmit="return confirm('این اعلان حذف شود؟')"><input type="hidden" name="notification_id" value="{item_id}"><button class="btn btn-danger" type="submit">حذف</button></form>
    </div>
  </div>
</article>
""")

    tabs = []
    for key, label in [("all", "همه"), ("ready", "آماده"), ("scheduled", "زمان‌بندی"), ("sent", "ارسال‌شده"), ("off", "متوقف")]:
        tabs.append(f'<a class="filter-tab {"active" if status_filter == key else ""}" href="/admin/notifications?status={key}&q={esc(query)}">{label}<span>{totals[key]}</span></a>')

    body = NOTIFICATIONS_CSS + f"""
<section class="notification-hero">
  <div><h2>مرکز اعلان‌ها</h2><p>اعلان‌های داخل اپ، بنرها و پیام‌های هدفمند را بساز، زمان‌بندی کن و عملکرد آن‌ها را اندازه‌گیری کن.</p></div>
  <a class="btn btn-primary" href="#create-notification">ساخت اعلان جدید</a>
</section>
<div class="notification-kpis">
  <div class="notification-kpi"><span>کل اعلان‌ها</span><strong>{totals['all']:,}</strong></div>
  <div class="notification-kpi"><span>آماده ارسال</span><strong>{totals['ready']:,}</strong></div>
  <div class="notification-kpi"><span>زمان‌بندی‌شده</span><strong>{totals['scheduled']:,}</strong></div>
  <div class="notification-kpi"><span>کل نمایش</span><strong>{total_impressions:,}</strong></div>
  <div class="notification-kpi"><span>نرخ کلیک</span><strong>{ctr:.1f}%</strong></div>
</div>
<section class="card" id="create-notification">
  <div class="notification-editor">
    <form method="post" action="/admin/notifications/create">
      <h3>ساخت اعلان جدید</h3>
      <div class="form-grid">
        <div><label>عنوان</label><input id="n-title" name="title" required maxlength="100" placeholder="مثلاً قابلیت جدید فعال شد"></div>
        <div><label>نوع نمایش</label><select name="notification_type"><option value="in_app">داخل اپ</option><option value="banner">بنر</option><option value="dialog">پنجره</option><option value="bottom_sheet">Bottom Sheet</option><option value="push">Push</option></select></div>
        <div><label>مخاطب</label><select name="audience"><option value="all">همه کاربران</option><option value="free">کاربران رایگان</option><option value="premium">کاربران حرفه‌ای</option><option value="expired">اشتراک منقضی</option><option value="new_users">کاربران جدید</option><option value="inactive">کاربران غیرفعال</option></select></div>
        <div><label>اولویت</label><input name="priority" type="number" value="0" min="0" max="999"></div>
        <div class="full"><label>متن اعلان</label><textarea id="n-body" name="body" required maxlength="500" placeholder="متن کوتاه و واضح اعلان را بنویس"></textarea></div>
        <div class="full"><label>آدرس تصویر اختیاری</label><input id="n-image" name="image_url" type="url" placeholder="https://..."></div>
        <div><label>متن دکمه</label><input id="n-button" name="button_text" value="مشاهده"></div>
        <div><label>نوع اقدام</label><select name="action_type"><option value="none">بدون اقدام</option><option value="route">صفحه داخل اپ</option><option value="url">لینک وب</option><option value="subscription">خرید اشتراک</option><option value="update">بروزرسانی اپ</option></select></div>
        <div><label>مقدار اقدام / Route</label><input name="action_value" placeholder="مثلاً image_generator"></div>
        <div><label>صفحه مقصد قدیمی</label><input name="target_route" placeholder="مثلاً home"></div>
        <div><label>زمان ارسال</label><input type="datetime-local" name="scheduled_at"></div>
        <div><label>زمان انقضا</label><input type="datetime-local" name="expires_at"></div>
        <div><label><input type="checkbox" name="dismissible" value="1" checked> قابل بستن باشد</label></div>
        <div><label><input type="checkbox" name="show_once" value="1"> فقط یک بار نمایش</label></div>
        <div class="full"><button class="btn btn-primary" type="submit">ذخیره اعلان</button></div>
      </div>
    </form>
    <aside class="preview-shell"><strong>پیش‌نمایش داخل اپ</strong><div class="preview-device"><div class="preview-card"><img id="preview-image" style="display:none" alt=""><h4 id="preview-title">عنوان اعلان</h4><p id="preview-body">متن اعلان در این بخش نمایش داده می‌شود.</p><button id="preview-button" type="button">مشاهده</button></div></div></aside>
  </div>
</section>
<div style="height:18px"></div>
<div class="notification-toolbar"><div class="filter-tabs">{''.join(tabs)}</div><form method="get" action="/admin/notifications"><input type="hidden" name="status" value="{esc(status_filter)}"><input name="q" value="{esc(query)}" placeholder="جستجو در اعلان‌ها"></form></div>
<section class="notification-list">{''.join(cards) or '<div class="empty-state">اعلانی با این فیلتر پیدا نشد.</div>'}</section>
<script>
(function(){{
 const title=document.getElementById('n-title'), body=document.getElementById('n-body'), image=document.getElementById('n-image'), button=document.getElementById('n-button');
 const pt=document.getElementById('preview-title'), pb=document.getElementById('preview-body'), pi=document.getElementById('preview-image'), pbtn=document.getElementById('preview-button');
 function sync(){{pt.textContent=title.value||'عنوان اعلان';pb.textContent=body.value||'متن اعلان در این بخش نمایش داده می‌شود.';pbtn.textContent=button.value||'مشاهده';if(image.value){{pi.src=image.value;pi.style.display='block'}}else{{pi.style.display='none'}}}}
 [title,body,image,button].forEach(function(el){{el.addEventListener('input',sync)}});sync();
}})();
</script>
"""
    return HTMLResponse(page_layout("اعلان‌ها", body))


def _form_datetime(value: str | None) -> str | None:
    parsed = _parse_datetime(value)
    return isoformat(parsed) if parsed else None


@router.post("/notifications/create")
async def create_notification(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect
    form = await read_form(request)
    with database() as connection:
        _ensure_schema(connection)
        connection.execute(
            """
            INSERT INTO notifications (
                id,title,body,audience,target_route,image_url,scheduled_at,sent_at,enabled,created_at,
                notification_type,priority,button_text,action_type,action_value,dismissible,show_once,expires_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()),
                (form.get("title") or "اعلان").strip(),
                (form.get("body") or "").strip(),
                form.get("audience") or "all",
                (form.get("target_route") or "").strip() or None,
                (form.get("image_url") or "").strip() or None,
                _form_datetime(form.get("scheduled_at")),
                None,
                1,
                isoformat(utc_now()),
                form.get("notification_type") or "in_app",
                _safe_int(form.get("priority")),
                (form.get("button_text") or "").strip() or None,
                form.get("action_type") or "none",
                (form.get("action_value") or "").strip() or None,
                1 if form.get("dismissible") == "1" else 0,
                1 if form.get("show_once") == "1" else 0,
                _form_datetime(form.get("expires_at")),
            ),
        )
    return RedirectResponse("/admin/notifications", status_code=303)


@router.post("/notifications/toggle")
async def toggle_notification(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect
    form = await read_form(request)
    with database() as connection:
        _ensure_schema(connection)
        connection.execute("UPDATE notifications SET enabled = CASE WHEN enabled=1 THEN 0 ELSE 1 END WHERE id=?", (form.get("notification_id", ""),))
    return RedirectResponse("/admin/notifications", status_code=303)


@router.post("/notifications/send")
async def send_notification(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect
    form = await read_form(request)
    with database() as connection:
        _ensure_schema(connection)
        connection.execute("UPDATE notifications SET enabled=1, sent_at=?, scheduled_at=NULL WHERE id=?", (isoformat(utc_now()), form.get("notification_id", "")))
    return RedirectResponse("/admin/notifications", status_code=303)


@router.post("/notifications/delete")
async def delete_notification(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect
    form = await read_form(request)
    notification_id = form.get("notification_id", "")
    with database() as connection:
        _ensure_schema(connection)
        connection.execute("DELETE FROM notification_events WHERE notification_id=?", (notification_id,))
        connection.execute("DELETE FROM notifications WHERE id=?", (notification_id,))
    return RedirectResponse("/admin/notifications", status_code=303)


@router.post("/notifications/duplicate")
async def duplicate_notification(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect
    form = await read_form(request)
    with database() as connection:
        _ensure_schema(connection)
        row = connection.execute("SELECT * FROM notifications WHERE id=?", (form.get("notification_id", ""),)).fetchone()
        if row:
            connection.execute(
                """
                INSERT INTO notifications (id,title,body,audience,target_route,image_url,scheduled_at,sent_at,enabled,created_at,notification_type,priority,button_text,action_type,action_value,dismissible,show_once,expires_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (str(uuid.uuid4()), f"کپی - {_value(row, 'title', 'اعلان')}", _value(row, "body", ""), _value(row, "audience", "all"), _value(row, "target_route"), _value(row, "image_url"), None, None, 0, isoformat(utc_now()), _value(row, "notification_type", "in_app"), _safe_int(_value(row, "priority", 0)), _value(row, "button_text"), _value(row, "action_type", "none"), _value(row, "action_value"), _safe_int(_value(row, "dismissible", 1)), _safe_int(_value(row, "show_once", 0)), _value(row, "expires_at")),
            )
    return RedirectResponse("/admin/notifications", status_code=303)


@public_router.get("/notifications")
async def public_notifications(request: Request, plan: str = "free", user_id: str | None = None, limit: int = 20):
    limit = max(1, min(limit, 50))
    now = isoformat(utc_now())
    with database() as connection:
        _ensure_schema(connection)
        rows = connection.execute(
            """
            SELECT * FROM notifications
            WHERE enabled=1
              AND audience IN ('all', ?)
              AND (scheduled_at IS NULL OR scheduled_at <= ?)
              AND (expires_at IS NULL OR expires_at > ?)
              AND (sent_at IS NOT NULL OR scheduled_at IS NULL OR scheduled_at <= ?)
            ORDER BY priority DESC, created_at DESC
            LIMIT ?
            """,
            (plan, now, now, now, limit * 3),
        ).fetchall()
        result = []
        for row in rows:
            if user_id and bool(_value(row, "show_once", 0)):
                seen = connection.execute(
                    "SELECT 1 FROM notification_events WHERE notification_id=? AND user_id=? AND event_type='impression' LIMIT 1",
                    (_value(row, "id"), user_id),
                ).fetchone()
                if seen:
                    continue
            result.append(_notification_payload(row))
            if len(result) >= limit:
                break
    return JSONResponse({"success": True, "items": result, "serverTime": now})


@public_router.post("/notifications/{notification_id}/events")
async def notification_event(notification_id: str, request: Request):
    try:
        payload = await request.json()
    except (json.JSONDecodeError, ValueError):
        payload = {}
    event_type = str(payload.get("eventType") or payload.get("event_type") or "").strip().lower()
    if event_type not in {"impression", "click", "dismiss"}:
        return JSONResponse({"success": False, "error": "invalid_event_type"}, status_code=400)
    with database() as connection:
        _ensure_schema(connection)
        exists = connection.execute("SELECT 1 FROM notifications WHERE id=?", (notification_id,)).fetchone()
        if not exists:
            return JSONResponse({"success": False, "error": "notification_not_found"}, status_code=404)
        connection.execute(
            "INSERT INTO notification_events(id,notification_id,event_type,user_id,created_at) VALUES(?,?,?,?,?)",
            (str(uuid.uuid4()), notification_id, event_type, str(payload.get("userId") or payload.get("user_id") or "").strip() or None, isoformat(utc_now())),
        )
    return JSONResponse({"success": True})

from __future__ import annotations

from .common import *  # noqa: F401,F403

router = APIRouter(prefix="/admin")

FEATURE_TITLES = {
    "analyzer": "تحلیل پیج",
    "content_studio": "استودیو محتوا",
    "image_generate": "ساخت تصویر",
    "image_generator": "ساخت تصویر",
    "image_edit": "ویرایش تصویر",
    "video_studio": "استودیو ویدیو",
    "planner": "برنامه رشد",
    "text_content": "محتوای هوشمند",
    "trends": "مرکز ترند",
    "hashtags": "هشتگ هوشمند",
}
SUCCESS_EVENT_TYPES = {"use", "success", "generated", "complete", "completed"}


def _value(row, key: str, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return getattr(row, key, default)


def _int(value, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _pct(part: int, total: int) -> float:
    return round((part / total * 100), 1) if total else 0.0


def _build_chart(series) -> str:
    if not series:
        return '<div class="empty-state">هنوز داده‌ای برای نمودار ثبت نشده است.</div>'
    max_value = max(
        [max(_int(_value(x, "users")), _int(_value(x, "usage"))) for x in series] + [1]
    )
    parts = []
    for item in series:
        users = _int(_value(item, "users"))
        usage = _int(_value(item, "usage"))
        users_height = max(4, round(users / max_value * 180))
        usage_height = max(4, round(usage / max_value * 180))
        parts.append(
            f'''<div class="chart-column">
              <div class="chart-tip">کاربر جدید: {users:,} · مصرف: {usage:,}</div>
              <div class="chart-bars"><div class="chart-bar users" style="height:{users_height}px"></div><div class="chart-bar usage" style="height:{usage_height}px"></div></div>
              <div class="chart-label">{esc(_value(item, "label", "-"))}</div>
            </div>'''
        )
    return "".join(parts)


def _recent_html(rows) -> str:
    if not rows:
        return '<div class="empty-state">هنوز فعالیتی ثبت نشده است.</div>'
    items = []
    for row in rows:
        key = str(_value(row, "feature_key", ""))
        feature = FEATURE_TITLES.get(key, key or "قابلیت نامشخص")
        event = str(_value(row, "event_type", ""))
        action = "استفاده موفق از" if event in SUCCESS_EVENT_TYPES else (event or "رویداد در")
        items.append(
            f'''<div class="activity-item"><span class="activity-dot"></span><div>
              <div class="activity-title">{esc(_value(row, "user_title", "کاربر ناشناس"))} — {esc(action)} {esc(feature)}</div>
              <div class="activity-meta">{esc(_value(row, "created_at", "-"))}</div>
            </div></div>'''
        )
    return "".join(items)


def _feature_bars(rows) -> str:
    if not rows:
        return '<div class="empty-state">داده مصرف قابلیت‌ها هنوز ثبت نشده است.</div>'
    maximum = max([_int(_value(row, "total")) for row in rows] + [1])
    result = []
    for row in rows:
        key = str(_value(row, "feature_key", ""))
        total = _int(_value(row, "total"))
        title = FEATURE_TITLES.get(key, key or "نامشخص")
        width = max(3, round(total / maximum * 100))
        result.append(
            f'''<div class="bar-item"><div class="bar-item-head"><strong>{esc(title)}</strong><span>{total:,}</span></div>
            <div class="progress"><span style="width:{width}%"></span></div></div>'''
        )
    return "".join(result)


def _alerts_html(expiring: int, blocked: int, online: int, total: int, active_campaigns: int) -> str:
    alerts = []
    if expiring:
        alerts.append(("warning", "⏳", f"{expiring:,} اشتراک نزدیک به پایان", "برای تمدید یا کمپین بازگشت بررسی شوند."))
    if blocked:
        alerts.append(("danger", "⛔", f"{blocked:,} کاربر مسدود", "وضعیت کاربران مسدود را بازبینی کنید."))
    if total and online == 0:
        alerts.append(("warning", "◉", "کاربر آنلاین ثبت نشده", "ممکن است ثبت last_seen نیاز به بررسی داشته باشد."))
    if active_campaigns == 0:
        alerts.append(("warning", "🎯", "کمپین فعالی وجود ندارد", "برای بازگشت کاربران یا فروش، کمپین جدید بسازید."))
    if not alerts:
        alerts.append(("success", "✓", "وضعیت سامانه پایدار است", "هشدار مهمی در داده‌های فعلی دیده نشد."))
    return "".join(
        f'''<div class="alert-item {kind}"><span>{icon}</span><div class="alert-copy"><strong>{esc(title)}</strong><small>{esc(note)}</small></div></div>'''
        for kind, icon, title, note in alerts[:4]
    )


@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    metrics = dashboard_metrics() or {}
    try:
        days = max(7, min(int(request.query_params.get('days', '14')), 90))
    except ValueError:
        days = 14
    series = dashboard_daily_series(days) or []
    recent = dashboard_recent_activity(7) or []
    now = utc_now()
    week_start = isoformat(now - timedelta(days=7))
    month_start = isoformat(now - timedelta(days=30))
    next_week = isoformat(now + timedelta(days=7))
    now_text = isoformat(now)

    with database() as connection:
        new_week = _int(connection.execute(
            "SELECT COUNT(*) AS n FROM users WHERE created_at >= ?", (week_start,)
        ).fetchone()["n"])
        active_month = _int(connection.execute(
            "SELECT COUNT(*) AS n FROM users WHERE last_seen_at >= ?", (month_start,)
        ).fetchone()["n"])
        usage_month = _int(connection.execute(
            "SELECT COUNT(*) AS n FROM usage_events WHERE created_at >= ?", (month_start,)
        ).fetchone()["n"])
        expired = _int(connection.execute(
            "SELECT COUNT(DISTINCT user_id) AS n FROM subscriptions WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now_text,),
        ).fetchone()["n"])
        expiring = _int(connection.execute(
            """SELECT COUNT(DISTINCT user_id) AS n FROM subscriptions
               WHERE is_active = 1 AND expires_at IS NOT NULL AND expires_at > ? AND expires_at <= ?""",
            (now_text, next_week),
        ).fetchone()["n"])
        top_features = connection.execute(
            """SELECT feature_key, COUNT(*) AS total FROM usage_events
               WHERE created_at >= ? GROUP BY feature_key ORDER BY total DESC LIMIT 6""",
            (month_start,),
        ).fetchall()
        newest = connection.execute(
            """SELECT COALESCE(display_name, phone, email, installation_id) AS title, created_at
               FROM users ORDER BY created_at DESC LIMIT 5"""
        ).fetchall()

    total = _int(metrics.get("total_users"))
    premium = _int(metrics.get("premium_users"))
    free = _int(metrics.get("free_users"))
    online = _int(metrics.get("online_users"))
    blocked = _int(metrics.get("blocked_users"))
    usage_today = _int(metrics.get("usage_today"))
    active_campaigns = _int(metrics.get("active_campaigns"))
    enabled_notifications = _int(metrics.get("enabled_notifications"))
    conversion = _pct(premium, total)
    activity_rate = _pct(active_month, total)

    newest_html = "".join(
        f'<div class="health-row"><span>{esc(_value(row, "title", "کاربر"))}</span><small class="section-sub">{esc(_value(row, "created_at", "-"))}</small></div>'
        for row in newest
    ) or '<div class="empty-state">کاربری ثبت نشده است.</div>'

    body = f'''
<div class="filters" style="margin-bottom:12px"><a class="filter-link" href="/admin?days=7">۷ روز</a><a class="filter-link" href="/admin?days=14">۱۴ روز</a><a class="filter-link" href="/admin?days=30">۳۰ روز</a><a class="filter-link" href="/admin?days=90">۹۰ روز</a><span class="section-sub">انتخاب بازه نمودار</span></div>
<div class="dashboard-grid">
  <section class="card metric-card"><div class="metric-head"><span class="metric-label">کل کاربران</span><span class="metric-icon">👥</span></div><div class="metric-value">{total:,}</div><div class="metric-note"><span class="trend up">+{_int(metrics.get('new_users_today'))} امروز</span> · {new_week:,} این هفته</div></section>
  <section class="card metric-card"><div class="metric-head"><span class="metric-label">کاربران آنلاین</span><span class="metric-icon">●</span></div><div class="metric-value">{online:,}</div><div class="metric-note">فعال در ۱۵ دقیقه اخیر</div></section>
  <section class="card metric-card"><div class="metric-head"><span class="metric-label">اشتراک Pro</span><span class="metric-icon">★</span></div><div class="metric-value">{premium:,}</div><div class="metric-note">نرخ تبدیل <span class="trend up">{conversion}%</span></div></section>
  <section class="card metric-card"><div class="metric-head"><span class="metric-label">مصرف امروز</span><span class="metric-icon">⚡</span></div><div class="metric-value">{usage_today:,}</div><div class="metric-note">{usage_month:,} رویداد در ۳۰ روز</div></section>
  <section class="card metric-card"><div class="metric-head"><span class="metric-label">کاربران فعال ماه</span><span class="metric-icon">📈</span></div><div class="metric-value">{active_month:,}</div><div class="metric-note">نرخ فعالیت {activity_rate}%</div></section>
  <section class="card metric-card"><div class="metric-head"><span class="metric-label">کاربران رایگان</span><span class="metric-icon">◇</span></div><div class="metric-value">{free:,}</div><div class="metric-note">فرصت تبدیل به اشتراک</div></section>
  <section class="card metric-card"><div class="metric-head"><span class="metric-label">اشتراک نزدیک پایان</span><span class="metric-icon">⌛</span></div><div class="metric-value">{expiring:,}</div><div class="metric-note">{expired:,} اشتراک منقضی‌شده</div></section>
  <section class="card metric-card"><div class="metric-head"><span class="metric-label">کاربران مسدود</span><span class="metric-icon">⛔</span></div><div class="metric-value">{blocked:,}</div><div class="metric-note">مدیریت از صفحه کاربران</div></section>
</div>

<div class="dashboard-main">
  <section class="card"><div class="section-title"><div><h3>رشد و مصرف {days} روز اخیر</h3><div class="section-sub">مقایسه ثبت‌نام کاربران با استفاده از ابزارها</div></div><div class="legend"><span class="users">کاربر جدید</span><span class="usage">استفاده ابزارها</span></div></div><div class="chart">{_build_chart(series)}</div></section>
  <section class="card"><div class="section-title"><div><h3>مرکز هشدارها</h3><div class="section-sub">مواردی که نیاز به توجه مدیر دارند</div></div></div><div class="alert-list">{_alerts_html(expiring, blocked, online, total, active_campaigns)}</div></section>
</div>

<div class="split">
  <section class="card"><div class="section-title"><div><h3>قابلیت‌های پرمصرف</h3><div class="section-sub">۳۰ روز اخیر</div></div><a class="badge badge-pro" href="/admin/analytics">گزارش کامل</a></div><div class="bar-list">{_feature_bars(top_features)}</div></section>
  <section class="card"><div class="section-title"><div><h3>آخرین فعالیت‌ها</h3><div class="section-sub">جدیدترین رویدادهای ثبت‌شده در اپ</div></div></div><div class="activity-list">{_recent_html(recent)}</div></section>
</div>

<div class="dashboard-main">
  <section class="card"><div class="section-title"><div><h3>دسترسی سریع</h3><div class="section-sub">عملیات پرکاربرد مدیریت</div></div></div><div class="quick-grid">
    <a class="quick-link" href="/admin/users">👥 کاربران و اشتراک‌ها</a><a class="quick-link" href="/admin/campaigns">🎯 ساخت کمپین</a>
    <a class="quick-link" href="/admin/notifications">🔔 ارسال اعلان</a><a class="quick-link" href="/admin/support">💬 تیکت‌های پشتیبانی</a>
    <a class="quick-link" href="/admin/analytics">📊 گزارش‌های تحلیلی</a><a class="quick-link" href="/admin/features">🧩 مدیریت قابلیت‌ها</a>
    <a class="quick-link" href="/admin/settings">⚙️ نسخه و تنظیمات</a><a class="quick-link" href="/admin/logout">↪ خروج امن</a>
  </div></section>
  <section class="card"><div class="section-title"><div><h3>وضعیت سامانه</h3><div class="section-sub">بررسی سریع سرویس‌های اصلی</div></div></div>
    <div class="health-row"><span>FastAPI Backend</span><span class="health-status">● فعال</span></div>
    <div class="health-row"><span>دیتابیس SQLite</span><span class="health-status">● متصل</span></div>
    <div class="health-row"><span>ثبت رویدادها</span><span class="health-status">● در حال دریافت</span></div>
    <div class="health-row"><span>کمپین فعال</span><span class="badge badge-pro">{active_campaigns}</span></div>
    <div class="health-row"><span>اعلان فعال</span><span class="badge badge-pro">{enabled_notifications}</span></div>
  </section>
</div>

<div class="card" style="margin-top:13px"><div class="section-title"><div><h3>جدیدترین کاربران</h3><div class="section-sub">آخرین حساب‌های ایجادشده</div></div><a class="badge badge-pro" href="/admin/users">مشاهده همه</a></div>{newest_html}</div>
'''
    return HTMLResponse(page_layout("داشبورد مدیریت", body))

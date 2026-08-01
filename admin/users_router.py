from __future__ import annotations

from .common import *  # noqa: F401,F403

router = APIRouter(prefix="/admin")


def _pretty_datetime(value) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    try:
        normalized = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.astimezone(timezone(timedelta(hours=3, minutes=30))).strftime("%Y/%m/%d - %H:%M")
    except (ValueError, TypeError):
        return text[:19].replace("T", " ")


@router.get(
    "/users",
    response_class=HTMLResponse,
)
async def users_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    search = request.query_params.get("search", "").strip()
    plan_filter = request.query_params.get("plan", "all").strip()
    status_filter = request.query_params.get("status", "all").strip()
    sort = request.query_params.get("sort", "recent").strip()
    try:
        page = max(1, int(request.query_params.get("page", "1")))
    except ValueError:
        page = 1

    per_page = 30
    offset = (page - 1) * per_page
    now = utc_now()
    now_text = isoformat(now)
    online_since = isoformat(now - timedelta(minutes=15))
    like = f"%{search}%"

    where = ["(u.installation_id LIKE ? OR COALESCE(u.auth_user_id,'') LIKE ? OR COALESCE(u.display_name,'') LIKE ? OR COALESCE(u.phone,'') LIKE ? OR COALESCE(u.email,'') LIKE ? OR COALESCE(u.device_model,'') LIKE ?)"]
    params: list[object] = [like, like, like, like, like, like]

    if status_filter == "online":
        where.append("u.last_seen_at >= ?")
        params.append(online_since)
    elif status_filter == "blocked":
        where.append("u.is_blocked = 1")
    elif status_filter == "inactive":
        where.append("u.last_seen_at < ?")
        params.append(isoformat(now - timedelta(days=30)))

    premium_expr = "EXISTS (SELECT 1 FROM subscriptions s WHERE s.user_id=u.id AND s.is_active=1 AND (s.expires_at IS NULL OR s.expires_at > ?))"
    if plan_filter == "pro":
        where.append(premium_expr)
        params.append(now_text)
    elif plan_filter == "free":
        where.append("NOT " + premium_expr)
        params.append(now_text)

    order_sql = {
        "oldest": "u.created_at ASC",
        "name": "COALESCE(u.display_name,u.phone,u.email,u.installation_id) COLLATE NOCASE ASC",
        "online": "u.last_seen_at DESC",
        "recent": "u.created_at DESC",
    }.get(sort, "u.last_seen_at DESC")
    where_sql = " AND ".join(where)

    with database() as connection:
        total = int(connection.execute(
            f"SELECT COUNT(*) AS total FROM users u WHERE {where_sql}", tuple(params)
        ).fetchone()["total"])
        users = connection.execute(
            f"""
            SELECT u.*,
              COALESCE((SELECT SUM(used_count) FROM usage_counters uc WHERE uc.user_id=u.id),0) AS counter_total,
              COALESCE((SELECT COUNT(*) FROM usage_events ue WHERE ue.installation_id=u.installation_id),0) AS event_total,
              COALESCE((SELECT SUM(used_count) FROM usage_counters uc WHERE uc.user_id=u.id AND uc.feature_key='analyzer'),0) AS analyzer_used,
              COALESCE((SELECT SUM(used_count) FROM usage_counters uc WHERE uc.user_id=u.id AND uc.feature_key IN ('image_generate','image_edit')),0) AS image_used,
              COALESCE((SELECT SUM(used_count) FROM usage_counters uc WHERE uc.user_id=u.id AND uc.feature_key IN ('text_content','content_studio')),0) AS content_used
            FROM users u
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
            """, tuple(params + [per_page, offset])
        ).fetchall()
        summary = connection.execute(
            """SELECT COUNT(*) AS total,
              SUM(CASE WHEN is_blocked=1 THEN 1 ELSE 0 END) AS blocked,
              SUM(CASE WHEN last_seen_at>=? THEN 1 ELSE 0 END) AS online,
              SUM(CASE WHEN created_at>=? THEN 1 ELSE 0 END) AS new_today
              FROM users""",
            (online_since, isoformat(now.replace(hour=0, minute=0, second=0, microsecond=0))),
        ).fetchone()
        pro_total = int(connection.execute(
            """SELECT COUNT(DISTINCT user_id) AS total FROM subscriptions
               WHERE is_active=1 AND (expires_at IS NULL OR expires_at>?)""", (now_text,)
        ).fetchone()["total"])

    cards = []
    drawer_templates = []
    for user in users:
        subscription = user_subscription_snapshot(user)
        premium = bool(subscription["is_premium"])
        blocked = bool(user["is_blocked"])
        online = (user["last_seen_at"] or "") >= online_since
        name_raw = user["display_name"] or user["phone"] or user["email"] or "کاربر بدون نام"
        initial = esc(name_raw.strip()[:1] or "ک")
        installation_id = esc(user["installation_id"])
        user_id = esc(user["id"])
        device = " ".join(part for part in [user["manufacturer"], user["device_model"]] if part) or "نامشخص"
        presence = "blocked" if blocked else ("online" if online else "offline")
        status_badge = '<span class="badge badge-off">مسدود</span>' if blocked else ('<span class="badge badge-active">آنلاین</span>' if online else '<span class="badge badge-free">آفلاین</span>')
        plan_badge = '<span class="badge badge-pro">رشد یار Pro</span>' if premium else '<span class="badge badge-free">رایگان</span>'
        expires = esc(_pretty_datetime(subscription.get("expires_at")) if subscription.get("expires_at") else "بدون تاریخ")
        source = esc(subscription.get("source") or "-")

        drawer_id = f"drawer-{user_id}"
        drawer_templates.append(f"""
<template id="{drawer_id}">
  <div class="drawer-profile">
    <div class="avatar-ring"><div class="avatar-v3">{initial}</div></div>
    <div><div class="user-name" style="font-size:18px">{esc(name_raw)}</div><div class="user-sub">{esc(user['email'] or 'بدون ایمیل')} · {esc(user['phone'] or 'بدون شماره')}</div><div class="user-badges">{plan_badge}{status_badge}</div></div>
  </div>
  <div class="drawer-grid">
    <div class="drawer-item"><small>دستگاه</small><strong>{esc(device)}</strong></div>
    <div class="drawer-item"><small>اندروید / نسخه اپ</small><strong>{esc(user['android_version'] or '-')} / {esc(user['app_version'] or '-')}</strong></div>
    <div class="drawer-item"><small>آخرین اتصال</small><strong>{esc(_pretty_datetime(user['last_seen_at']))}</strong></div>
    <div class="drawer-item"><small>عضویت</small><strong>{esc(_pretty_datetime(user['created_at']))}</strong></div>
    <div class="drawer-item"><small>انقضای اشتراک</small><strong>{expires}</strong></div>
    <div class="drawer-item"><small>منبع اشتراک</small><strong>{source}</strong></div>
  </div>
  <div class="usage-strip" style="margin-bottom:14px">
    <div class="usage-chip"><strong>{int(user['analyzer_used'] or 0)}</strong><span>تحلیل</span></div>
    <div class="usage-chip"><strong>{int(user['image_used'] or 0)}</strong><span>تصویر</span></div>
    <div class="usage-chip"><strong>{int(user['content_used'] or 0)}</strong><span>محتوا</span></div>
  </div>
  <div class="drawer-item" style="margin-bottom:14px"><small>Installation ID</small><strong style="display:block;direction:ltr;word-break:break-all">{installation_id}</strong></div>
  <div class="drawer-actions">
    <a class="btn btn-secondary btn-icon" href="/admin/users/{user_id}">📋 جزئیات کامل</a>
    <form method="post" action="/admin/users/activate"><input type="hidden" name="installation_id" value="{installation_id}"><input type="hidden" name="days" value="30"><button class="btn btn-success btn-icon">➕ تمدید ۳۰ روز</button></form>
    <form method="post" action="/admin/users/reset-usage" onsubmit="return confirm('سهمیه‌های این کاربر ریست شود؟')"><input type="hidden" name="user_id" value="{user_id}"><button class="btn btn-secondary btn-icon">↻ ریست سهمیه</button></form>
    <form method="post" action="/admin/users/toggle-block" onsubmit="return confirm('وضعیت دسترسی کاربر تغییر کند؟')"><input type="hidden" name="user_id" value="{user_id}"><button class="btn {'btn-secondary' if blocked else 'btn-danger'} btn-icon">{'🔓 رفع مسدودی' if blocked else '⛔ مسدودسازی'}</button></form>
  </div>
</template>
""")

        cards.append(f"""
<article class="user-card-v3">
  <div class="user-profile">
    <div class="avatar-wrap"><div class="avatar-ring"><div class="avatar-v3">{initial}</div></div><span class="presence-dot {presence}"></span></div>
    <div class="user-main">
      <div class="user-name">{esc(name_raw)}</div>
      <div class="user-sub">{esc(user['email'] or 'بدون ایمیل')}</div>
      <div class="user-sub">{esc(user['phone'] or 'بدون شماره')}</div>
      <div class="user-badges">{plan_badge}{status_badge}</div>
    </div>
  </div>
  <div class="info-stack">
    <div class="info-row"><b>دستگاه</b><span>{esc(device)}</span></div>
    <div class="info-row"><b>اندروید</b><span>{esc(user['android_version'] or '-')}</span></div>
    <div class="info-row"><b>نسخه اپ</b><span>{esc(user['app_version'] or '-')}</span></div>
    <div class="info-row"><b>آخرین اتصال</b><span>{esc(_pretty_datetime(user['last_seen_at']))}</span></div>
  </div>
  <div>
    <div class="usage-strip">
      <div class="usage-chip"><strong>{int(user['analyzer_used'] or 0)}</strong><span>تحلیل</span></div>
      <div class="usage-chip"><strong>{int(user['image_used'] or 0)}</strong><span>تصویر</span></div>
      <div class="usage-chip"><strong>{int(user['content_used'] or 0)}</strong><span>محتوا</span></div>
    </div>
    <div class="user-sub" style="margin-top:9px">انقضا: {expires}</div>
  </div>
  <div class="user-actions">
    <button class="btn btn-secondary btn-small btn-icon" type="button" onclick="openUserDrawer('{drawer_id}')">👁 مشاهده</button>
    <form method="post" action="/admin/users/activate"><input type="hidden" name="installation_id" value="{installation_id}"><input type="hidden" name="days" value="30"><button class="btn btn-success btn-small btn-icon" type="submit">➕ ۳۰ روز</button></form>
    <details class="more-menu"><summary>⋮</summary><div class="more-pop"><a href="/admin/users/{user_id}">جزئیات کامل</a><form method="post" action="/admin/users/reset-usage" onsubmit="return confirm('سهمیه‌ها ریست شود؟')"><input type="hidden" name="user_id" value="{user_id}"><button>ریست سهمیه</button></form><form method="post" action="/admin/users/toggle-block" onsubmit="return confirm('وضعیت کاربر تغییر کند؟')"><input type="hidden" name="user_id" value="{user_id}"><button>{'رفع مسدودی' if blocked else 'مسدودسازی'}</button></form></div></details>
  </div>
</article>
""")

    total_pages = max(1, (total + per_page - 1) // per_page)
    def page_url(number: int) -> str:
        return "/admin/users?" + urllib.parse.urlencode({"search": search, "plan": plan_filter, "status": status_filter, "sort": sort, "page": number})

    pagination = []
    if page > 1:
        pagination.append(f'<a class="page-link" href="{esc(page_url(page-1))}">قبلی</a>')
    for number in range(max(1, page-2), min(total_pages, page+2)+1):
        pagination.append(f'<a class="page-link {"active" if number==page else ""}" href="{esc(page_url(number))}">{number}</a>')
    if page < total_pages:
        pagination.append(f'<a class="page-link" href="{esc(page_url(page+1))}">بعدی</a>')

    body = f"""
<section class="users-hero"><div><h2>مدیریت کاربران رشد یار</h2><p>جستجو، بررسی مصرف، تمدید اشتراک و مدیریت دسترسی کاربران در یک صفحه</p></div><span class="badge badge-pro">{total} نتیجه</span></section>
<section class="card">
  <form method="get" action="/admin/users" class="users-toolbar">
    <div class="search-wrap"><label>جستجو</label><span class="search-icon">🔎</span><input id="user-search" name="search" value="{esc(search)}" placeholder="نام، ایمیل، شماره، دستگاه یا شناسه"><button class="clear-search" type="button" onclick="document.getElementById('user-search').value=''">×</button></div>
    <div><label>پلن</label><select name="plan"><option value="all" {'selected' if plan_filter=='all' else ''}>همه پلن‌ها</option><option value="pro" {'selected' if plan_filter=='pro' else ''}>فقط Pro</option><option value="free" {'selected' if plan_filter=='free' else ''}>فقط رایگان</option></select></div>
    <div><label>وضعیت</label><select name="status"><option value="all" {'selected' if status_filter=='all' else ''}>همه</option><option value="online" {'selected' if status_filter=='online' else ''}>آنلاین</option><option value="blocked" {'selected' if status_filter=='blocked' else ''}>مسدود</option><option value="inactive" {'selected' if status_filter=='inactive' else ''}>۳۰ روز غیرفعال</option></select></div>
    <div><label>مرتب‌سازی</label><select name="sort"><option value="recent" {'selected' if sort=='recent' else ''}>جدیدترین</option><option value="online" {'selected' if sort=='online' else ''}>آخرین اتصال</option><option value="name" {'selected' if sort=='name' else ''}>نام</option><option value="oldest" {'selected' if sort=='oldest' else ''}>قدیمی‌ترین</option></select></div>
    <button class="btn btn-primary btn-icon" type="submit">⚙️ اعمال فیلتر</button>
  </form>
</section>
<div class="users-summary">
  <div class="mini-stat"><div class="stat-icon">👥</div><span>کل کاربران</span><strong>{int(summary['total'] or 0)}</strong></div>
  <div class="mini-stat"><div class="stat-icon">⭐</div><span>کاربران Pro</span><strong>{pro_total}</strong></div>
  <div class="mini-stat"><div class="stat-icon">🆓</div><span>رایگان</span><strong>{max(int(summary['total'] or 0)-pro_total,0)}</strong></div>
  <div class="mini-stat"><div class="stat-icon">🟢</div><span>آنلاین</span><strong>{int(summary['online'] or 0)}</strong></div>
  <div class="mini-stat"><div class="stat-icon">⛔</div><span>مسدود</span><strong>{int(summary['blocked'] or 0)}</strong></div>
</div>
<div class="section-title"><h3>{total} کاربر پیدا شد</h3><span class="badge badge-pro">صفحه {page} از {total_pages}</span></div>
<div class="user-list">{''.join(cards) or '<section class="card">کاربری با این فیلتر پیدا نشد.</section>'}</div>
<div class="pagination">{''.join(pagination)}</div>
{''.join(drawer_templates)}
<div class="drawer-backdrop" onclick="closeUserDrawer()"></div>
<aside class="user-drawer" aria-hidden="true"><div class="drawer-head"><strong>جزئیات سریع کاربر</strong><button class="drawer-close" onclick="closeUserDrawer()">×</button></div><div id="drawer-content" class="drawer-body"></div></aside>
<script>
function openUserDrawer(templateId) {{
  const template = document.getElementById(templateId);
  if (!template) return;
  document.getElementById('drawer-content').innerHTML = template.innerHTML;
  document.body.classList.add('drawer-open');
  document.querySelector('.user-drawer').setAttribute('aria-hidden','false');
}}
function closeUserDrawer() {{
  document.body.classList.remove('drawer-open');
  document.querySelector('.user-drawer').setAttribute('aria-hidden','true');
}}
document.addEventListener('keydown', function(event) {{ if (event.key === 'Escape') closeUserDrawer(); }});
document.addEventListener('click', function(event) {{
  document.querySelectorAll('.more-menu[open]').forEach(function(menu) {{ if (!menu.contains(event.target)) menu.removeAttribute('open'); }});
}});
</script>
"""
    return HTMLResponse(page_layout("کاربران و اشتراک‌ها", body))


@router.get("/users/{user_id}", response_class=HTMLResponse)
async def user_detail_page(user_id: str, request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect
    with database() as connection:
        user = connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not user:
            return HTMLResponse(page_layout("کاربر پیدا نشد", '<section class="card">کاربر موردنظر وجود ندارد.</section>'), status_code=404)
        subscriptions = connection.execute("SELECT * FROM subscriptions WHERE user_id=? ORDER BY created_at DESC LIMIT 30", (user_id,)).fetchall()
        counters = connection.execute("SELECT feature_key, SUM(used_count) AS total FROM usage_counters WHERE user_id=? GROUP BY feature_key ORDER BY total DESC", (user_id,)).fetchall()
        events = connection.execute("SELECT feature_key,event_type,created_at FROM usage_events WHERE installation_id=? ORDER BY created_at DESC LIMIT 40", (user['installation_id'],)).fetchall()
    snapshot = user_subscription_snapshot(user)
    sub_rows = ''.join(f"<tr><td>{esc(s['plan_key'])}</td><td>{esc(s['source'])}</td><td>{esc(s['starts_at'])}</td><td>{esc(s['expires_at'] or 'بدون تاریخ')}</td><td>{'<span class=\"badge badge-active\">فعال</span>' if s['is_active'] else '<span class=\"badge badge-off\">غیرفعال</span>'}</td></tr>" for s in subscriptions)
    usage_cards = ''.join(f'<div class="usage-item"><strong>{esc(c["feature_key"])}</strong><div class="stat" style="font-size:23px">{int(c["total"] or 0)}</div></div>' for c in counters)
    event_rows = ''.join(f'<tr><td>{esc(e["feature_key"])}</td><td>{esc(e["event_type"])}</td><td>{esc(e["created_at"])}</td></tr>' for e in events)
    body=f"""
<div class="actions" style="margin-bottom:16px"><a class="btn btn-secondary" href="/admin/users">بازگشت به کاربران</a></div>
<div class="detail-grid">
 <div class="detail-card"><small>نام کاربر</small><strong>{esc(user['display_name'] or 'بدون نام')}</strong></div>
 <div class="detail-card"><small>پلن فعلی</small><strong>{'رشد یار Pro' if snapshot['is_premium'] else 'رایگان'}</strong></div>
 <div class="detail-card"><small>وضعیت</small><strong>{'مسدود' if user['is_blocked'] else 'فعال'}</strong></div>
 <div class="detail-card"><small>آخرین اتصال</small><strong>{esc(user['last_seen_at'])}</strong></div>
 <div class="detail-card"><small>ایمیل</small><strong>{esc(user['email'] or '-')}</strong></div>
 <div class="detail-card"><small>شماره</small><strong>{esc(user['phone'] or '-')}</strong></div>
 <div class="detail-card"><small>دستگاه</small><strong>{esc((user['manufacturer'] or '')+' '+(user['device_model'] or ''))}</strong></div>
 <div class="detail-card"><small>نسخه اپ / اندروید</small><strong>{esc(user['app_version'] or '-')} / {esc(user['android_version'] or '-')}</strong></div>
</div>
<section class="card" style="margin-bottom:16px"><h3>مدیریت سریع</h3><div class="actions">
<form method="post" action="/admin/users/activate"><input type="hidden" name="installation_id" value="{esc(user['installation_id'])}"><input name="days" type="number" min="1" max="3650" value="30" style="width:100px"><button class="btn btn-primary">فعال‌سازی / تمدید</button></form>
<form method="post" action="/admin/users/deactivate" onsubmit="return confirm('اشتراک غیرفعال شود؟')"><input type="hidden" name="installation_id" value="{esc(user['installation_id'])}"><button class="btn btn-danger">غیرفعال‌کردن اشتراک</button></form>
<form method="post" action="/admin/users/reset-usage" onsubmit="return confirm('همه سهمیه‌های این کاربر ریست شود؟')"><input type="hidden" name="user_id" value="{esc(user_id)}"><button class="btn btn-secondary">ریست سهمیه</button></form>
<form method="post" action="/admin/users/toggle-block"><input type="hidden" name="user_id" value="{esc(user_id)}"><button class="btn {'btn-secondary' if user['is_blocked'] else 'btn-danger'}">{'رفع مسدودی' if user['is_blocked'] else 'مسدودسازی'}</button></form>
</div></section>
<section class="card" style="margin-bottom:16px"><h3>مصرف سهمیه‌ها</h3><div class="usage-grid">{usage_cards or '<div>مصرفی ثبت نشده است.</div>'}</div></section>
<section class="card" style="margin-bottom:16px"><h3>تاریخچه اشتراک</h3><div style="overflow:auto"><table><thead><tr><th>پلن</th><th>منبع</th><th>شروع</th><th>انقضا</th><th>وضعیت</th></tr></thead><tbody>{sub_rows or '<tr><td colspan="5">اشتراکی ثبت نشده است.</td></tr>'}</tbody></table></div></section>
<section class="card"><h3>آخرین فعالیت‌ها</h3><div style="overflow:auto"><table><thead><tr><th>قابلیت</th><th>رویداد</th><th>زمان</th></tr></thead><tbody>{event_rows or '<tr><td colspan="3">فعالیتی ثبت نشده است.</td></tr>'}</tbody></table></div></section>
"""
    return HTMLResponse(page_layout("جزئیات کاربر", body))


@router.post("/users/activate")
async def activate_user(
    request: Request,
):
    redirect = require_auth(request)

    if redirect:
        return redirect

    form = await read_form(request)

    installation_id = form.get(
        "installation_id",
        "",
    ).strip()

    try:
        days = max(
            1,
            min(
                int(form.get("days", "30")),
                3650,
            ),
        )
    except ValueError:
        days = 30

    user = get_or_create_user(
        installation_id=
            installation_id
    )

    now = utc_now()
    expires_at = now + timedelta(
        days=days
    )

    with database() as connection:
        connection.execute(
            """
            UPDATE subscriptions
            SET is_active = 0,
                updated_at = ?
            WHERE user_id = ?
              AND is_manual = 1
            """,
            (
                isoformat(now),
                user["id"],
            ),
        )

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
                created_at,
                updated_at
            )
            VALUES (?, ?, 'manual', 'admin', ?, ?, 1, 1, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                user["id"],
                isoformat(now),
                isoformat(expires_at),
                isoformat(now),
                isoformat(now),
            ),
        )

    return RedirectResponse(
        url="/admin/users",
        status_code=303,
    )


@router.post("/users/deactivate")
async def deactivate_user(
    request: Request,
):
    redirect = require_auth(request)

    if redirect:
        return redirect

    form = await read_form(request)

    installation_id = form.get(
        "installation_id",
        "",
    ).strip()

    user = get_or_create_user(
        installation_id=
            installation_id
    )

    with database() as connection:
        connection.execute(
            """
            UPDATE subscriptions
            SET is_active = 0,
                updated_at = ?
            WHERE user_id = ?
            """,
            (
                isoformat(utc_now()),
                user["id"],
            ),
        )

    return RedirectResponse(
        url="/admin/users",
        status_code=303,
    )




@router.post("/users/toggle-block")
async def toggle_user_block(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect
    form = await read_form(request)
    user_id = form.get("user_id", "").strip()
    with database() as connection:
        row = connection.execute("SELECT is_blocked FROM users WHERE id=?", (user_id,)).fetchone()
        if row:
            connection.execute("UPDATE users SET is_blocked=?, updated_at=? WHERE id=?", (0 if row['is_blocked'] else 1, isoformat(utc_now()), user_id))
    return RedirectResponse(url=request.headers.get("referer") or "/admin/users", status_code=303)


@router.post("/users/reset-usage")
async def reset_user_usage(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect
    form = await read_form(request)
    user_id = form.get("user_id", "").strip()
    with database() as connection:
        connection.execute("DELETE FROM usage_counters WHERE user_id=?", (user_id,))
        connection.execute("INSERT INTO admin_actions(id,action,target_type,target_id,payload,created_at) VALUES(?,?,?,?,?,?)", (str(uuid.uuid4()), 'reset_usage', 'user', user_id, '{}', isoformat(utc_now())))
    return RedirectResponse(url=request.headers.get("referer") or "/admin/users", status_code=303)

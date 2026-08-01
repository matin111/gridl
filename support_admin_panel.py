from __future__ import annotations

import uuid
from datetime import datetime, timezone
from urllib.parse import quote_plus

from fastapi import (
    APIRouter,
    Request,
)
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
)

from admin_panel import (
    esc,
    page_layout,
    read_form,
    require_auth,
)
from support_api import (
    database,
    utc_now_text,
)


router = APIRouter(
    prefix="/admin/support",
    tags=["admin-support-panel"],
)


def status_title(value: str) -> str:
    return {
        "open": "باز",
        "answered": "پاسخ داده‌شده",
        "closed": "بسته",
    }.get(value, value)


def status_class(value: str) -> str:
    return {
        "open": "support-status-open",
        "answered": "support-status-answered",
        "closed": "support-status-closed",
    }.get(value, "support-status-open")


def category_title(value: str) -> str:
    return {
        "general": "عمومی",
        "account": "حساب کاربری",
        "subscription": "اشتراک",
        "payment": "پرداخت",
        "technical": "فنی",
        "feature": "پیشنهاد قابلیت",
        "bug": "گزارش خطا",
    }.get(value, value or "عمومی")


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = str(value).strip().replace("Z", "+00:00")

    try:
        result = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)

    return result.astimezone(timezone.utc)


def relative_time(value: str | None) -> str:
    parsed = parse_datetime(value)

    if parsed is None:
        return esc(value or "—")

    now = datetime.now(timezone.utc)
    seconds = max(0, int((now - parsed).total_seconds()))

    if seconds < 60:
        return "همین حالا"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} دقیقه پیش"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} ساعت پیش"

    days = hours // 24
    if days < 7:
        return f"{days} روز پیش"

    weeks = days // 7
    if weeks < 5:
        return f"{weeks} هفته پیش"

    return parsed.strftime("%Y/%m/%d - %H:%M")


def initials(name: str | None) -> str:
    clean = (name or "کاربر").strip()
    return esc(clean[:1].upper() if clean else "ک")


def attachment_html(attachment_url: str | None) -> str:
    if not attachment_url:
        return ""

    safe_url = esc(attachment_url)

    return f"""
<a href="{safe_url}" target="_blank" rel="noopener" class="support-attachment">
  <img src="{safe_url}" alt="تصویر پیوست">
</a>
"""


def support_styles() -> str:
    return """
<style>
.support-shell{
  display:grid;
  gap:18px;
}
.support-intro{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:16px;
  flex-wrap:wrap;
}
.support-intro h2{
  margin:0 0 7px;
  font-size:22px;
}
.support-intro p{
  margin:0;
  color:#77778e;
  line-height:1.8;
}
.support-refresh{
  display:inline-flex;
  align-items:center;
  gap:8px;
  text-decoration:none;
}
.support-stats{
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:14px;
}
.support-stat{
  position:relative;
  overflow:hidden;
  min-height:105px;
  padding:18px;
  border:1px solid #e7e4f5;
  border-radius:20px;
  background:linear-gradient(145deg,#fff,#fbfaff);
}
.support-stat:after{
  content:"";
  position:absolute;
  width:70px;
  height:70px;
  left:-25px;
  bottom:-30px;
  border-radius:50%;
  background:rgba(108,60,255,.08);
}
.support-stat-label{
  color:#77778e;
  font-size:13px;
  font-weight:700;
}
.support-stat-value{
  margin-top:10px;
  font-size:29px;
  font-weight:950;
  color:#171725;
}
.support-toolbar{
  display:grid;
  grid-template-columns:minmax(240px,1fr) auto;
  gap:14px;
  align-items:center;
}
.support-search{
  position:relative;
}
.support-search input{
  margin:0;
  padding-right:44px;
  height:46px;
}
.support-search-icon{
  position:absolute;
  right:15px;
  top:50%;
  transform:translateY(-50%);
  color:#8a8aa3;
}
.support-filters{
  display:flex;
  align-items:center;
  flex-wrap:wrap;
  gap:8px;
}
.support-filter{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-height:42px;
  padding:0 16px;
  border-radius:13px;
  border:1px solid #e7e4f5;
  color:#5d5870;
  background:#fff;
  text-decoration:none;
  font-weight:800;
  font-size:13px;
}
.support-filter.active{
  color:#fff;
  border-color:#6c3cff;
  background:#6c3cff;
  box-shadow:0 8px 20px rgba(108,60,255,.2);
}
.support-table-wrap{
  overflow-x:auto;
  border:1px solid #ece9f7;
  border-radius:18px;
}
.support-table{
  min-width:900px;
  width:100%;
  border-collapse:separate;
  border-spacing:0;
}
.support-table th{
  padding:14px 16px;
  background:#faf9ff;
  color:#77778e;
  font-size:12px;
  text-align:right;
  border-bottom:1px solid #ece9f7;
}
.support-table td{
  padding:15px 16px;
  border-bottom:1px solid #f0eef7;
  vertical-align:middle;
}
.support-row{
  cursor:pointer;
  transition:background .18s ease,transform .18s ease;
}
.support-row:hover{
  background:#faf9ff;
}
.support-row:last-child td{
  border-bottom:0;
}
.support-subject{
  font-weight:900;
  color:#282438;
  margin-bottom:6px;
}
.support-email{
  color:#8a8aa3;
  font-size:12px;
  direction:ltr;
  text-align:right;
}
.support-user{
  display:flex;
  align-items:center;
  gap:10px;
}
.support-avatar{
  width:38px;
  height:38px;
  display:grid;
  place-items:center;
  border-radius:12px;
  background:linear-gradient(145deg,#eee9ff,#ddd2ff);
  color:#6337e6;
  font-weight:950;
  flex:0 0 auto;
}
.support-user-name{
  font-weight:850;
  color:#282438;
}
.support-category{
  display:inline-flex;
  padding:6px 10px;
  border-radius:10px;
  background:#f5f3fb;
  color:#67617c;
  font-size:12px;
  font-weight:750;
}
.support-status{
  display:inline-flex;
  align-items:center;
  gap:7px;
  padding:7px 10px;
  border-radius:999px;
  font-size:12px;
  font-weight:850;
  white-space:nowrap;
}
.support-status:before{
  content:"";
  width:7px;
  height:7px;
  border-radius:50%;
  background:currentColor;
}
.support-status-open{
  color:#2563eb;
  background:#eaf2ff;
}
.support-status-answered{
  color:#11875d;
  background:#e7f8f0;
}
.support-status-closed{
  color:#686579;
  background:#efeff3;
}
.support-unread{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-width:25px;
  height:25px;
  padding:0 7px;
  border-radius:999px;
  background:#6c3cff;
  color:#fff;
  font-size:11px;
  font-weight:950;
}
.support-time{
  color:#686579;
  font-size:12px;
  white-space:nowrap;
}
.support-open-link{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-height:36px;
  padding:0 12px;
  border-radius:11px;
  text-decoration:none;
  background:#f0ebff;
  color:#6235e4;
  font-weight:850;
  font-size:12px;
}
.support-empty{
  text-align:center;
  padding:52px 20px !important;
  color:#77778e;
}
.ticket-layout{
  display:grid;
  grid-template-columns:minmax(0,1fr) 290px;
  gap:18px;
  align-items:start;
}
.ticket-main,.ticket-side{
  min-width:0;
}
.ticket-head{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:16px;
  margin-bottom:18px;
}
.ticket-head h2{
  margin:0 0 8px;
  font-size:21px;
}
.ticket-meta{
  display:flex;
  flex-wrap:wrap;
  gap:8px;
  color:#77778e;
  font-size:12px;
}
.ticket-thread{
  background:#f8f7fc;
  border:1px solid #ece9f7;
  border-radius:20px;
  padding:18px;
  min-height:320px;
}
.ticket-message{
  max-width:min(78%,650px);
  padding:14px 16px;
  border-radius:18px;
  margin:12px 0;
  box-shadow:0 4px 12px rgba(38,31,68,.04);
}
.ticket-message.user{
  margin-left:auto;
  background:#fff;
  border:1px solid #e9e6f1;
  border-bottom-right-radius:5px;
}
.ticket-message.admin{
  margin-right:auto;
  background:#6c3cff;
  color:#fff;
  border-bottom-left-radius:5px;
}
.ticket-message-label{
  font-size:12px;
  font-weight:950;
  margin-bottom:7px;
}
.ticket-message-body{
  white-space:pre-wrap;
  line-height:1.9;
  word-break:break-word;
}
.ticket-message-time{
  margin-top:9px;
  font-size:10px;
  opacity:.72;
}
.support-attachment{
  display:block;
  margin-top:10px;
}
.support-attachment img{
  display:block;
  width:min(360px,100%);
  max-height:360px;
  object-fit:contain;
  border-radius:14px;
  border:1px solid rgba(120,110,150,.18);
  background:#fff;
}
.ticket-reply{
  margin-top:16px;
  padding-top:16px;
  border-top:1px solid #ece9f7;
}
.ticket-reply textarea{
  min-height:125px;
  resize:vertical;
  margin-top:8px;
}
.ticket-reply-footer{
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:12px;
  flex-wrap:wrap;
}
.ticket-side-card{
  padding:18px;
}
.ticket-profile{
  text-align:center;
  padding-bottom:16px;
  border-bottom:1px solid #eeeaf7;
}
.ticket-profile .support-avatar{
  width:58px;
  height:58px;
  border-radius:18px;
  margin:0 auto 10px;
  font-size:20px;
}
.ticket-profile-name{
  font-size:16px;
  font-weight:950;
}
.ticket-profile-email{
  direction:ltr;
  color:#77778e;
  font-size:12px;
  margin-top:5px;
  word-break:break-all;
}
.ticket-info{
  display:grid;
  gap:13px;
  padding-top:16px;
}
.ticket-info-row{
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:12px;
}
.ticket-info-label{
  color:#77778e;
  font-size:12px;
}
.ticket-info-value{
  color:#282438;
  font-size:12px;
  font-weight:850;
  text-align:left;
}
.ticket-actions{
  display:grid;
  gap:9px;
  margin-top:17px;
}
.ticket-actions form,.ticket-actions .btn{
  width:100%;
}
.ticket-actions button{
  width:100%;
}
@media(max-width:1000px){
  .support-stats{grid-template-columns:repeat(2,minmax(0,1fr));}
  .ticket-layout{grid-template-columns:1fr;}
  .ticket-side{order:-1;}
}
@media(max-width:720px){
  .support-toolbar{grid-template-columns:1fr;}
  .support-stats{grid-template-columns:1fr 1fr;}
  .ticket-message{max-width:92%;}
}
@media(max-width:470px){
  .support-stats{grid-template-columns:1fr;}
}
</style>
"""


@router.get(
    "",
    response_class=HTMLResponse,
)
async def tickets_page(
    request: Request,
):
    redirect = require_auth(request)
    if redirect:
        return redirect

    status_filter = request.query_params.get("status", "all").strip()
    search = request.query_params.get("search", "").strip()

    allowed_statuses = {"open", "answered", "closed"}
    where_parts: list[str] = []
    params: list[str] = []

    if status_filter in allowed_statuses:
        where_parts.append("status = ?")
        params.append(status_filter)

    if search:
        where_parts.append(
            "(subject LIKE ? OR user_name LIKE ? OR user_email LIKE ? OR category LIKE ?)"
        )
        like = f"%{search}%"
        params.extend([like, like, like, like])

    where_sql = (
        " WHERE " + " AND ".join(where_parts)
        if where_parts
        else ""
    )

    with database() as connection:
        tickets = connection.execute(
            f"""
            SELECT *
            FROM support_tickets
            {where_sql}
            ORDER BY
                admin_unread_count DESC,
                updated_at DESC
            LIMIT 300
            """,
            tuple(params),
        ).fetchall()

        stats = connection.execute(
            """
            SELECT
                COUNT(*) AS total_count,
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open_count,
                SUM(CASE WHEN status = 'answered' THEN 1 ELSE 0 END) AS answered_count,
                SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) AS closed_count
            FROM support_tickets
            """
        ).fetchone()

    def filter_url(value: str) -> str:
        query_parts = []
        if value != "all":
            query_parts.append(f"status={quote_plus(value)}")
        if search:
            query_parts.append(f"search={quote_plus(search)}")
        suffix = "?" + "&".join(query_parts) if query_parts else ""
        return f"/admin/support{suffix}"

    rows: list[str] = []

    for ticket in tickets:
        unread = int(ticket["admin_unread_count"] or 0)
        ticket_id = esc(ticket["id"])
        status = str(ticket["status"] or "open")

        rows.append(
            f"""
<tr class="support-row" onclick="window.location='/admin/support/{ticket_id}'">
  <td>
    <div class="support-subject">{esc(ticket["subject"])}</div>
    <div class="support-email">{esc(ticket["user_email"])}</div>
  </td>
  <td>
    <div class="support-user">
      <div class="support-avatar">{initials(ticket["user_name"])}</div>
      <div>
        <div class="support-user-name">{esc(ticket["user_name"] or "کاربر")}</div>
        <div class="support-email">{'پیام خوانده‌نشده' if unread else 'بدون پیام جدید'}</div>
      </div>
    </div>
  </td>
  <td><span class="support-category">{esc(category_title(ticket["category"]))}</span></td>
  <td>
    <span class="support-status {status_class(status)}">
      {esc(status_title(status))}
    </span>
  </td>
  <td>{f'<span class="support-unread">{unread}</span>' if unread else '—'}</td>
  <td>
    <span class="support-time" title="{esc(ticket["updated_at"])}">
      {relative_time(ticket["updated_at"])}
    </span>
  </td>
  <td>
    <a class="support-open-link" href="/admin/support/{ticket_id}" onclick="event.stopPropagation()">
      مشاهده
    </a>
  </td>
</tr>
"""
        )

    total_count = int(stats["total_count"] or 0)
    open_count = int(stats["open_count"] or 0)
    answered_count = int(stats["answered_count"] or 0)
    closed_count = int(stats["closed_count"] or 0)

    body = f"""
{support_styles()}
<div class="support-shell">
  <section class="card">
    <div class="support-intro">
      <div>
        <h2>مرکز پشتیبانی کاربران</h2>
        <p>مدیریت، پاسخ‌گویی و پیگیری درخواست‌های ثبت‌شده در اپلیکیشن</p>
      </div>
      <a class="btn btn-secondary support-refresh" href="/admin/support">
        ↻ بروزرسانی
      </a>
    </div>
  </section>

  <div class="support-stats">
    <section class="support-stat">
      <div class="support-stat-label">کل تیکت‌ها</div>
      <div class="support-stat-value">{total_count}</div>
    </section>
    <section class="support-stat">
      <div class="support-stat-label">تیکت‌های باز</div>
      <div class="support-stat-value">{open_count}</div>
    </section>
    <section class="support-stat">
      <div class="support-stat-label">پاسخ داده‌شده</div>
      <div class="support-stat-value">{answered_count}</div>
    </section>
    <section class="support-stat">
      <div class="support-stat-label">بسته‌شده</div>
      <div class="support-stat-value">{closed_count}</div>
    </section>
  </div>

  <section class="card">
    <form class="support-toolbar" method="get" action="/admin/support">
      <div class="support-search">
        <span class="support-search-icon">⌕</span>
        <input
          type="search"
          name="search"
          value="{esc(search)}"
          placeholder="جستجوی موضوع، نام کاربر، ایمیل یا دسته‌بندی..."
        >
        {f'<input type="hidden" name="status" value="{esc(status_filter)}">' if status_filter in allowed_statuses else ''}
      </div>
      <button class="btn btn-primary" type="submit">جستجو</button>
    </form>

    <div class="support-filters" style="margin-top:14px">
      <a class="support-filter {'active' if status_filter not in allowed_statuses else ''}" href="{filter_url('all')}">همه</a>
      <a class="support-filter {'active' if status_filter == 'open' else ''}" href="{filter_url('open')}">باز</a>
      <a class="support-filter {'active' if status_filter == 'answered' else ''}" href="{filter_url('answered')}">پاسخ داده‌شده</a>
      <a class="support-filter {'active' if status_filter == 'closed' else ''}" href="{filter_url('closed')}">بسته</a>
    </div>
  </section>

  <section class="card">
    <div class="support-table-wrap">
      <table class="support-table">
        <thead>
          <tr>
            <th>موضوع</th>
            <th>کاربر</th>
            <th>دسته‌بندی</th>
            <th>وضعیت</th>
            <th>جدید</th>
            <th>آخرین تغییر</th>
            <th>عملیات</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows) if rows else '<tr><td class="support-empty" colspan="7">تیکتی با این فیلتر پیدا نشد.</td></tr>'}
        </tbody>
      </table>
    </div>
  </section>
</div>
"""

    return HTMLResponse(
        page_layout(
            "پشتیبانی کاربران",
            body,
        )
    )


@router.get(
    "/{ticket_id}",
    response_class=HTMLResponse,
)
async def ticket_page(
    ticket_id: str,
    request: Request,
):
    redirect = require_auth(request)
    if redirect:
        return redirect

    with database() as connection:
        ticket = connection.execute(
            """
            SELECT *
            FROM support_tickets
            WHERE id = ?
            """,
            (ticket_id,),
        ).fetchone()

        if not ticket:
            return HTMLResponse(
                page_layout(
                    "درخواست پیدا نشد",
                    '<section class="card">درخواست موردنظر پیدا نشد.</section>',
                ),
                status_code=404,
            )

        messages = connection.execute(
            """
            SELECT *
            FROM support_messages
            WHERE ticket_id = ?
            ORDER BY created_at ASC
            """,
            (ticket_id,),
        ).fetchall()

        connection.execute(
            """
            UPDATE support_tickets
            SET admin_unread_count = 0
            WHERE id = ?
            """,
            (ticket_id,),
        )

    message_cards: list[str] = []

    for message in messages:
        is_admin = message["sender_type"] == "admin"
        message_cards.append(
            f"""
<div class="ticket-message {'admin' if is_admin else 'user'}">
  <div class="ticket-message-label">{'مدیر پشتیبانی' if is_admin else esc(ticket["user_name"] or "کاربر")}</div>
  <div class="ticket-message-body">{esc(message["message"])}</div>
  {attachment_html(message["attachment_url"])}
  <div class="ticket-message-time">{relative_time(message["created_at"])}</div>
</div>
"""
        )

    is_closed = ticket["status"] == "closed"
    ticket_status = str(ticket["status"] or "open")

    body = f"""
{support_styles()}
<div class="ticket-layout">
  <main class="ticket-main">
    <section class="card">
      <div class="ticket-head">
        <div>
          <h2>{esc(ticket["subject"])}</h2>
          <div class="ticket-meta">
            <span>شماره تیکت: {esc(ticket_id[:8])}</span>
            <span>•</span>
            <span>{esc(category_title(ticket["category"]))}</span>
            <span>•</span>
            <span>{relative_time(ticket["updated_at"])}</span>
          </div>
        </div>
        <span class="support-status {status_class(ticket_status)}">
          {esc(status_title(ticket_status))}
        </span>
      </div>

      <div class="ticket-thread">
        {''.join(message_cards) if message_cards else '<div class="support-empty">پیامی در این گفتگو ثبت نشده است.</div>'}
      </div>

      <form class="ticket-reply" method="post" action="/admin/support/{esc(ticket_id)}/reply">
        <label for="reply-message">پاسخ مدیر</label>
        <textarea
          id="reply-message"
          name="message"
          required
          {'disabled' if is_closed else ''}
          placeholder="پاسخ خود را برای کاربر بنویسید..."
        ></textarea>

        <div class="ticket-reply-footer">
          <span style="color:#8a8aa3;font-size:12px">
            پاسخ از طریق مرکز پشتیبانی داخل اپ برای کاربر نمایش داده می‌شود.
          </span>
          <button
            class="btn btn-primary"
            type="submit"
            {'disabled' if is_closed else ''}
          >
            ارسال پاسخ
          </button>
        </div>
      </form>
    </section>
  </main>

  <aside class="ticket-side">
    <section class="card ticket-side-card">
      <div class="ticket-profile">
        <div class="support-avatar">{initials(ticket["user_name"])}</div>
        <div class="ticket-profile-name">{esc(ticket["user_name"] or "کاربر")}</div>
        <div class="ticket-profile-email">{esc(ticket["user_email"] or "—")}</div>
      </div>

      <div class="ticket-info">
        <div class="ticket-info-row">
          <span class="ticket-info-label">دسته‌بندی</span>
          <span class="ticket-info-value">{esc(category_title(ticket["category"]))}</span>
        </div>
        <div class="ticket-info-row">
          <span class="ticket-info-label">وضعیت</span>
          <span class="ticket-info-value">{esc(status_title(ticket_status))}</span>
        </div>
        <div class="ticket-info-row">
          <span class="ticket-info-label">آخرین تغییر</span>
          <span class="ticket-info-value">{relative_time(ticket["updated_at"])}</span>
        </div>
        <div class="ticket-info-row">
          <span class="ticket-info-label">پیام‌های گفتگو</span>
          <span class="ticket-info-value">{len(messages)}</span>
        </div>
      </div>

      <div class="ticket-actions">
        <form method="post" action="/admin/support/{esc(ticket_id)}/status">
          <input type="hidden" name="status" value="{'open' if is_closed else 'closed'}">
          <button
            class="btn {'btn-secondary' if is_closed else 'btn-danger'}"
            type="submit"
          >
            {'بازکردن دوباره تیکت' if is_closed else 'بستن تیکت'}
          </button>
        </form>

        <a class="btn btn-secondary" href="/admin/support">
          بازگشت به فهرست
        </a>
      </div>
    </section>
  </aside>
</div>
"""

    return HTMLResponse(
        page_layout(
            f"پشتیبانی: {ticket['subject']}",
            body,
        )
    )


@router.post(
    "/{ticket_id}/reply"
)
async def reply_ticket(
    ticket_id: str,
    request: Request,
):
    redirect = require_auth(request)
    if redirect:
        return redirect

    form = await read_form(request)
    message = form.get("message", "").strip()

    if message:
        now = utc_now_text()

        with database() as connection:
            connection.execute(
                """
                INSERT INTO support_messages (
                    id,
                    ticket_id,
                    sender_type,
                    sender_id,
                    message,
                    attachment_url,
                    created_at
                )
                VALUES (?, ?, 'admin', 'admin', ?, NULL, ?)
                """,
                (
                    str(uuid.uuid4()),
                    ticket_id,
                    message,
                    now,
                ),
            )

            connection.execute(
                """
                UPDATE support_tickets
                SET status = 'answered',
                    user_unread_count = user_unread_count + 1,
                    admin_unread_count = 0,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    now,
                    ticket_id,
                ),
            )

    return RedirectResponse(
        url=f"/admin/support/{ticket_id}",
        status_code=303,
    )


@router.post(
    "/{ticket_id}/status"
)
async def update_status(
    ticket_id: str,
    request: Request,
):
    redirect = require_auth(request)
    if redirect:
        return redirect

    form = await read_form(request)
    status = form.get("status", "open").strip()

    if status not in {"open", "answered", "closed"}:
        status = "open"

    with database() as connection:
        connection.execute(
            """
            UPDATE support_tickets
            SET status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                utc_now_text(),
                ticket_id,
            ),
        )

    return RedirectResponse(
        url=f"/admin/support/{ticket_id}",
        status_code=303,
    )

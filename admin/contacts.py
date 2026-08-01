from __future__ import annotations
from .common import *  # noqa: F401,F403
from landing import ensure_landing_tables

router = APIRouter(prefix="/admin")

@router.get("/contact-messages", response_class=HTMLResponse)
async def contact_messages(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect
    status_filter = (request.query_params.get("status") or "").strip()
    with database() as connection:
        ensure_landing_tables(connection)
        if status_filter in {"new", "read", "closed"}:
            rows = connection.execute("SELECT * FROM landing_contact_messages WHERE status=? ORDER BY id DESC LIMIT 300", (status_filter,)).fetchall()
        else:
            rows = connection.execute("SELECT * FROM landing_contact_messages ORDER BY id DESC LIMIT 300").fetchall()
        counts = {row["status"]: row["n"] for row in connection.execute("SELECT status,COUNT(*) n FROM landing_contact_messages GROUP BY status").fetchall()}
    cards = ""
    for row in rows:
        status_labels = {"new": "جدید", "read": "خوانده‌شده", "closed": "بسته‌شده"}
        badge = {"new":"badge-active", "read":"badge-pro", "closed":"badge-free"}.get(row["status"], "badge-free")
        status_label = status_labels.get(row["status"], "نامشخص")
        cards += f'''<article class="card" style="margin-bottom:12px"><div class="section-title"><div><h3>{esc(row['subject'] or 'پیام بدون موضوع')}</h3><div class="section-sub">{esc(row['name'])} · {esc(row['contact'])} · {esc(row['created_at'])}</div></div><span class="badge {badge}">{esc(status_label)}</span></div><p style="white-space:pre-wrap">{esc(row['message'])}</p><div class="actions"><form method="post" action="/admin/contact-messages/{row['id']}/status"><input type="hidden" name="status" value="read"><button class="btn btn-secondary btn-small">خوانده شد</button></form><form method="post" action="/admin/contact-messages/{row['id']}/status"><input type="hidden" name="status" value="closed"><button class="btn btn-primary btn-small">بستن پیام</button></form><form method="post" action="/admin/contact-messages/{row['id']}/delete" onsubmit="return confirm('پیام حذف شود؟')"><button class="btn btn-danger btn-small">حذف</button></form></div></article>'''
    body = f'''<div class="filters" style="margin-bottom:15px"><a class="filter-link" href="/admin/contact-messages">همه</a><a class="filter-link" href="?status=new">جدید ({counts.get('new',0)})</a><a class="filter-link" href="?status=read">خوانده‌شده ({counts.get('read',0)})</a><a class="filter-link" href="?status=closed">بسته‌شده ({counts.get('closed',0)})</a></div>{cards or '<div class="card empty-state">هنوز پیامی ثبت نشده است.</div>'}'''
    return HTMLResponse(page_layout("پیام‌های تماس سایت", body))

@router.post("/contact-messages/{message_id}/status")
async def update_message_status(request: Request, message_id: int):
    redirect = require_auth(request)
    if redirect:
        return redirect
    form = await read_form(request)
    status = form.get("status") if form.get("status") in {"new", "read", "closed"} else "read"
    with database() as connection:
        connection.execute("UPDATE landing_contact_messages SET status=?,updated_at=? WHERE id=?", (status,isoformat(utc_now()),message_id))
    return RedirectResponse("/admin/contact-messages", status_code=303)

@router.post("/contact-messages/{message_id}/delete")
async def delete_message(request: Request, message_id: int):
    redirect = require_auth(request)
    if redirect:
        return redirect
    with database() as connection:
        connection.execute("DELETE FROM landing_contact_messages WHERE id=?", (message_id,))
    return RedirectResponse("/admin/contact-messages", status_code=303)

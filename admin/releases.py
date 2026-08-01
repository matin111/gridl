from __future__ import annotations

import json
from urllib.parse import quote

from .common import *  # noqa: F401,F403

router = APIRouter(prefix="/admin")


def _ensure_release_table(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS app_releases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_name TEXT NOT NULL,
            version_code INTEGER NOT NULL UNIQUE,
            minimum_version_code INTEGER NOT NULL DEFAULT 1,
            title TEXT NOT NULL DEFAULT 'نسخه جدید رشدیار منتشر شد',
            message TEXT NOT NULL DEFAULT '',
            release_notes TEXT NOT NULL DEFAULT '[]',
            button_text TEXT NOT NULL DEFAULT 'به‌روزرسانی',
            download_url TEXT,
            force_update INTEGER NOT NULL DEFAULT 0,
            show_update INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            published_at TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_app_releases_status_code
        ON app_releases(status, version_code DESC)
        """
    )


def _release_styles() -> str:
    return """
<style>
.release-page{display:grid;gap:16px}
.release-hero{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
.release-hero h2{margin:0 0 6px;font-size:23px;color:#171725}
.release-hero p{margin:0;color:#77778e;line-height:1.75;font-size:12px}
.release-actions{display:flex;gap:9px;flex-wrap:wrap}
.release-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.release-stat{padding:14px 15px;border:1px solid #e9e5f5;border-radius:16px;background:linear-gradient(180deg,#fff,#fbfaff)}
.release-stat span{display:block;color:#8a8498;font-size:10px;margin-bottom:6px}
.release-stat strong{display:block;color:#2b2639;font-size:17px;word-break:break-word}
.release-layout{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(300px,.65fr);gap:16px;align-items:start}
.release-form{display:grid;gap:13px}
.release-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px}
.release-field{display:grid;gap:6px}
.release-field.full{grid-column:1/-1}
.release-field label{font-size:11px;font-weight:900;color:#3e384b}
.release-field input,.release-field textarea,.release-field select{margin:0;min-height:42px;padding:10px 12px;border-radius:12px}
.release-field textarea{resize:vertical;line-height:1.75}
.release-switches{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.release-switch{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px;border:1px solid #ece8f7;border-radius:14px;background:#faf9ff}
.release-switch strong{display:block;font-size:11px;color:#332e41}
.release-switch span span{display:block;margin-top:3px;font-size:10px;color:#878194;line-height:1.55}
.release-side{display:grid;gap:12px}
.release-side-card{padding:15px;border:1px solid #e9e5f5;border-radius:16px;background:#fff}
.release-side-card h4{margin:0 0 10px;font-size:13px;color:#2d283c}
.release-side-card p{margin:0;color:#817b91;font-size:11px;line-height:1.8}
.release-checklist{display:grid;gap:8px;margin-top:10px}
.release-check{display:flex;gap:8px;align-items:flex-start;font-size:11px;color:#575064}
.release-dot{width:8px;height:8px;border-radius:50%;background:#6c3cff;margin-top:5px;flex:0 0 auto}
.release-submit{display:flex;gap:9px;flex-wrap:wrap;align-items:center}
.release-submit .btn{min-width:145px}
.release-help{padding:11px 13px;border-radius:13px;background:#f5f1ff;border:1px solid #e1d8ff;color:#6245c3;font-size:11px;line-height:1.8}
.release-table-wrap{overflow-x:auto}
.release-table{width:100%;border-collapse:separate;border-spacing:0 8px;min-width:980px}
.release-table th{padding:0 10px 7px;text-align:right;color:#817b91;font-size:10px}
.release-table td{padding:11px 10px;background:#fff;border-top:1px solid #ece8f7;border-bottom:1px solid #ece8f7;font-size:11px;vertical-align:middle}
.release-table td:first-child{border-right:1px solid #ece8f7;border-radius:0 12px 12px 0}
.release-table td:last-child{border-left:1px solid #ece8f7;border-radius:12px 0 0 12px}
.release-status{display:inline-flex;padding:5px 8px;border-radius:999px;font-size:10px;font-weight:900;white-space:nowrap}
.release-status.published{background:#e8f8f0;color:#12815a}.release-status.draft{background:#f1eff8;color:#6e6583}.release-status.archived{background:#fff1e7;color:#a35c21}
.release-buttons{display:flex;gap:6px;flex-wrap:wrap}.release-buttons form{margin:0}
.release-mini{border:1px solid #ded8f0;background:#fff;color:#5d46b6;border-radius:9px;padding:6px 9px;font-size:10px;font-weight:850;cursor:pointer}
.release-mini.primary{background:#6c3cff;color:#fff;border-color:#6c3cff}.release-mini.warn{color:#9b571c;border-color:#f1cda9}.release-mini.danger{color:#b42335;border-color:#f2bdc4}
.release-alert{padding:12px 14px;border-radius:14px;border:1px solid;font-size:11px;line-height:1.8}.release-alert.success{background:#ecfbf4;border-color:#bdebd5;color:#0f7a52}.release-alert.error{background:#fff0f1;border-color:#ffc9ce;color:#b42335}
@media(max-width:1080px){.release-layout{grid-template-columns:1fr}.release-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:720px){.release-form-grid,.release-switches,.release-grid{grid-template-columns:1fr}.release-field.full{grid-column:auto}.release-actions{width:100%}.release-actions a{flex:1;text-align:center}.release-submit{display:grid}.release-submit .btn{width:100%}}
</style>
"""


def _flash(request: Request) -> str:
    status = (request.query_params.get("status") or "").strip().lower()
    message = (request.query_params.get("message") or "").strip()
    if status not in {"success", "error"} or not message:
        return ""
    return f'<div class="release-alert {status}">{esc(message)}</div>'


def _notes_from_form(value: str) -> list[str]:
    notes: list[str] = []
    for line in value.replace("\r", "").split("\n"):
        cleaned = line.strip().lstrip("-•").strip()
        if cleaned and cleaned not in notes:
            notes.append(cleaned)
    return notes


def _read_notes(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return _notes_from_form(str(raw))


def _upsert_settings(connection, values: dict[str, str], now: str) -> None:
    for key, value in values.items():
        connection.execute(
            """
            INSERT INTO app_settings(key, value, updated_at)
            VALUES(?, ?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (key, value, now),
        )


def _publish_release(connection, release_id: int) -> dict:
    _ensure_release_table(connection)
    row = connection.execute(
        "SELECT * FROM app_releases WHERE id = ?",
        (release_id,),
    ).fetchone()
    if row is None:
        raise ValueError("نسخه موردنظر پیدا نشد.")

    release = dict(row)
    if not (release.get("download_url") or "").strip():
        raise ValueError("برای انتشار، لینک دانلود را وارد کنید.")

    now = isoformat(utc_now())
    connection.execute(
        "UPDATE app_releases SET status='archived', updated_at=? WHERE status='published' AND id<>?",
        (now, release_id),
    )
    connection.execute(
        "UPDATE app_releases SET status='published', published_at=?, updated_at=? WHERE id=?",
        (now, now, release_id),
    )

    notes = _read_notes(release.get("release_notes"))
    settings_values = {
        "minimum_version_code": str(release["minimum_version_code"]),
        "latest_version_code": str(release["version_code"]),
        "latest_version_name": str(release["version_name"]),
        "force_update": "1" if int(release["force_update"] or 0) else "0",
        "show_update": "1" if int(release["show_update"] or 0) else "0",
        "update_title": str(release["title"] or "نسخه جدید رشدیار منتشر شد"),
        "update_message": str(release["message"] or ""),
        "release_notes": json.dumps(notes, ensure_ascii=False),
        "button_text": str(release["button_text"] or "به‌روزرسانی"),
        "download_url": str(release["download_url"] or ""),
    }
    _upsert_settings(connection, settings_values, now)
    return release


@router.get("/releases", response_class=HTMLResponse)
async def releases_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    with database() as connection:
        _ensure_release_table(connection)
        releases = connection.execute(
            "SELECT * FROM app_releases ORDER BY version_code DESC, id DESC"
        ).fetchall()
        published = connection.execute(
            "SELECT * FROM app_releases WHERE status='published' ORDER BY version_code DESC LIMIT 1"
        ).fetchone()

    published_code = published["version_code"] if published else "—"
    published_name = published["version_name"] if published else "—"
    total_count = len(releases)
    draft_count = sum(1 for row in releases if row["status"] == "draft")

    rows_html = ""
    for row in releases:
        release_id = int(row["id"])
        status = row["status"] or "draft"
        status_text = {"published": "منتشرشده", "draft": "پیش‌نویس", "archived": "آرشیو"}.get(status, status)
        type_text = "اجباری" if int(row["force_update"] or 0) else "اختیاری"
        notes_count = len(_read_notes(row["release_notes"]))
        buttons = []
        if status != "published":
            buttons.append(f"""
            <form method="post" action="/admin/releases/{release_id}/publish" onsubmit="return confirm('این نسخه منتشر شود؟')">
              <button class="release-mini primary" type="submit">انتشار</button>
            </form>
            """)
        if status == "published":
            buttons.append(f"""
            <form method="post" action="/admin/releases/{release_id}/archive" onsubmit="return confirm('انتشار این نسخه متوقف شود؟')">
              <button class="release-mini warn" type="submit">توقف انتشار</button>
            </form>
            """)
        if status == "archived":
            buttons.append(f"""
            <form method="post" action="/admin/releases/{release_id}/rollback" onsubmit="return confirm('این نسخه دوباره به‌عنوان نسخه فعال منتشر شود؟')">
              <button class="release-mini" type="submit">Rollback</button>
            </form>
            """)
        if status == "draft":
            buttons.append(f"""
            <form method="post" action="/admin/releases/{release_id}/delete" onsubmit="return confirm('این پیش‌نویس حذف شود؟')">
              <button class="release-mini danger" type="submit">حذف</button>
            </form>
            """)

        rows_html += f"""
        <tr>
          <td><strong>{esc(row['version_name'])}</strong><br><small>Code {row['version_code']}</small></td>
          <td>{row['minimum_version_code']}</td>
          <td>{esc(type_text)}</td>
          <td><span class="release-status {esc(status)}">{esc(status_text)}</span></td>
          <td>{notes_count} مورد</td>
          <td>{esc(row['published_at'] or row['created_at'] or '—')}</td>
          <td><div class="release-buttons">{''.join(buttons)}</div></td>
        </tr>
        """

    if not rows_html:
        rows_html = '<tr><td colspan="7" style="text-align:center;color:#888;padding:24px">هنوز نسخه‌ای ثبت نشده است.</td></tr>'

    body = f"""
{_release_styles()}
<div class="release-page">
  {_flash(request)}
  <section class="card">
    <div class="release-hero">
      <div>
        <h2>Release Center</h2>
        <p>نسخه‌ها را به‌صورت پیش‌نویس ثبت کنید، بررسی کنید و سپس روی اپ منتشر کنید.</p>
      </div>
      <div class="release-actions">
        <a class="btn" href="/admin/settings">تنظیمات نسخه</a>
        <a class="btn btn-primary" href="#newRelease">نسخه جدید</a>
      </div>
    </div>
  </section>

  <div class="release-grid">
    <div class="release-stat"><span>نسخه فعال</span><strong>{esc(published_name)}</strong></div>
    <div class="release-stat"><span>Version Code فعال</span><strong>{esc(published_code)}</strong></div>
    <div class="release-stat"><span>کل نسخه‌ها</span><strong>{total_count}</strong></div>
    <div class="release-stat"><span>پیش‌نویس‌ها</span><strong>{draft_count}</strong></div>
  </div>

  <div class="release-layout" id="newRelease">
    <section class="card">
      <h3 style="margin:0 0 14px">ساخت نسخه جدید</h3>
      <form class="release-form" method="post" action="/admin/releases/create">
        <div class="release-form-grid">
          <div class="release-field"><label>Version Name</label><input name="version_name" placeholder="1.1.0" required></div>
          <div class="release-field"><label>Version Code</label><input type="number" min="1" name="version_code" required></div>
          <div class="release-field"><label>حداقل Version Code</label><input type="number" min="1" name="minimum_version_code" value="1" required></div>
          <div class="release-field"><label>متن دکمه</label><input name="button_text" value="به‌روزرسانی"></div>
          <div class="release-field full"><label>عنوان بروزرسانی</label><input name="title" value="نسخه جدید رشدیار منتشر شد"></div>
          <div class="release-field full"><label>پیام بروزرسانی</label><textarea name="message" rows="2" placeholder="نسخه جدید رشدیار با امکانات بهتر منتشر شده است."></textarea></div>
          <div class="release-field full"><label>Release Notes — هر مورد در یک خط</label><textarea name="release_notes" rows="4" placeholder="افزایش سرعت برنامه&#10;رفع مشکلات گزارش‌شده&#10;بهبود تحلیل پیج"></textarea></div>
          <div class="release-field full"><label>لینک دانلود مستقیم APK</label><input type="url" name="download_url" placeholder="https://example.com/app-release.apk"></div>
        </div>
        <div class="release-switches">
          <label class="release-switch"><span><strong>بروزرسانی اجباری</strong><span>کاربر نسخه قدیمی امکان بستن پنجره را ندارد.</span></span><input type="checkbox" name="force_update" value="1"></label>
          <label class="release-switch"><span><strong>نمایش بروزرسانی</strong><span>اعلان نسخه جدید در اپ نمایش داده شود.</span></span><input type="checkbox" name="show_update" value="1" checked></label>
        </div>
        <div class="release-help">«ذخیره پیش‌نویس» فقط اطلاعات را ثبت می‌کند. «ذخیره و انتشار» همان لحظه نسخه را فعال می‌کند.</div>
        <div class="release-submit">
          <button class="btn" type="submit" name="submit_action" value="draft">ذخیره پیش‌نویس</button>
          <button class="btn btn-primary" type="submit" name="submit_action" value="publish" onclick="return confirm('این نسخه همین حالا منتشر شود؟')">ذخیره و انتشار</button>
        </div>
      </form>
    </section>

    <aside class="release-side">
      <div class="release-side-card">
        <h4>چک‌لیست انتشار</h4>
        <p>قبل از انتشار نهایی این موارد را بررسی کنید.</p>
        <div class="release-checklist">
          <div class="release-check"><span class="release-dot"></span><span>Version Code از نسخه قبلی بزرگ‌تر باشد.</span></div>
          <div class="release-check"><span class="release-dot"></span><span>لینک دانلود مستقیم و قابل دسترس باشد.</span></div>
          <div class="release-check"><span class="release-dot"></span><span>Release Notes کوتاه و دقیق نوشته شود.</span></div>
          <div class="release-check"><span class="release-dot"></span><span>آپدیت اجباری فقط هنگام ضرورت فعال شود.</span></div>
        </div>
      </div>
      <div class="release-side-card">
        <h4>وضعیت فعلی</h4>
        <p>نسخه فعال: <strong>{esc(published_name)}</strong><br>Version Code: <strong>{esc(published_code)}</strong><br>کل نسخه‌ها: <strong>{total_count}</strong></p>
      </div>
    </aside>
  </div>

  <section class="card">
    <h3 style="margin:0 0 12px">تاریخچه نسخه‌ها</h3>
    <div class="release-table-wrap">
      <table class="release-table">
        <thead><tr><th>نسخه</th><th>حداقل نسخه</th><th>نوع</th><th>وضعیت</th><th>یادداشت‌ها</th><th>زمان</th><th>عملیات</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
  </section>
</div>
"""
    return HTMLResponse(page_layout("مرکز انتشار", body))


@router.post("/releases/create")
async def create_release(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    try:
        form = await read_form(request)
        version_name = (form.get("version_name") or "").strip()
        title = (form.get("title") or "نسخه جدید رشدیار منتشر شد").strip()
        message = (form.get("message") or "").strip()
        button_text = (form.get("button_text") or "به‌روزرسانی").strip()
        download_url = (form.get("download_url") or "").strip()
        version_code = int(form.get("version_code") or 0)
        minimum_version_code = int(form.get("minimum_version_code") or 0)
        notes = _notes_from_form(form.get("release_notes") or "")

        if not version_name:
            raise ValueError("Version Name الزامی است.")
        if version_code < 1 or minimum_version_code < 1:
            raise ValueError("Version Code باید بزرگ‌تر از صفر باشد.")
        if minimum_version_code > version_code:
            raise ValueError("حداقل Version Code نمی‌تواند از Version Code نسخه جدید بیشتر باشد.")
        if download_url and not download_url.startswith(("https://", "http://")):
            raise ValueError("لینک دانلود باید با http یا https شروع شود.")

        submit_action = (form.get("submit_action") or "draft").strip().lower()
        if submit_action == "publish" and not download_url:
            raise ValueError("برای انتشار فوری، لینک دانلود مستقیم الزامی است.")

        now = isoformat(utc_now())
        with database() as connection:
            _ensure_release_table(connection)
            cursor = connection.execute(
                """
                INSERT INTO app_releases(
                    version_name, version_code, minimum_version_code,
                    title, message, release_notes, button_text, download_url,
                    force_update, show_update, status, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)
                """,
                (
                    version_name,
                    version_code,
                    minimum_version_code,
                    title,
                    message,
                    json.dumps(notes, ensure_ascii=False),
                    button_text,
                    download_url,
                    1 if form.get("force_update") == "1" else 0,
                    1 if form.get("show_update") == "1" else 0,
                    now,
                    now,
                ),
            )
            release_id = int(cursor.lastrowid)
            if submit_action == "publish":
                _publish_release(connection, release_id)

        success_message = (
            "نسخه جدید ذخیره و با موفقیت منتشر شد."
            if submit_action == "publish"
            else "نسخه جدید به‌صورت پیش‌نویس ذخیره شد."
        )
        return RedirectResponse(
            url=f"/admin/releases?status=success&message={quote(success_message)}",
            status_code=303,
        )
    except Exception as exc:
        message = "این Version Code قبلاً ثبت شده است." if "UNIQUE constraint" in str(exc) else str(exc)
        return RedirectResponse(
            url=f"/admin/releases?status=error&message={quote(message)}",
            status_code=303,
        )


@router.post("/releases/{release_id}/publish")
async def publish_release(request: Request, release_id: int):
    redirect = require_auth(request)
    if redirect:
        return redirect
    try:
        with database() as connection:
            release = _publish_release(connection, release_id)
        message = f"نسخه {release['version_name']} با موفقیت منتشر شد و اکنون از API اپ قابل دریافت است."
        return RedirectResponse(url=f"/admin/releases?status=success&message={quote(message)}", status_code=303)
    except Exception as exc:
        return RedirectResponse(url=f"/admin/releases?status=error&message={quote(str(exc))}", status_code=303)


@router.post("/releases/{release_id}/rollback")
async def rollback_release(request: Request, release_id: int):
    redirect = require_auth(request)
    if redirect:
        return redirect
    try:
        with database() as connection:
            release = _publish_release(connection, release_id)
        message = f"Rollback انجام شد؛ نسخه {release['version_name']} دوباره فعال است."
        return RedirectResponse(url=f"/admin/releases?status=success&message={quote(message)}", status_code=303)
    except Exception as exc:
        return RedirectResponse(url=f"/admin/releases?status=error&message={quote(str(exc))}", status_code=303)


@router.post("/releases/{release_id}/archive")
async def archive_release(request: Request, release_id: int):
    redirect = require_auth(request)
    if redirect:
        return redirect
    try:
        now = isoformat(utc_now())
        with database() as connection:
            _ensure_release_table(connection)
            row = connection.execute("SELECT id FROM app_releases WHERE id=?", (release_id,)).fetchone()
            if row is None:
                raise ValueError("نسخه موردنظر پیدا نشد.")
            connection.execute("UPDATE app_releases SET status='archived', updated_at=? WHERE id=?", (now, release_id))
            _upsert_settings(connection, {"show_update": "0"}, now)
        return RedirectResponse(url=f"/admin/releases?status=success&message={quote('انتشار متوقف شد و پنجره بروزرسانی در اپ غیرفعال شد.')}", status_code=303)
    except Exception as exc:
        return RedirectResponse(url=f"/admin/releases?status=error&message={quote(str(exc))}", status_code=303)


@router.post("/releases/{release_id}/delete")
async def delete_release(request: Request, release_id: int):
    redirect = require_auth(request)
    if redirect:
        return redirect
    try:
        with database() as connection:
            _ensure_release_table(connection)
            row = connection.execute("SELECT status FROM app_releases WHERE id=?", (release_id,)).fetchone()
            if row is None:
                raise ValueError("نسخه موردنظر پیدا نشد.")
            if row["status"] != "draft":
                raise ValueError("فقط نسخه‌های پیش‌نویس قابل حذف هستند.")
            connection.execute("DELETE FROM app_releases WHERE id=?", (release_id,))
        return RedirectResponse(url=f"/admin/releases?status=success&message={quote('پیش‌نویس حذف شد.')}", status_code=303)
    except Exception as exc:
        return RedirectResponse(url=f"/admin/releases?status=error&message={quote(str(exc))}", status_code=303)

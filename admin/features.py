from __future__ import annotations

from .common import *  # noqa: F401,F403

router = APIRouter(prefix="/admin")


def _feature_styles() -> str:
    return """
<style>
.feature-page{
  display:grid;
  gap:18px;
}
.feature-hero{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:18px;
  flex-wrap:wrap;
}
.feature-hero h2{
  margin:0 0 8px;
  font-size:23px;
  color:#171725;
}
.feature-hero p{
  margin:0;
  color:#77778e;
  line-height:1.9;
}
.feature-summary{
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:14px;
}
.feature-summary-card{
  padding:18px;
  border:1px solid #e7e4f5;
  border-radius:20px;
  background:linear-gradient(145deg,#fff,#fbfaff);
}
.feature-summary-label{
  color:#77778e;
  font-size:12px;
  font-weight:800;
}
.feature-summary-value{
  margin-top:9px;
  color:#171725;
  font-size:28px;
  font-weight:950;
}
.feature-grid{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:16px;
}
.feature-card{
  position:relative;
  overflow:hidden;
  border:1px solid #e7e4f5;
  border-radius:22px;
  background:#fff;
  box-shadow:0 8px 24px rgba(65,49,120,.06);
}
.feature-card:before{
  content:"";
  position:absolute;
  inset:0 auto 0 0;
  width:4px;
  background:#6c3cff;
}
.feature-card.is-off:before{
  background:#a3a0ad;
}
.feature-card-head{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:14px;
  padding:20px 20px 14px;
}
.feature-title{
  margin:0;
  font-size:18px;
  font-weight:950;
  color:#242032;
}
.feature-key{
  margin-top:7px;
  display:inline-flex;
  align-items:center;
  padding:6px 9px;
  border-radius:9px;
  background:#f5f3fb;
  color:#6d6780;
  direction:ltr;
  font-size:11px;
  font-weight:800;
}
.feature-status{
  display:inline-flex;
  align-items:center;
  gap:7px;
  padding:7px 10px;
  border-radius:999px;
  font-size:12px;
  font-weight:900;
  white-space:nowrap;
}
.feature-status:before{
  content:"";
  width:7px;
  height:7px;
  border-radius:50%;
  background:currentColor;
}
.feature-status.on{
  color:#12805d;
  background:#e7f8f0;
}
.feature-status.off{
  color:#6d6a78;
  background:#efeff3;
}
.feature-form{
  padding:0 20px 20px;
}
.feature-options{
  display:grid;
  gap:10px;
  margin:4px 0 16px;
}
.feature-option{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:14px;
  padding:12px 14px;
  border:1px solid #ece9f7;
  border-radius:15px;
  background:#faf9ff;
}
.feature-option-text strong{
  display:block;
  color:#2d283c;
  font-size:13px;
}
.feature-option-text span{
  display:block;
  margin-top:4px;
  color:#858096;
  font-size:11px;
  line-height:1.7;
}
.switch{
  position:relative;
  display:inline-block;
  width:48px;
  height:28px;
  flex:0 0 auto;
}
.switch input{
  opacity:0;
  width:0;
  height:0;
}
.slider{
  position:absolute;
  cursor:pointer;
  inset:0;
  background:#d9d6e2;
  transition:.2s;
  border-radius:999px;
}
.slider:before{
  content:"";
  position:absolute;
  width:20px;
  height:20px;
  right:4px;
  bottom:4px;
  border-radius:50%;
  background:#fff;
  box-shadow:0 2px 6px rgba(0,0,0,.18);
  transition:.2s;
}
.switch input:checked + .slider{
  background:#6c3cff;
}
.switch input:checked + .slider:before{
  transform:translateX(-20px);
}
.feature-message{
  display:grid;
  gap:8px;
}
.feature-message label{
  color:#403a50;
  font-size:12px;
  font-weight:850;
}
.feature-message input{
  margin:0;
}
.feature-message small{
  color:#8a8aa3;
  line-height:1.7;
}
.feature-save{
  display:flex;
  justify-content:flex-end;
  margin-top:16px;
}
.feature-save button{
  min-width:120px;
}
.feature-empty{
  grid-column:1/-1;
  text-align:center;
  padding:44px 20px;
  color:#77778e;
}
@media(max-width:980px){
  .feature-grid{grid-template-columns:1fr;}
}
@media(max-width:720px){
  .feature-summary{grid-template-columns:1fr;}
}
</style>
"""


@router.get("/features", response_class=HTMLResponse)
async def features_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    with database() as connection:
        rows = connection.execute(
            "SELECT * FROM feature_flags ORDER BY title"
        ).fetchall()

    total_count = len(rows)
    enabled_count = sum(1 for row in rows if row["enabled"])
    premium_count = sum(1 for row in rows if row["premium_only"])

    cards = []

    for row in rows:
        enabled = bool(row["enabled"])
        premium_only = bool(row["premium_only"])

        cards.append(
            f"""
<section class="feature-card {'is-off' if not enabled else ''}">
  <div class="feature-card-head">
    <div>
      <h3 class="feature-title">{esc(row['title'])}</h3>
      <span class="feature-key">{esc(row['feature_key'])}</span>
    </div>
    <span class="feature-status {'on' if enabled else 'off'}">
      {'فعال' if enabled else 'غیرفعال'}
    </span>
  </div>

  <form class="feature-form" method="post" action="/admin/features/update">
    <input type="hidden" name="feature_key" value="{esc(row['feature_key'])}">

    <div class="feature-options">
      <div class="feature-option">
        <div class="feature-option-text">
          <strong>فعال بودن قابلیت</strong>
          <span>در صورت خاموش بودن، این بخش برای همه کاربران غیرفعال می‌شود.</span>
        </div>
        <label class="switch">
          <input
            type="checkbox"
            name="enabled"
            value="1"
            {'checked' if enabled else ''}
          >
          <span class="slider"></span>
        </label>
      </div>

      <div class="feature-option">
        <div class="feature-option-text">
          <strong>فقط کاربران حرفه‌ای</strong>
          <span>این قابلیت فقط برای کاربران دارای اشتراک حرفه‌ای نمایش داده شود.</span>
        </div>
        <label class="switch">
          <input
            type="checkbox"
            name="premium_only"
            value="1"
            {'checked' if premium_only else ''}
          >
          <span class="slider"></span>
        </label>
      </div>
    </div>

    <div class="feature-message">
      <label>پیام اختصاصی قابلیت</label>
      <input
        name="message"
        value="{esc(row['message'] or '')}"
        placeholder="مثلاً: این قابلیت به‌زودی فعال می‌شود."
      >
      <small>در صورت نیاز، این پیام برای کاربر نمایش داده می‌شود.</small>
    </div>

    <div class="feature-save">
      <button class="btn btn-primary" type="submit">ذخیره تغییرات</button>
    </div>
  </form>
</section>
"""
        )

    body = f"""
{_feature_styles()}
<div class="feature-page">
  <section class="card">
    <div class="feature-hero">
      <div>
        <h2>کنترل قابلیت‌های اپلیکیشن</h2>
        <p>
          هر قابلیت را بدون انتشار نسخه جدید فعال، غیرفعال یا فقط برای کاربران حرفه‌ای در دسترس قرار دهید.
        </p>
      </div>
      <span class="badge badge-pro">مدیریت زنده قابلیت‌ها</span>
    </div>
  </section>

  <div class="feature-summary">
    <section class="feature-summary-card">
      <div class="feature-summary-label">کل قابلیت‌ها</div>
      <div class="feature-summary-value">{total_count}</div>
    </section>
    <section class="feature-summary-card">
      <div class="feature-summary-label">قابلیت‌های فعال</div>
      <div class="feature-summary-value">{enabled_count}</div>
    </section>
    <section class="feature-summary-card">
      <div class="feature-summary-label">فقط حرفه‌ای</div>
      <div class="feature-summary-value">{premium_count}</div>
    </section>
  </div>

  <div class="feature-grid">
    {''.join(cards) if cards else '<section class="card feature-empty">قابلیتی ثبت نشده است.</section>'}
  </div>
</div>
"""

    return HTMLResponse(
        page_layout(
            "مدیریت قابلیت‌ها",
            body,
        )
    )


@router.post("/features/update")
async def update_feature(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    form = await read_form(request)
    key = form.get("feature_key", "").strip()

    with database() as connection:
        connection.execute(
            """
            UPDATE feature_flags
            SET enabled=?,
                premium_only=?,
                message=?,
                updated_at=?
            WHERE feature_key=?
            """,
            (
                1 if form.get("enabled") == "1" else 0,
                1 if form.get("premium_only") == "1" else 0,
                form.get("message", "") or None,
                isoformat(utc_now()),
                key,
            ),
        )

    return RedirectResponse(
        url="/admin/features",
        status_code=303,
    )

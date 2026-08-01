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
    "dashboard": "داشبورد",
}

SUCCESS_TYPES = {"use", "success", "generated", "complete", "completed"}
ERROR_TYPES = {"error", "failed", "failure"}


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _analytics_styles() -> str:
    return """
<style>
.analytics-page{
  display:grid;
  gap:18px;
}
.analytics-header{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:18px;
  flex-wrap:wrap;
}
.analytics-title h2{
  margin:0 0 7px;
  color:#171725;
  font-size:23px;
}
.analytics-title p{
  margin:0;
  color:#77778e;
  line-height:1.8;
}
.analytics-filters{
  display:flex;
  gap:8px;
  flex-wrap:wrap;
}
.analytics-filter{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-height:40px;
  padding:0 14px;
  border:1px solid #e7e4f5;
  border-radius:12px;
  color:#5f596f;
  background:#fff;
  text-decoration:none;
  font-size:12px;
  font-weight:850;
}
.analytics-filter.active{
  background:#6c3cff;
  color:#fff;
  border-color:#6c3cff;
  box-shadow:0 8px 20px rgba(108,60,255,.18);
}
.analytics-kpis{
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:14px;
}
.analytics-kpi{
  position:relative;
  overflow:hidden;
  min-height:125px;
  padding:18px;
  border:1px solid #e7e4f5;
  border-radius:20px;
  background:linear-gradient(145deg,#fff,#fbfaff);
  box-shadow:0 7px 22px rgba(65,49,120,.05);
}
.analytics-kpi:after{
  content:"";
  position:absolute;
  width:90px;
  height:90px;
  left:-35px;
  bottom:-40px;
  border-radius:50%;
  background:rgba(108,60,255,.06);
}
.analytics-kpi-label{
  display:flex;
  align-items:center;
  gap:8px;
  color:#77778e;
  font-size:12px;
  font-weight:850;
}
.analytics-kpi-value{
  margin-top:12px;
  font-size:30px;
  line-height:1;
  color:#171725;
  font-weight:950;
}
.analytics-kpi-note{
  margin-top:12px;
  color:#817b91;
  font-size:11px;
}
.analytics-kpi-note.good{
  color:#11875d;
}
.analytics-grid{
  display:grid;
  grid-template-columns:minmax(0,1.7fr) minmax(280px,.9fr);
  gap:16px;
}
.analytics-card{
  border:1px solid #e7e4f5;
  border-radius:22px;
  background:#fff;
  padding:20px;
  box-shadow:0 8px 24px rgba(65,49,120,.05);
}
.analytics-card-head{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:14px;
  margin-bottom:18px;
}
.analytics-card-title{
  margin:0;
  font-size:18px;
  font-weight:950;
  color:#282438;
}
.analytics-card-sub{
  margin-top:6px;
  color:#817b91;
  font-size:11px;
}
.analytics-chart{
  display:flex;
  align-items:flex-end;
  gap:14px;
  height:260px;
  padding:22px 10px 8px;
  border-radius:18px;
  background:
    repeating-linear-gradient(
      to top,
      #f1eef8 0,
      #f1eef8 1px,
      transparent 1px,
      transparent 52px
    );
  overflow-x:auto;
}
.analytics-chart-col{
  min-width:54px;
  height:100%;
  display:flex;
  flex-direction:column;
  justify-content:flex-end;
  align-items:center;
  gap:8px;
}
.analytics-chart-value{
  font-size:10px;
  color:#6c3cff;
  font-weight:900;
}
.analytics-chart-bar{
  width:18px;
  min-height:6px;
  border-radius:999px 999px 5px 5px;
  background:linear-gradient(180deg,#7f56ff,#45d2a4);
  box-shadow:0 8px 18px rgba(108,60,255,.16);
}
.analytics-chart-label{
  font-size:10px;
  color:#77778e;
  direction:ltr;
}
.analytics-ranking{
  display:grid;
  gap:13px;
}
.analytics-rank-item{
  display:grid;
  gap:8px;
}
.analytics-rank-head{
  display:flex;
  justify-content:space-between;
  gap:10px;
  align-items:center;
  font-size:12px;
}
.analytics-rank-name{
  color:#322d42;
  font-weight:900;
}
.analytics-rank-value{
  color:#6c3cff;
  font-weight:950;
}
.analytics-progress{
  height:8px;
  border-radius:999px;
  overflow:hidden;
  background:#f0edf8;
}
.analytics-progress span{
  display:block;
  height:100%;
  border-radius:999px;
  background:linear-gradient(90deg,#6c3cff,#9b7cff);
}
.analytics-table-wrap{
  overflow:auto;
  border:1px solid #ece9f7;
  border-radius:18px;
}
.analytics-table{
  width:100%;
  min-width:760px;
  border-collapse:separate;
  border-spacing:0;
}
.analytics-table th{
  padding:13px 15px;
  background:#faf9ff;
  color:#77778e;
  font-size:11px;
  text-align:right;
  border-bottom:1px solid #ece9f7;
}
.analytics-table td{
  padding:14px 15px;
  border-bottom:1px solid #f0eef7;
  vertical-align:middle;
  font-size:12px;
}
.analytics-table tr:last-child td{
  border-bottom:0;
}
.analytics-feature-name{
  font-weight:900;
  color:#292438;
}
.analytics-feature-key{
  margin-top:5px;
  color:#8a8aa3;
  font-size:10px;
  direction:ltr;
}
.analytics-badge{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-width:30px;
  padding:6px 9px;
  border-radius:999px;
  font-size:11px;
  font-weight:900;
}
.analytics-badge.success{
  color:#11875d;
  background:#e7f8f0;
}
.analytics-badge.error{
  color:#b42318;
  background:#ffeceb;
}
.analytics-health{
  display:inline-flex;
  align-items:center;
  gap:7px;
  padding:6px 9px;
  border-radius:999px;
  color:#11875d;
  background:#e7f8f0;
  font-size:11px;
  font-weight:900;
}
.analytics-health.warn{
  color:#9a630e;
  background:#fff4df;
}
.campaign-grid{
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:14px;
}
.campaign-card{
  padding:17px;
  border:1px solid #e7e4f5;
  border-radius:18px;
  background:#faf9ff;
}
.campaign-title{
  color:#282438;
  font-weight:950;
  margin-bottom:14px;
}
.campaign-stats{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:10px;
}
.campaign-stat{
  padding:10px;
  border-radius:13px;
  background:#fff;
  border:1px solid #ece9f7;
}
.campaign-stat-label{
  color:#8a8aa3;
  font-size:10px;
}
.campaign-stat-value{
  margin-top:5px;
  color:#282438;
  font-size:17px;
  font-weight:950;
}
.analytics-empty{
  text-align:center;
  padding:42px 20px;
  color:#77778e;
}
@media(max-width:1100px){
  .analytics-kpis{grid-template-columns:repeat(2,minmax(0,1fr));}
  .analytics-grid{grid-template-columns:1fr;}
  .campaign-grid{grid-template-columns:repeat(2,minmax(0,1fr));}
}
@media(max-width:700px){
  .analytics-kpis{grid-template-columns:1fr;}
  .campaign-grid{grid-template-columns:1fr;}
}
</style>
"""


def _daily_chart(rows) -> str:
    if not rows:
        return '<div class="analytics-empty">داده روزانه‌ای ثبت نشده است.</div>'

    top = max([_int(row["total"]) for row in rows] + [1])

    return (
        '<div class="analytics-chart">'
        + "".join(
            f"""
<div class="analytics-chart-col" title="{_int(row['total'])} رویداد">
  <div class="analytics-chart-value">{_int(row['total'])}</div>
  <div
    class="analytics-chart-bar"
    style="height:{max(8, round(_int(row['total']) / top * 200))}px"
  ></div>
  <div class="analytics-chart-label">{esc(str(row['day'])[5:])}</div>
</div>
"""
            for row in rows
        )
        + "</div>"
    )


def _feature_ranking(rows) -> str:
    if not rows:
        return '<div class="analytics-empty">داده‌ای برای این بازه ثبت نشده است.</div>'

    top = max([_int(row["total"]) for row in rows] + [1])

    return '<div class="analytics-ranking">' + "".join(
        f"""
<div class="analytics-rank-item">
  <div class="analytics-rank-head">
    <span class="analytics-rank-name">
      {esc(FEATURE_TITLES.get(row['feature_key'], row['feature_key'] or 'نامشخص'))}
    </span>
    <span class="analytics-rank-value">{_int(row['total']):,}</span>
  </div>
  <div class="analytics-progress">
    <span style="width:{max(4, round(_int(row['total']) / top * 100))}%"></span>
  </div>
</div>
"""
        for row in rows
    ) + "</div>"


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    try:
        days = int(request.query_params.get("days", "30"))
    except ValueError:
        days = 30

    days = days if days in {7, 30, 90} else 30
    since = isoformat(utc_now() - timedelta(days=days))

    with database() as connection:
        total_users = _int(
            connection.execute(
                "SELECT COUNT(*) AS n FROM users"
            ).fetchone()["n"]
        )

        active_users = _int(
            connection.execute(
                "SELECT COUNT(*) AS n FROM users WHERE last_seen_at >= ?",
                (since,),
            ).fetchone()["n"]
        )

        new_users = _int(
            connection.execute(
                "SELECT COUNT(*) AS n FROM users WHERE created_at >= ?",
                (since,),
            ).fetchone()["n"]
        )

        total_events = _int(
            connection.execute(
                "SELECT COUNT(*) AS n FROM usage_events WHERE created_at >= ?",
                (since,),
            ).fetchone()["n"]
        )

        feature_rows = connection.execute(
            """
            SELECT
                feature_key,
                COUNT(*) AS total,
                SUM(
                    CASE
                        WHEN event_type IN (
                            'use',
                            'success',
                            'generated',
                            'complete',
                            'completed'
                        )
                        THEN 1
                        ELSE 0
                    END
                ) AS successes,
                SUM(
                    CASE
                        WHEN event_type IN (
                            'error',
                            'failed',
                            'failure'
                        )
                        THEN 1
                        ELSE 0
                    END
                ) AS errors
            FROM usage_events
            WHERE created_at >= ?
            GROUP BY feature_key
            ORDER BY total DESC
            """,
            (since,),
        ).fetchall()

        daily = connection.execute(
            """
            SELECT
                substr(created_at, 1, 10) AS day,
                COUNT(*) AS total
            FROM usage_events
            WHERE created_at >= ?
            GROUP BY substr(created_at, 1, 10)
            ORDER BY day
            """,
            (since,),
        ).fetchall()

        campaign_rows = connection.execute(
            """
            SELECT
                c.title,
                SUM(
                    CASE
                        WHEN e.event_type = 'impression'
                        THEN 1
                        ELSE 0
                    END
                ) AS impressions,
                SUM(
                    CASE
                        WHEN e.event_type = 'click'
                        THEN 1
                        ELSE 0
                    END
                ) AS clicks,
                SUM(
                    CASE
                        WHEN e.event_type = 'dismiss'
                        THEN 1
                        ELSE 0
                    END
                ) AS dismisses
            FROM campaigns c
            LEFT JOIN campaign_events e
                ON e.campaign_id = c.id
            GROUP BY c.id
            ORDER BY impressions DESC
            LIMIT 100
            """
        ).fetchall()

    all_success = sum(_int(row["successes"]) for row in feature_rows)
    all_errors = sum(_int(row["errors"]) for row in feature_rows)

    success_rate = (
        round(
            all_success / (all_success + all_errors) * 100,
            1,
        )
        if (all_success + all_errors)
        else 0
    )

    active_rate = (
        round(active_users / total_users * 100, 1)
        if total_users
        else 0
    )

    feature_table = "".join(
        f"""
<tr>
  <td>
    <div class="analytics-feature-name">
      {esc(FEATURE_TITLES.get(row['feature_key'], row['feature_key'] or 'نامشخص'))}
    </div>
    <div class="analytics-feature-key">{esc(row['feature_key'])}</div>
  </td>
  <td>{_int(row['total']):,}</td>
  <td><span class="analytics-badge success">{_int(row['successes']):,}</span></td>
  <td><span class="analytics-badge error">{_int(row['errors']):,}</span></td>
  <td>
    <span class="analytics-health {'warn' if _int(row['errors']) > _int(row['successes']) else ''}">
      {round(_int(row['successes']) / max(1, _int(row['successes']) + _int(row['errors'])) * 100, 1)}%
    </span>
  </td>
</tr>
"""
        for row in feature_rows
    ) or '<tr><td colspan="5" class="analytics-empty">هنوز رویدادی ثبت نشده است.</td></tr>'

    campaign_cards = "".join(
        f"""
<section class="campaign-card">
  <div class="campaign-title">{esc(row['title'])}</div>
  <div class="campaign-stats">
    <div class="campaign-stat">
      <div class="campaign-stat-label">نمایش</div>
      <div class="campaign-stat-value">{_int(row['impressions']):,}</div>
    </div>
    <div class="campaign-stat">
      <div class="campaign-stat-label">کلیک</div>
      <div class="campaign-stat-value">{_int(row['clicks']):,}</div>
    </div>
    <div class="campaign-stat">
      <div class="campaign-stat-label">بستن</div>
      <div class="campaign-stat-value">{_int(row['dismisses']):,}</div>
    </div>
    <div class="campaign-stat">
      <div class="campaign-stat-label">CTR</div>
      <div class="campaign-stat-value">
        {round(_int(row['clicks']) / max(1, _int(row['impressions'])) * 100, 1)}%
      </div>
    </div>
  </div>
</section>
"""
        for row in campaign_rows
    ) or '<div class="analytics-empty">کمپینی ثبت نشده است.</div>'

    filters = "".join(
        f"""
<a
  class="analytics-filter {'active' if value == days else ''}"
  href="/admin/analytics?days={value}"
>
  {value} روز
</a>
"""
        for value in (7, 30, 90)
    )

    body = f"""
{_analytics_styles()}
<div class="analytics-page">
  <section class="card">
    <div class="analytics-header">
      <div class="analytics-title">
        <h2>گزارش جامع عملکرد</h2>
        <p>تحلیل کاربران، قابلیت‌ها، رویدادها و کمپین‌ها در بازه انتخاب‌شده</p>
      </div>
      <div class="analytics-filters">{filters}</div>
    </div>
  </section>

  <div class="analytics-kpis">
    <section class="analytics-kpi">
      <div class="analytics-kpi-label">👤 کاربران جدید</div>
      <div class="analytics-kpi-value">{new_users:,}</div>
      <div class="analytics-kpi-note">در {days} روز گذشته</div>
    </section>

    <section class="analytics-kpi">
      <div class="analytics-kpi-label">🟢 کاربران فعال</div>
      <div class="analytics-kpi-value">{active_users:,}</div>
      <div class="analytics-kpi-note good">{active_rate}% از کل کاربران</div>
    </section>

    <section class="analytics-kpi">
      <div class="analytics-kpi-label">⚡ کل رویدادها</div>
      <div class="analytics-kpi-value">{total_events:,}</div>
      <div class="analytics-kpi-note">
        میانگین {round(total_events / max(days, 1), 1)} رویداد در روز
      </div>
    </section>

    <section class="analytics-kpi">
      <div class="analytics-kpi-label">🎯 نرخ موفقیت ابزارها</div>
      <div class="analytics-kpi-value">{success_rate}%</div>
      <div class="analytics-kpi-note">{all_errors:,} خطای ثبت‌شده</div>
    </section>
  </div>

  <div class="analytics-grid">
    <section class="analytics-card">
      <div class="analytics-card-head">
        <div>
          <h3 class="analytics-card-title">روند مصرف روزانه</h3>
          <div class="analytics-card-sub">تعداد رویدادهای ثبت‌شده در هر روز</div>
        </div>
      </div>
      {_daily_chart(daily)}
    </section>

    <section class="analytics-card">
      <div class="analytics-card-head">
        <div>
          <h3 class="analytics-card-title">محبوب‌ترین قابلیت‌ها</h3>
          <div class="analytics-card-sub">رتبه‌بندی بر اساس میزان استفاده</div>
        </div>
      </div>
      {_feature_ranking(feature_rows[:7])}
    </section>
  </div>

  <section class="analytics-card">
    <div class="analytics-card-head">
      <div>
        <h3 class="analytics-card-title">جزئیات عملکرد قابلیت‌ها</h3>
        <div class="analytics-card-sub">مصرف، موفقیت، خطا و نرخ سلامت هر قابلیت</div>
      </div>
    </div>

    <div class="analytics-table-wrap">
      <table class="analytics-table">
        <thead>
          <tr>
            <th>قابلیت</th>
            <th>کل مصرف</th>
            <th>موفق</th>
            <th>خطا</th>
            <th>نرخ موفقیت</th>
          </tr>
        </thead>
        <tbody>{feature_table}</tbody>
      </table>
    </div>
  </section>

  <section class="analytics-card">
    <div class="analytics-card-head">
      <div>
        <h3 class="analytics-card-title">عملکرد کمپین‌ها</h3>
        <div class="analytics-card-sub">نمایش، کلیک، بستن و نرخ کلیک هر کمپین</div>
      </div>
    </div>

    <div class="campaign-grid">{campaign_cards}</div>
  </section>
</div>
"""

    return HTMLResponse(
        page_layout(
            "آمار و گزارش‌ها",
            body,
        )
    )

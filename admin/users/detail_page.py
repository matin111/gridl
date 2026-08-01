from __future__ import annotations

from ..common import *  # noqa: F401,F403


router = APIRouter(prefix="/admin")


@router.get("/users/{user_id}", response_class=HTMLResponse)
async def user_detail_page(user_id: str, request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    with database() as connection:
        user = connection.execute(
            "SELECT * FROM users WHERE id=?",
            (user_id,),
        ).fetchone()

        if not user:
            return HTMLResponse(
                page_layout(
                    "کاربر پیدا نشد",
                    '<section class="card">کاربر موردنظر وجود ندارد.</section>',
                ),
                status_code=404,
            )

        subscriptions = connection.execute(
            """
            SELECT *
            FROM subscriptions
            WHERE user_id=?
            ORDER BY created_at DESC
            LIMIT 30
            """,
            (user_id,),
        ).fetchall()

        counters = connection.execute(
            """
            SELECT
                feature_key,
                SUM(used_count) AS total
            FROM usage_counters
            WHERE user_id=?
            GROUP BY feature_key
            ORDER BY total DESC
            """,
            (user_id,),
        ).fetchall()

        events = connection.execute(
            """
            SELECT
                feature_key,
                event_type,
                created_at
            FROM usage_events
            WHERE installation_id=?
            ORDER BY created_at DESC
            LIMIT 40
            """,
            (user["installation_id"],),
        ).fetchall()

    snapshot = user_subscription_snapshot(user)

    sub_rows = "".join(
        f"""
        <tr>
            <td>{esc(subscription["plan_key"])}</td>
            <td>{esc(subscription["source"])}</td>
            <td>{esc(subscription["starts_at"])}</td>
            <td>{esc(subscription["expires_at"] or "بدون تاریخ")}</td>
            <td>
                {
                    '<span class="badge badge-active">فعال</span>'
                    if subscription["is_active"]
                    else '<span class="badge badge-off">غیرفعال</span>'
                }
            </td>
        </tr>
        """
        for subscription in subscriptions
    )

    usage_cards = "".join(
        f"""
        <div class="usage-item">
            <strong>{esc(counter["feature_key"])}</strong>
            <div class="stat" style="font-size:23px">
                {int(counter["total"] or 0)}
            </div>
        </div>
        """
        for counter in counters
    )

    event_rows = "".join(
        f"""
        <tr>
            <td>{esc(event["feature_key"])}</td>
            <td>{esc(event["event_type"])}</td>
            <td>{esc(event["created_at"])}</td>
        </tr>
        """
        for event in events
    )

    display_name = esc(user["display_name"] or "بدون نام")
    email = esc(user["email"] or "-")
    phone = esc(user["phone"] or "-")
    app_version = esc(user["app_version"] or "-")
    android_version = esc(user["android_version"] or "-")
    last_seen_at = esc(user["last_seen_at"] or "-")
    installation_id = esc(user["installation_id"])
    escaped_user_id = esc(user_id)

    device = " ".join(
        part
        for part in [
            user["manufacturer"],
            user["device_model"],
        ]
        if part
    )

    plan_name = (
        "رشد یار Pro"
        if snapshot["is_premium"]
        else "رایگان"
    )

    user_status = (
        "مسدود"
        if user["is_blocked"]
        else "فعال"
    )

    block_button_class = (
        "btn-secondary"
        if user["is_blocked"]
        else "btn-danger"
    )

    block_button_text = (
        "رفع مسدودی"
        if user["is_blocked"]
        else "مسدودسازی"
    )

    body = f"""
<div class="actions" style="margin-bottom:16px">
    <a class="btn btn-secondary" href="/admin/users">
        بازگشت به کاربران
    </a>
</div>

<div class="detail-grid">
    <div class="detail-card">
        <small>نام کاربر</small>
        <strong>{display_name}</strong>
    </div>

    <div class="detail-card">
        <small>پلن فعلی</small>
        <strong>{plan_name}</strong>
    </div>

    <div class="detail-card">
        <small>وضعیت</small>
        <strong>{user_status}</strong>
    </div>

    <div class="detail-card">
        <small>آخرین اتصال</small>
        <strong>{last_seen_at}</strong>
    </div>

    <div class="detail-card">
        <small>ایمیل</small>
        <strong>{email}</strong>
    </div>

    <div class="detail-card">
        <small>شماره</small>
        <strong>{phone}</strong>
    </div>

    <div class="detail-card">
        <small>دستگاه</small>
        <strong>{esc(device or "-")}</strong>
    </div>

    <div class="detail-card">
        <small>نسخه اپ / اندروید</small>
        <strong>{app_version} / {android_version}</strong>
    </div>
</div>

<section class="card" style="margin-bottom:16px">
    <h3>مدیریت سریع</h3>

    <div class="actions">
        <form method="post" action="/admin/users/activate">
            <input
                type="hidden"
                name="installation_id"
                value="{installation_id}"
            >

            <input
                name="days"
                type="number"
                min="1"
                max="3650"
                value="30"
                style="width:100px"
            >

            <button class="btn btn-primary" type="submit">
                فعال‌سازی / تمدید
            </button>
        </form>

        <form
            method="post"
            action="/admin/users/deactivate"
            onsubmit="return confirm('اشتراک غیرفعال شود؟')"
        >
            <input
                type="hidden"
                name="installation_id"
                value="{installation_id}"
            >

            <button class="btn btn-danger" type="submit">
                غیرفعال‌کردن اشتراک
            </button>
        </form>

        <form
            method="post"
            action="/admin/users/reset-usage"
            onsubmit="return confirm('همه سهمیه‌های این کاربر ریست شود؟')"
        >
            <input
                type="hidden"
                name="user_id"
                value="{escaped_user_id}"
            >

            <button class="btn btn-secondary" type="submit">
                ریست سهمیه
            </button>
        </form>

        <form method="post" action="/admin/users/toggle-block">
            <input
                type="hidden"
                name="user_id"
                value="{escaped_user_id}"
            >

            <button
                class="btn {block_button_class}"
                type="submit"
            >
                {block_button_text}
            </button>
        </form>
    </div>
</section>

<section class="card" style="margin-bottom:16px">
    <h3>مصرف سهمیه‌ها</h3>

    <div class="usage-grid">
        {
            usage_cards
            or "<div>مصرفی ثبت نشده است.</div>"
        }
    </div>
</section>

<section class="card" style="margin-bottom:16px">
    <h3>تاریخچه اشتراک</h3>

    <div style="overflow:auto">
        <table>
            <thead>
                <tr>
                    <th>پلن</th>
                    <th>منبع</th>
                    <th>شروع</th>
                    <th>انقضا</th>
                    <th>وضعیت</th>
                </tr>
            </thead>

            <tbody>
                {
                    sub_rows
                    or '<tr><td colspan="5">اشتراکی ثبت نشده است.</td></tr>'
                }
            </tbody>
        </table>
    </div>
</section>

<section class="card">
    <h3>آخرین فعالیت‌ها</h3>

    <div style="overflow:auto">
        <table>
            <thead>
                <tr>
                    <th>قابلیت</th>
                    <th>رویداد</th>
                    <th>زمان</th>
                </tr>
            </thead>

            <tbody>
                {
                    event_rows
                    or '<tr><td colspan="3">فعالیتی ثبت نشده است.</td></tr>'
                }
            </tbody>
        </table>
    </div>
</section>
"""

    return HTMLResponse(
        page_layout(
            "جزئیات کاربر",
            body,
        )
    )

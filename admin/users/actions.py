from __future__ import annotations

from ..common import *  # noqa: F401,F403

router = APIRouter(prefix="/admin")


@router.post("/users/activate")
async def activate_user(request: Request):
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
        installation_id=installation_id
    )

    now = utc_now()
    expires_at = now + timedelta(days=days)

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
async def deactivate_user(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    form = await read_form(request)

    installation_id = form.get(
        "installation_id",
        "",
    ).strip()

    user = get_or_create_user(
        installation_id=installation_id
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
        row = connection.execute(
            "SELECT is_blocked FROM users WHERE id=?",
            (user_id,),
        ).fetchone()

        if row:
            connection.execute(
                "UPDATE users SET is_blocked=?, updated_at=? WHERE id=?",
                (
                    0 if row["is_blocked"] else 1,
                    isoformat(utc_now()),
                    user_id,
                ),
            )

    return RedirectResponse(
        url=request.headers.get("referer") or "/admin/users",
        status_code=303,
    )


@router.post("/users/reset-usage")
async def reset_user_usage(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect

    form = await read_form(request)
    user_id = form.get("user_id", "").strip()

    with database() as connection:
        connection.execute(
            "DELETE FROM usage_counters WHERE user_id=?",
            (user_id,),
        )

        connection.execute(
            """
            INSERT INTO admin_actions
            (
                id,
                action,
                target_type,
                target_id,
                payload,
                created_at
            )
            VALUES (?,?,?,?,?,?)
            """,
            (
                str(uuid.uuid4()),
                "reset_usage",
                "user",
                user_id,
                "{}",
                isoformat(utc_now()),
            ),
        )

    return RedirectResponse(
        url=request.headers.get("referer") or "/admin/users",
        status_code=303,
    )

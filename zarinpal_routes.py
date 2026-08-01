from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse

from subscription_admin_api import (
    database,
    utc_now,
    isoformat,
)

from zarinpal_payment import (
    create_payment,
    verify_payment,
)

import payment_db


router = APIRouter()


@router.post("/payment/create/{plan_slug}")
async def create_zarinpal_payment(
    plan_slug: str,
    request: Request,
):

    form = await request.form()

    email = str(
        form.get("email","")
    ).strip()


    if not email:
        return RedirectResponse(
            f"/buy/{plan_slug}",
            status_code=303
        )


    with database() as db:

        plan = db.execute(
            """
            SELECT *
            FROM subscription_plans
            WHERE slug=?
            AND is_active=1
            """,
            (plan_slug,)
        ).fetchone()


    if not plan:
        return HTMLResponse(
            "پلن پیدا نشد",
            status_code=404
        )


    result = await create_payment(
        amount=int(plan["price"]),
        description=f"خرید {plan['title']}",
        email=email,
    )


    return RedirectResponse(
        result["url"],
        status_code=303
    )



@router.get("/payment/verify")
async def verify_zarinpal_payment(
    Authority:str,
    Status:str,
):

    if Status != "OK":
        return HTMLResponse(
            "پرداخت لغو شد"
        )


    # فعلاً برای تکمیل اتصال
    # مرحله بعد ذخیره Authority را اضافه می‌کنیم

    return HTMLResponse(
        """
        <h2 dir="rtl">
        پرداخت موفق بود.
        در حال فعال سازی اشتراک...
        </h2>
        """
    )


from __future__ import annotations

from .common import *  # noqa: F401,F403

router = APIRouter(prefix="/admin")


@router.get(
    "/login",
    response_class=HTMLResponse,
)
async def login_page(
    request: Request,
):
    if is_authenticated(request):
        return RedirectResponse(
            url="/admin",
            status_code=303,
        )

    error = request.query_params.get(
        "error"
    )

    error_html = (
        '<div class="notice">رمز عبور اشتباه است.</div>'
        if error
        else ""
    )

    return HTMLResponse(
        f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ورود پنل رشد یار</title>
<style>
body {{
  margin:0;
  font-family:Tahoma,Arial,sans-serif;
  background:#f8f7ff;
}}
.login-shell {{
  min-height:100vh;
  display:grid;
  place-items:center;
  padding:20px;
}}
.login-card {{
  width:min(420px,100%);
  background:white;
  border-radius:24px;
  padding:28px;
  border:1px solid #e7e4f5;
  box-shadow:0 15px 45px rgba(62,45,120,.12);
}}
input {{
  width:100%;
  padding:13px;
  margin:10px 0 16px;
  border:1px solid #e7e4f5;
  border-radius:13px;
  box-sizing:border-box;
}}
button {{
  width:100%;
  padding:13px;
  background:#6c3cff;
  color:white;
  border:0;
  border-radius:13px;
  font-weight:800;
}}
.notice {{
  background:#ffe7e5;
  color:#b42318;
  padding:11px;
  border-radius:12px;
  margin-bottom:12px;
}}
</style>
</head>
<body>
<div class="login-shell">
  <form class="login-card" method="post" action="/admin/login">
    <h2>ورود به پنل مدیریت</h2>
    <p>رشد یار</p>
    {error_html}
    <label>رمز مدیریت</label>
    <input type="password" name="password" required autofocus>
    <button type="submit">ورود</button>
  </form>
</div>
</body>
</html>"""
    )


@router.post("/login")
async def login_submit(
    request: Request,
):
    form = await read_form(request)

    password = form.get(
        "password",
        "",
    )

    if (
        not panel_password()
        or not hmac.compare_digest(
            password,
            panel_password(),
        )
    ):
        return RedirectResponse(
            url="/admin/login?error=1",
            status_code=303,
        )

    response = RedirectResponse(
        url="/admin",
        status_code=303,
    )

    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_token(),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/admin",
    )

    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(
        url="/admin/login",
        status_code=303,
    )

    response.delete_cookie(
        SESSION_COOKIE,
        path="/admin",
    )

    return response

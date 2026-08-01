from pathlib import Path

p = Path("admin/settings.py")

text = p.read_text()

start = text.find("async def upload_apk(")

if start == -1:
    raise SystemExit("upload_apk not found")

next_def = text.find("\nasync def ", start + 10)

end = len(text) if next_def == -1 else next_def

new_func = """
async def upload_apk(
    request: Request,
    apk_file: UploadFile = File(...)
):

    redirect = require_auth(request)

    if redirect:
        return redirect

    if not apk_file.filename.lower().endswith(".apk"):
        return RedirectResponse(
            "/admin/settings",
            status_code=303
        )

    APK_DIR = "site-assets/apk"

    os.makedirs(
        APK_DIR,
        exist_ok=True
    )

    filename = apk_file.filename

    path = os.path.join(
        APK_DIR,
        filename
    )

    with open(path, "wb") as buffer:
        shutil.copyfileobj(
            apk_file.file,
            buffer
        )

    apk_url = f"/site-assets/apk/{filename}"

    with database() as db:
        db.execute(
            '''
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value
            ''',
            ("apk_url", apk_url),
        )

    return RedirectResponse(
        "/admin/settings",
        status_code=303
    )

"""

text = text[:start] + new_func + text[end:]

p.write_text(text)

print("upload_apk fixed")

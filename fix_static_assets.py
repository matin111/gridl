from pathlib import Path

p = Path("main.py")

text = p.read_text(encoding="utf-8")


old = '''
os.makedirs("/root/aistudio-api/site_assets", exist_ok=True)
app.mount(
    "/site-assets",
    StaticFiles(directory="/root/aistudio-api/site_assets"),
    name="site_assets",
)
'''


new = '''
os.makedirs("/root/aistudio-api/site-assets", exist_ok=True)

app.mount(
    "/site-assets",
    StaticFiles(
        directory="/root/aistudio-api/site-assets"
    ),
    name="site_assets",
)
'''


if old not in text:
    raise Exception("static block not found")


text=text.replace(old,new)

p.write_text(text,encoding="utf-8")

print("static path fixed")

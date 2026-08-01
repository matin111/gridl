from pathlib import Path

p = Path("landing.py")

text = p.read_text(encoding="utf-8")


old = """
    s = {}
    try:
        s = get_landing_settings()
    except Exception:
        pass
"""


new = """
    s = {}

    try:
        s = get_landing_settings()
    except Exception:
        pass


    # Load download links from app_settings
    try:
        with database() as connection:
            rows = connection.execute(
                '''
                SELECT key,value
                FROM app_settings
                WHERE key IN (
                    'apk_url',
                    'market_url',
                    'google_play_url'
                )
                '''
            ).fetchall()

        for row in rows:
            s[row["key"]] = row["value"]

    except Exception:
        pass
"""


if old not in text:
    raise Exception("target block not found")


text = text.replace(old,new)


p.write_text(text,encoding="utf-8")

print("landing download settings fixed")


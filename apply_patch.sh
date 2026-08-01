#!/bin/bash
set -e
cd /root/aistudio-api

cp landing.py landing.py.before-logo-patch

python3 - <<'PY'
from pathlib import Path
p = Path("landing.py")
txt = p.read_text()
txt = txt.replace('/site-assets/app-1.webp','/site-assets/rashdyar-logo.png')
p.write_text(txt)
print("landing patched")
PY

cp site_assets/rashdyar-logo.png /root/aistudio-api/site_assets/rashdyar-logo.png
systemctl restart aistudio-api
echo "done"

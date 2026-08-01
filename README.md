# AIStudioPro Backend v8

Structured JSON output for all AI tools.

Install path:
`/root/aistudio-api`

Check:
```bash
/root/aistudio-api/venv/bin/python -m py_compile /root/aistudio-api/main.py
systemctl restart aistudio-api
curl https://ap.movifilm.sbs/health
```

Existing Android hashtag endpoint remains compatible:
`POST /v1/hashtags`

General endpoint:
`POST /v1/ai`

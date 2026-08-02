from __future__ import annotations

from pathlib import Path

PATH = Path("instagram_analyzer.py")
text = PATH.read_text(encoding="utf-8")

if "import asyncio\n" not in text:
    text = text.replace("from __future__ import annotations\n\n", "from __future__ import annotations\n\nimport asyncio\n", 1)

start = text.index("async def boxapi_post(\n")
end = text.index("\n\nasync def fetch_instagram_profile(\n", start)

replacement = '''async def boxapi_post(
    url: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not BOXAPI_TOKEN:
        raise HTTPException(
            status_code=500,
            detail=(
                "BOXAPI_TOKEN روی سرور "
                "تنظیم نشده است."
            ),
        )

    timeout = httpx.Timeout(
        connect=float(os.getenv("BOXAPI_CONNECT_TIMEOUT", "15")),
        read=float(os.getenv("BOXAPI_READ_TIMEOUT", "75")),
        write=float(os.getenv("BOXAPI_WRITE_TIMEOUT", "20")),
        pool=float(os.getenv("BOXAPI_POOL_TIMEOUT", "20")),
    )
    max_attempts = max(1, int(os.getenv("BOXAPI_MAX_ATTEMPTS", "3")))
    backoff_seconds = max(0.0, float(os.getenv("BOXAPI_RETRY_BACKOFF", "1.2")))
    retry_statuses = {408, 425, 429, 500, 502, 503, 504}
    last_error: Exception | None = None

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {BOXAPI_TOKEN}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=payload,
                )

                if response.status_code in retry_statuses and attempt < max_attempts:
                    await asyncio.sleep(backoff_seconds * (2 ** (attempt - 1)))
                    continue

                if response.status_code >= 400:
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "BoxAPI درخواست را نپذیرفت. "
                            f"HTTP {response.status_code}: "
                            f"{response.text[:300]}"
                        ),
                    )

                data = response.json()
                if not isinstance(data, dict):
                    raise HTTPException(
                        status_code=502,
                        detail="پاسخ BoxAPI ساختار JSON معتبری ندارد.",
                    )
                return data

            except HTTPException:
                raise
            except (httpx.TimeoutException, httpx.RemoteProtocolError, httpx.NetworkError) as error:
                last_error = error
                if attempt < max_attempts:
                    await asyncio.sleep(backoff_seconds * (2 ** (attempt - 1)))
                    continue
                break
            except httpx.RequestError as error:
                last_error = error
                if attempt < max_attempts:
                    await asyncio.sleep(backoff_seconds * (2 ** (attempt - 1)))
                    continue
                break
            except ValueError as error:
                raise HTTPException(
                    status_code=502,
                    detail="پاسخ BoxAPI فرمت JSON معتبر ندارد.",
                ) from error

    if isinstance(last_error, httpx.TimeoutException):
        raise HTTPException(
            status_code=504,
            detail=(
                "زمان دریافت اطلاعات اینستاگرام پس از "
                f"{max_attempts} تلاش تمام شد."
            ),
        ) from last_error

    raise HTTPException(
        status_code=502,
        detail=(
            "ارتباط با BoxAPI پس از "
            f"{max_attempts} تلاش برقرار نشد: {last_error}"
        ),
    ) from last_error
'''

text = text[:start] + replacement + text[end:]
PATH.write_text(text, encoding="utf-8")
print("BoxAPI retry and timeout hardening applied to instagram_analyzer.py")

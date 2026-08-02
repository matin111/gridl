import httpx
import pytest

import instagram_analyzer as analyzer


class FakeAsyncClient:
    responses = []
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        type(self).calls += 1
        item = type(self).responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def response(status_code: int, payload=None):
    request = httpx.Request("POST", "https://boxapi.ir/test")
    return httpx.Response(status_code, request=request, json=payload or {"status": "done"})


@pytest.mark.asyncio
async def test_boxapi_retries_remote_disconnect(monkeypatch):
    monkeypatch.setattr(analyzer, "BOXAPI_TOKEN", "token")
    monkeypatch.setattr(analyzer.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setenv("BOXAPI_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("BOXAPI_RETRY_BACKOFF", "0")
    FakeAsyncClient.calls = 0
    FakeAsyncClient.responses = [
        httpx.RemoteProtocolError("Server disconnected"),
        response(200, {"status": "done", "response": {"body": {"ok": True}}}),
    ]

    result = await analyzer.boxapi_post("https://boxapi.ir/test", {"query": "test"})

    assert result["status"] == "done"
    assert FakeAsyncClient.calls == 2


@pytest.mark.asyncio
async def test_boxapi_retries_transient_http_status(monkeypatch):
    monkeypatch.setattr(analyzer, "BOXAPI_TOKEN", "token")
    monkeypatch.setattr(analyzer.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setenv("BOXAPI_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("BOXAPI_RETRY_BACKOFF", "0")
    FakeAsyncClient.calls = 0
    FakeAsyncClient.responses = [
        response(503, {"error": "temporary"}),
        response(200, {"status": "done"}),
    ]

    result = await analyzer.boxapi_post("https://boxapi.ir/test", {"query": "test"})

    assert result["status"] == "done"
    assert FakeAsyncClient.calls == 2

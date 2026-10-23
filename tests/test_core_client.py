import asyncio

import httpx
import pytest
from fastapi import HTTPException

from src.backend.integrations.guilarde.client import GuilardeClient


@pytest.mark.parametrize("data", [{}, {"allowed": True}, {"tenant_id": "bad"}])
def test_malformed_grant_fail_closed(data, monkeypatch):
    client = GuilardeClient()

    async def request(*args, **kwargs):
        return data

    monkeypatch.setattr(client, "_request", request)
    with pytest.raises(HTTPException) as error:
        asyncio.run(client.authorize("token", "tenant", "read"))
    assert error.value.status_code == 503


@pytest.mark.parametrize("status", [401, 403, 500])
def test_http_fail_closed(status, monkeypatch):
    original = httpx.AsyncClient
    transport = httpx.MockTransport(lambda req: httpx.Response(status, json={"detail": "denied"}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=transport, **kwargs))
    with pytest.raises(HTTPException) as error:
        asyncio.run(GuilardeClient()._request("GET", "/v1/me/tenants", "token"))
    assert error.value.status_code == (status if status < 500 else 503)

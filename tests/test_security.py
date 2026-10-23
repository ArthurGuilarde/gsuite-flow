import time
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.backend.api import deps
from src.backend.core import sessions
from src.backend.core.config import Settings, settings
from src.backend.integrations.guilarde import oidc
from src.backend.integrations.guilarde.contracts import Authorization, Principal
from src.backend.main import app


@pytest.fixture
def keys(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(
        oidc,
        "key_client",
        lambda: SimpleNamespace(get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=key.public_key())),
    )
    return key


def make_token(keys, **overrides):
    claims = dict(
        sub="user-a",
        iss=settings.OIDC_ISSUER,
        aud=settings.OIDC_AUDIENCE,
        iat=int(time.time()),
        exp=int(time.time()) + 300,
    )
    claims.update(overrides)
    return jwt.encode(claims, keys, algorithm="RS256")


def test_token_valid(keys):
    assert oidc.validate_access_token(make_token(keys)).sub == "user-a"


@pytest.mark.parametrize(
    "claim,value",
    [("exp", 1), ("aud", "other-app"), ("iss", "https://attacker"), ("sub", ""), ("iat", int(time.time()) + 3600)],
)
def test_bad_claims(keys, claim, value):
    with pytest.raises(HTTPException) as error:
        oidc.validate_access_token(make_token(keys, **{claim: value}))
    assert error.value.status_code == 401


def test_forged_signature(keys):
    wrong = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(HTTPException):
        oidc.validate_access_token(make_token(wrong))


def test_hs256_rejected(keys):
    token = jwt.encode(dict(sub="user-a", exp=int(time.time()) + 300), "x" * 32, algorithm="HS256")
    with pytest.raises(HTTPException):
        oidc.validate_access_token(token)


def test_production_config():
    with pytest.raises(ValueError):
        Settings(ENVIRONMENT="production", _env_file=None)
    with pytest.raises(ValueError):
        Settings(ENVIRONMENT="production", DATABASE_URL="sqlite:///app.db", _env_file=None)


@pytest.fixture
def client(monkeypatch):
    # Do not start the real DB lifespan in unit tests.
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(sessions, "load_session", lambda _sid: {"access_token": "test", "csrf": "csrf"})
    monkeypatch.setattr(deps, "validate_access_token", lambda _token: Principal(sub="user-a"))
    from tests.support.tenant_example import create_test_app

    client = TestClient(create_test_app())
    client.cookies.set(settings.SESSION_COOKIE, "a" * 43)
    return client


@pytest.mark.parametrize("alter", ["deny", "subject", "tenant", "app", "access", "write"])
def test_grant_mismatch_denied(client, monkeypatch, alter):
    tenant = uuid4()
    grant = dict(sub="user-a", tenant_id=tenant, app_id=settings.APP_ID, allowed=True, permissions={"access", "write"})
    if alter == "deny":
        grant["allowed"] = False
    if alter == "subject":
        grant["sub"] = "user-b"
    if alter == "tenant":
        grant["tenant_id"] = uuid4()
    if alter == "app":
        grant["app_id"] = "other"
    if alter in ("access", "write"):
        grant["permissions"].remove(alter)

    async def authorize(*_args):
        return Authorization(**grant)

    monkeypatch.setattr(deps.core_client, "authorize", authorize)
    response = client.post(
        "/api/v1/test-records",
        json={"title": "secret"},
        headers={"X-Tenant-ID": str(tenant), "X-CSRF-Token": "csrf", "Origin": settings.PUBLIC_URL},
    )
    assert response.status_code == 403


def test_core_outage_fail_closed(client, monkeypatch):
    async def authorize(*_args):
        raise HTTPException(503, "Core unavailable")

    monkeypatch.setattr(deps.core_client, "authorize", authorize)
    assert client.get("/api/v1/test-records", headers={"X-Tenant-ID": str(uuid4())}).status_code == 503


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-CSRF-Token": "wrong", "Origin": settings.PUBLIC_URL},
        {"X-CSRF-Token": "csrf", "Origin": "https://attacker"},
    ],
)
def test_csrf_denied(client, headers):
    assert (
        client.post(
            "/api/v1/test-records", json={"title": "x"}, headers={"X-Tenant-ID": str(uuid4()), **headers}
        ).status_code
        == 403
    )


def test_anonymous():
    assert TestClient(app).get("/auth/session").status_code == 401


def test_tenant_mandatory(client):
    assert client.get("/api/v1/test-records").status_code == 422


def test_private_no_store(client):
    response = client.get("/auth/session")
    assert response.headers["cache-control"] == "no-store"
    assert "access_token" not in response.text
    assert "default-src" in response.headers["content-security-policy"]


def test_authorized_workspace_context(client, monkeypatch):
    tenant = uuid4()

    async def authorize(_token, requested_tenant, permission):
        assert requested_tenant == tenant and permission == "read"
        return Authorization(
            sub="user-a",
            tenant_id=tenant,
            app_id=settings.APP_ID,
            allowed=True,
            permissions={"access", "read"},
            features={"export"},
        )

    monkeypatch.setattr(deps.core_client, "authorize", authorize)
    response = client.get("/api/v1/context", headers={"X-Tenant-ID": str(tenant)})
    assert response.status_code == 200
    assert response.json() == {"tenant_id": str(tenant), "permissions": ["access", "read"], "features": ["export"]}


@pytest.mark.parametrize("peer,host", [("203.0.113.9", "127.0.0.1"), ("127.0.0.1", "attacker.example")])
def test_local_adapter_rejects_network_peers_and_hosts(monkeypatch, peer, host):
    monkeypatch.setattr(settings, "AUTH_MODE", "local")
    client = TestClient(app, client=(peer, 50000), base_url=f"http://{host}")
    response = client.get("/health/live", headers={"X-Forwarded-For": "127.0.0.1"})
    assert response.status_code == 403


def test_oidc_app_does_not_mount_development_authentication():
    assert settings.AUTH_MODE == "oidc"
    assert not any(path.startswith("/auth/dev") for path in app.openapi()["paths"])
    assert TestClient(app).get("/auth/dev/config").status_code == 404


def test_direct_import_config_cannot_pair_local_identity_with_postgres():
    with pytest.raises(ValueError, match="Local authentication requires a SQLite"):
        Settings(
            ENVIRONMENT="development",
            AUTH_MODE="local",
            DATABASE_URL="postgresql+psycopg://app:secret@127.0.0.1/app",
            _env_file=None,
        )


def test_migration_backend_cannot_cross_local_and_production_databases():
    with pytest.raises(ValueError, match="same backend"):
        Settings(
            DATABASE_URL="sqlite:///dev.sqlite3",
            MIGRATION_DATABASE_URL="postgresql+psycopg://owner:secret@127.0.0.1/app",
            _env_file=None,
        )

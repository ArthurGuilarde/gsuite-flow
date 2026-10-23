import time
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from authlib.integrations.starlette_client import OAuth
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from src.backend.api import auth, deps
from src.backend.core import sessions
from src.backend.core.config import settings
from src.backend.integrations.guilarde.contracts import Principal
from src.backend.main import app


@pytest.fixture
def oidc_browser(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    jwk.update(kid="test", use="sig", alg="RS256")
    state = {}
    store = {}

    def respond(request):
        path = request.url.path
        if path.endswith("openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": settings.OIDC_ISSUER,
                    "authorization_endpoint": "https://idp.example/authorize",
                    "token_endpoint": "https://idp.example/token",
                    "jwks_uri": "https://idp.example/jwks",
                    "id_token_signing_alg_values_supported": ["RS256"],
                },
            )
        if path == "/jwks":
            return httpx.Response(200, json={"keys": [jwk]})
        if path == "/token":
            form = parse_qs(request.content.decode())
            assert "code_verifier" in form
            claims = dict(
                iss=settings.OIDC_ISSUER,
                sub="member",
                aud="test-client",
                exp=int(time.time()) + 300,
                iat=int(time.time()),
                nonce=state["nonce"],
            )
            claims.update(state.get("overrides", {}))
            return httpx.Response(
                200,
                json={
                    "access_token": "access",
                    "token_type": "Bearer",
                    "expires_in": 300,
                    "id_token": jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"}),
                },
            )
        raise AssertionError(path)

    registry = OAuth()
    registry.register(
        name="guilarde",
        client_id="test-client",
        client_secret="test-secret",
        server_metadata_url="https://idp.example/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid profile",
            "code_challenge_method": "S256",
            "transport": httpx.MockTransport(respond),
        },
    )
    monkeypatch.setattr(auth, "oauth", registry)
    monkeypatch.setattr(settings, "OIDC_CLIENT_ID", "test-client")
    monkeypatch.setattr(settings, "OIDC_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(settings, "COOKIE_SECURE", False)
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(auth, "validate_access_token", lambda _token: Principal(sub="member"))
    monkeypatch.setattr(deps, "validate_access_token", lambda _token: Principal(sub="member"))
    monkeypatch.setattr(sessions, "load_session", lambda sid: dict(store.get(sid, {})))

    def save(sid, data, old_sid=None):
        if old_sid:
            store.pop(old_sid, None)
        if data:
            store[sid] = dict(data)
        else:
            store.pop(sid, None)

    monkeypatch.setattr(sessions, "save_session", save)
    browser = TestClient(app)
    response = browser.get("/auth/login", follow_redirects=False)
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert "code_challenge" in query
    state["nonce"] = query["nonce"][0]
    state["state"] = query["state"][0]
    assert "access" not in response.headers["set-cookie"]
    return browser, state, store


def test_oidc_callback_rotation_and_logout(oidc_browser):
    browser, state, store = oidc_browser
    old = browser.cookies.get(settings.SESSION_COOKIE)
    response = browser.get("/auth/callback", params={"code": "code", "state": state["state"]}, follow_redirects=False)
    assert response.status_code == 303
    new = browser.cookies.get(settings.SESSION_COOKIE)
    assert new != old and old not in store
    assert "HttpOnly" in response.headers["set-cookie"] and "SameSite=Lax" in response.headers["set-cookie"]
    session = browser.get("/auth/session")
    assert session.status_code == 200 and "access_token" not in session.text
    replay = browser.get("/auth/callback", params={"code": "code", "state": state["state"]}, follow_redirects=False)
    assert replay.status_code == 401


def test_logout_removes_session(oidc_browser):
    browser, state, store = oidc_browser
    browser.get("/auth/callback", params={"code": "code", "state": state["state"]}, follow_redirects=False)
    session = browser.get("/auth/session").json()
    sid = browser.cookies.get(settings.SESSION_COOKIE)
    response = browser.post(
        "/auth/logout", headers={"X-CSRF-Token": session["csrf_token"], "Origin": settings.PUBLIC_URL}
    )
    assert response.status_code == 204 and sid not in store
    assert browser.get("/auth/session").status_code == 401


@pytest.mark.parametrize(
    "overrides", [{"nonce": "wrong"}, {"aud": "wrong"}, {"iss": "https://wrong"}, {"sub": "wrong"}]
)
def test_invalid_id_token_denied(oidc_browser, overrides):
    browser, state, _store = oidc_browser
    state["overrides"] = overrides
    response = browser.get("/auth/callback", params={"code": "code", "state": state["state"]}, follow_redirects=False)
    assert response.status_code == 401


def test_wrong_state_denied(oidc_browser):
    browser, _state, _store = oidc_browser
    assert (
        browser.get("/auth/callback", params={"code": "code", "state": "wrong"}, follow_redirects=False).status_code
        == 401
    )

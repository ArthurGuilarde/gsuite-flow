from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.integration


def context(db, tenant):
    db.execute(text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant)})


def insert(db, tenant, title="test"):
    db.execute(
        text("INSERT INTO tenant_test_records(id,tenant_id,created_by,title) VALUES (:id,:tenant,'user',:title)"),
        {"id": uuid4(), "tenant": tenant, "title": title},
    )


def test_rls_unfiltered_query_and_pool_reset(db_factory):
    a, b = uuid4(), uuid4()
    for tenant in [a, b]:
        with db_factory.begin() as db:
            context(db, tenant)
            insert(db, tenant)
    with db_factory.begin() as db:
        context(db, a)
        assert db.execute(text("SELECT tenant_id FROM tenant_test_records")).scalars().all() == [a]
    with db_factory.begin() as db:
        assert db.execute(text("SELECT count(*) FROM tenant_test_records")).scalar() == 0
        context(db, b)
        assert db.execute(text("SELECT tenant_id FROM tenant_test_records")).scalars().all() == [b]


def test_rls_insert_mismatch_denied(db_factory):
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, uuid4())
        insert(db, uuid4())


def test_rls_update_and_delete_denied(db_factory):
    a, b = uuid4(), uuid4()
    with db_factory.begin() as db:
        context(db, a)
        insert(db, a)
    with db_factory.begin() as db:
        context(db, b)
        assert db.execute(text("UPDATE tenant_test_records SET title='stolen'")).rowcount == 0
        assert db.execute(text("DELETE FROM tenant_test_records")).rowcount == 0
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, a)
        db.execute(text("UPDATE tenant_test_records SET tenant_id=:b"), {"b": b})


def test_runtime_privileges(db_factory):
    with db_factory.begin() as db:
        row = db.execute(text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")).one()
        assert not row.rolsuper and not row.rolbypassrls
        assert (
            db.execute(
                text("SELECT tableowner=current_user FROM pg_tables WHERE tablename='tenant_test_records'")
            ).scalar()
            is False
        )
        assert (
            db.execute(
                text("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname='tenant_test_records'")
            ).scalar()
            is True
        )
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        db.execute(text("ALTER TABLE tenant_test_records DISABLE ROW LEVEL SECURITY"))


def test_shared_family_and_rollback(db_factory):
    a = uuid4()
    with db_factory.begin() as db:
        context(db, a)
        insert(db, a)
    with db_factory.begin() as db:
        context(db, a)
        db.execute(text("SELECT set_config('app.subject','other-member',true)"))
        assert db.execute(text("SELECT count(*) FROM tenant_test_records")).scalar() == 1
    with pytest.raises(RuntimeError), db_factory.begin() as db:
        context(db, a)
        insert(db, a)
        raise RuntimeError("rollback")
    with db_factory.begin() as db:
        context(db, a)
        assert db.execute(text("SELECT count(*) FROM tenant_test_records")).scalar() == 1


def test_api_authorized_flow(db_factory, monkeypatch):
    from fastapi.testclient import TestClient

    from src.backend.api import deps
    from src.backend.core import sessions
    from src.backend.core.config import settings
    from src.backend.integrations.guilarde.contracts import Authorization, Principal
    from tests.support.tenant_example import create_test_app

    a = uuid4()
    monkeypatch.setattr(deps, "SessionLocal", db_factory)
    monkeypatch.setattr(sessions, "load_session", lambda _sid: {"access_token": "test", "csrf": "csrf"})
    monkeypatch.setattr(deps, "validate_access_token", lambda _token: Principal(sub="member-one"))

    async def authorize(token, tenant, permission):
        return Authorization(
            sub="member-one",
            tenant_id=tenant,
            app_id=settings.APP_ID,
            allowed=tenant == a,
            permissions={"access", "read", "write"},
        )

    monkeypatch.setattr(deps.core_client, "authorize", authorize)
    client = TestClient(create_test_app())
    client.cookies.set(settings.SESSION_COOKIE, "a" * 43)
    headers = {"X-Tenant-ID": str(a), "X-CSRF-Token": "csrf", "Origin": settings.PUBLIC_URL}
    created = client.post("/api/v1/test-records", json={"title": "shared"}, headers=headers)
    assert created.status_code == 201
    assert client.get("/api/v1/test-records", headers=headers).json()[0]["title"] == "shared"
    assert client.get("/api/v1/test-records", headers={"X-Tenant-ID": str(uuid4())}).status_code == 403


def test_session_storage_encryption_rotation_and_expiry(db_factory, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from src.backend.core import sessions
    from src.backend.models.session import BrowserSession

    monkeypatch.setattr(sessions, "SessionLocal", db_factory)
    sid = "a" * 43
    sessions.save_session(sid, {"access_token": "secret-bearer", "csrf": "secret-csrf"})
    with db_factory.begin() as db:
        row = db.get(BrowserSession, sessions.session_hash(sid))
        assert row and row.id != sid and "secret-bearer" not in row.payload
    assert sessions.load_session(sid)["access_token"] == "secret-bearer"
    next_sid = "b" * 43
    sessions.save_session(next_sid, {"access_token": "second"}, old_sid=sid)
    assert sessions.load_session(sid) == {}
    with db_factory.begin() as db:
        row = db.get(BrowserSession, sessions.session_hash(next_sid))
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert sessions.load_session(next_sid) == {}
    sessions.save_session(next_sid, {})
    assert sessions.load_session(next_sid) == {}


def test_runtime_startup_and_health(db_factory, postgres, monkeypatch):
    from fastapi.testclient import TestClient

    from src.backend import main

    monkeypatch.setattr(main, "engine", db_factory.kw["bind"])
    with TestClient(main.app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        assert client.get("/").status_code == 200
    monkeypatch.setattr(main, "engine", postgres[0])
    with pytest.raises(RuntimeError, match="Runtime role"):
        with TestClient(main.app):
            pass

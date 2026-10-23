"""Local-development auth exercises public behavior; SQLite does not prove RLS."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from src.backend.api import deps
from src.backend.tenancy.context import TenantContext
from tests.support.tenant_example import TestBase as _TestBase
from tests.support.tenant_example import TestRecord as _TestRecord

ROOT = Path(__file__).resolve().parents[1]


def _cli_failure(tmp_path, *, environment, database_url, auth_mode):
    env = os.environ.copy()
    env.update(
        ENVIRONMENT=environment,
        DATABASE_URL=database_url,
        DEV_DATABASE_URL=database_url,
        AUTH_MODE=auth_mode,
        PUBLIC_URL="https://suite.example.test",
        OIDC_ISSUER="https://identity.example.test/issuer",
        OIDC_CLIENT_ID="test-client",
        OIDC_CLIENT_SECRET="test-secret",
        CORE_URL="https://core.example.test",
        SESSION_ENCRYPTION_KEY="4XmJ1t0SXOjkCOaY1-6xD_SmEa_2L6et-F38rNO5FRs=",
    )
    env.pop("MIGRATION_DATABASE_URL", None)
    return subprocess.run(
        [sys.executable, "-m", "src", "check", "--profile", "production"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_production_rejects_local_auth_mode(tmp_path):
    result = _cli_failure(
        tmp_path,
        environment="production",
        database_url="postgresql+psycopg://app:secret@127.0.0.1:5432/app",
        auth_mode="local",
    )
    assert result.returncode != 0
    assert "auth_mode=oidc" in (result.stdout + result.stderr).lower()


def test_production_rejects_sqlite_database(tmp_path):
    result = _cli_failure(
        tmp_path,
        environment="production",
        database_url=f"sqlite:///{tmp_path / 'prod.sqlite3'}",
        auth_mode="oidc",
    )
    assert result.returncode != 0
    assert "sqlite" in (result.stdout + result.stderr).lower() or "postgres" in (result.stdout + result.stderr).lower()
    assert not (tmp_path / "prod.sqlite3").exists()


def test_explicit_local_auth_is_not_silently_overridden_by_production_profile(tmp_path):
    result = _cli_failure(
        tmp_path,
        environment="development",
        database_url="postgresql+psycopg://app:secret@127.0.0.1:5432/app",
        auth_mode="local",
    )
    assert result.returncode != 0
    assert "auth_mode=oidc" in (result.stdout + result.stderr).lower()


@pytest.fixture
def tenant_sqlite(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tenant.sqlite3'}")
    _TestBase.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(deps, "SessionLocal", factory)
    try:
        yield factory
    finally:
        engine.dispose()


def _context(tenant_id):
    return TenantContext(tenant_id, "fixture-user", frozenset({"access", "read", "write"}), frozenset())


def _scoped_session(tenant_id):
    generator = deps.tenant_transaction(_context(tenant_id))
    session = next(generator)
    return generator, session


def test_sqlite_scoped_orm_reads_only_current_tenant(tenant_sqlite):
    tenant_a, tenant_b = uuid4(), uuid4()
    with tenant_sqlite.begin() as db:
        db.add_all(
            [
                _TestRecord(tenant_id=tenant_a, created_by="seed", title="A secret"),
                _TestRecord(tenant_id=tenant_b, created_by="seed", title="B secret"),
            ]
        )

    generator, scoped = _scoped_session(tenant_a)
    try:
        # Deliberately omit a tenant WHERE clause: the SQLite functional guard
        # should apply tenant scope to ORM entity reads.
        records = scoped.scalars(select(_TestRecord)).all()
        assert [row.title for row in records] == ["A secret"]
    finally:
        generator.close()


def test_sqlite_scoped_orm_rejects_cross_tenant_insert_update_and_raw_sql(tenant_sqlite):
    tenant_a, tenant_b = uuid4(), uuid4()
    with tenant_sqlite.begin() as db:
        row = _TestRecord(tenant_id=tenant_b, created_by="fixture-user", title="before")
        db.add(row)
        db.flush()
        row_id = row.id

    with tenant_sqlite() as db:
        detached = db.get(_TestRecord, row_id)
        db.expunge(detached)

    generator, scoped = _scoped_session(tenant_a)
    try:
        scoped.add(_TestRecord(tenant_id=tenant_b, created_by="fixture-user", title="escape"))
        with pytest.raises(ValueError, match="Tenant mismatch"):
            scoped.flush()
    finally:
        generator.close()

    generator, scoped = _scoped_session(tenant_a)
    try:
        scoped.add(detached)
        detached.title = "attempted cross-tenant update"
        with pytest.raises(ValueError, match="Tenant mismatch"):
            scoped.flush()
    finally:
        generator.close()

    generator, scoped = _scoped_session(tenant_a)
    try:
        with pytest.raises(ValueError, match="SQLite tenant sessions require ORM SELECT"):
            scoped.execute(text("SELECT * FROM tenant_test_records"))
    finally:
        generator.close()

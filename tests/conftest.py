import os

os.environ.setdefault("AUTH_MODE", "oidc")

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="session")
def postgres():
    owner_url = os.environ.get("TEST_MIGRATION_DATABASE_URL")
    app_url = os.environ.get("TEST_DATABASE_URL")
    if not owner_url or not app_url:
        if os.environ.get("CI"):
            pytest.fail("CI integration requires TEST_MIGRATION_DATABASE_URL and TEST_DATABASE_URL")
        pytest.skip("Disposable PostgreSQL URLs not configured")
    owner = create_engine(owner_url, hide_parameters=True)
    runtime = create_engine(app_url, hide_parameters=True)
    parsed = make_url(app_url)
    assert parsed.username == "guilarde_app", "Use the dedicated non-owner runtime role"
    with owner.begin() as db:
        exists = db.execute(text("SELECT 1 FROM pg_roles WHERE rolname='guilarde_app'")).scalar()
        if not exists:
            # quote_literal and DBAPI parameter binding prevent password SQL injection.
            password = db.execute(text("SELECT quote_literal(:password)"), {"password": parsed.password}).scalar()
            db.exec_driver_sql(
                "CREATE ROLE guilarde_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD " + password
            )
        db.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
        db.execute(text("GRANT USAGE ON SCHEMA public TO guilarde_app"))
    from src.backend.core.config import settings

    previous = settings.MIGRATION_DATABASE_URL
    settings.MIGRATION_DATABASE_URL = owner_url
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        settings.MIGRATION_DATABASE_URL = previous
    from tests.support.tenant_example import TestBase

    with owner.begin() as db:
        TestBase.metadata.create_all(db)
        db.execute(text("ALTER TABLE tenant_test_records ENABLE ROW LEVEL SECURITY"))
        db.execute(text("ALTER TABLE tenant_test_records FORCE ROW LEVEL SECURITY"))
        db.execute(text("DROP POLICY IF EXISTS tenant_isolation ON tenant_test_records"))
        db.execute(
            text(
                "CREATE POLICY tenant_isolation ON tenant_test_records "
                "USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid) "
                "WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)"
            )
        )
        db.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_test_records TO guilarde_app"))
    yield owner, sessionmaker(bind=runtime, expire_on_commit=False)
    with owner.begin() as db:
        TestBase.metadata.drop_all(db)
    runtime.dispose()
    owner.dispose()


@pytest.fixture
def db_factory(postgres):
    owner, factory = postgres
    with owner.begin() as db:
        db.execute(
            text(
                "TRUNCATE tenant_test_records, browser_sessions, planner_itens, planner_dias, "
                "rotina_execucoes, rotinas, lancamentos, semanas, grupos, iniciativa_participantes, "
                "iniciativas, despesas, orcamentos_despesas, demanda_historico, demandas, "
                "faturas, fontes_custo, perfis_custo"
            )
        )
    return factory

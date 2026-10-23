from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker, with_loader_criteria
from sqlalchemy.pool import StaticPool

from src.backend.core.config import settings

url = make_url(settings.DATABASE_URL)
if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
    Path(url.database).resolve().parent.mkdir(parents=True, exist_ok=True)
kwargs: dict[str, Any] = {}
if url.get_backend_name() == "sqlite":
    kwargs["connect_args"] = {"check_same_thread": False}
    if url.database in (None, "", ":memory:"):
        kwargs["poolclass"] = StaticPool
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, hide_parameters=True, **kwargs)


def safe_database_identifier(database_url: str) -> str:
    """Return a database target without usernames, passwords, or URL options."""
    parsed = make_url(database_url)
    if parsed.get_backend_name() == "sqlite":
        database = Path(parsed.database or ":memory:").name
        return f"sqlite:///{database}"
    host = parsed.host or "localhost"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.get_backend_name()}://{host}{port}/{parsed.database or ''}"


if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def sqlite_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


@event.listens_for(Session, "do_orm_execute")
def sqlite_tenant_queries(state):
    tenant_id = state.session.info.get("tenant_id")
    if tenant_id is None or state.session.get_bind().dialect.name != "sqlite":
        return
    if not state.is_orm_statement or not state.is_select:
        raise ValueError(
            "SQLite tenant sessions require ORM SELECT or instance changes; use PostgreSQL for raw/bulk SQL"
        )
    from src.backend.models.base import TenantRecord

    state.statement = state.statement.options(
        with_loader_criteria(TenantRecord, lambda model: model.tenant_id == tenant_id, include_aliases=True)
    )


@event.listens_for(Session, "before_flush")
def sqlite_tenant_writes(session, _context, _instances):
    tenant_id = session.info.get("tenant_id")
    if tenant_id is None or session.get_bind().dialect.name != "sqlite":
        return
    from src.backend.models.base import TenantRecord

    for item in session.new | session.dirty | session.deleted:
        if isinstance(item, TenantRecord):
            history = inspect(item).attrs.tenant_id.history
            if item.tenant_id != tenant_id or any(old != tenant_id for old in history.deleted):
                raise ValueError("Tenant mismatch in SQLite development session")


def verify_database(target_engine=None):
    bind = target_engine if target_engine is not None else engine
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from src.backend.core.config import BASE_DIR

    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BASE_DIR / "src/backend/migrations"))
    expected = set(ScriptDirectory.from_config(config).get_heads())
    with bind.connect() as db:
        if bind.dialect.name == "postgresql":
            role = db.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")).one()
            owns = db.execute(
                text("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner=current_user")
            ).scalar()
            if role.rolsuper or role.rolbypassrls or owns:
                raise RuntimeError("Runtime role must not own tenant tables or bypass RLS")
        actual = set(db.execute(text("SELECT version_num FROM alembic_version")).scalars())
        if actual != expected:
            raise RuntimeError("Database migrations are not current; run python -m src migrate for this profile")

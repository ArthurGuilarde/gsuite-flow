from alembic import context
from sqlalchemy import create_engine, pool

from src.backend.core.config import settings
from src.backend.models import Base

config = context.config
url = settings.MIGRATION_DATABASE_URL or settings.DATABASE_URL

if settings.ENVIRONMENT == "production" and not settings.MIGRATION_DATABASE_URL:
    raise RuntimeError("Production migrations require MIGRATION_DATABASE_URL")

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.backend.api.auth import router as auth_router
from src.backend.api.v1.router import api_v1_router
from src.backend.core.config import FRONTEND_DIR, safe_public_address, settings
from src.backend.core.database import engine, safe_database_identifier, verify_database
from src.backend.core.error_handlers import register_error_handlers
from src.backend.core.local_guard import LocalOnlyMiddleware
from src.backend.core.logging import setup_logging
from src.backend.core.middleware import RequestIdAndLoggingMiddleware
from src.backend.core.rate_limit import RateLimitMiddleware
from src.backend.core.security_headers import SecurityHeadersMiddleware
from src.backend.core.sessions import ServerSessionMiddleware

setup_logging()
logger = logging.getLogger(__name__)

if settings.ENVIRONMENT == "production" and settings.MIGRATION_DATABASE_URL:
    raise RuntimeError("Production runtime must not receive migration credentials")


@asynccontextmanager
async def lifespan(_app):
    # Never migrate or seed identities on worker startup.
    logger.info(
        "Application startup profile=%s auth=%s address=%s database=%s",
        settings.APP_PROFILE,
        settings.AUTH_MODE,
        safe_public_address(settings.PUBLIC_URL),
        safe_database_identifier(settings.DATABASE_URL),
    )
    verify_database(engine)
    yield
    engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
)
register_error_handlers(app)
app.add_middleware(ServerSessionMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIdAndLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(LocalOnlyMiddleware)


@app.middleware("http")
async def private_responses(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/auth", "/api")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready():
    try:
        with engine.connect() as db:
            db.execute(text("SELECT 1 FROM alembic_version"))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database unavailable") from exc
    return {"status": "ready"}


if settings.ENVIRONMENT == "development" and settings.AUTH_MODE == "local":
    from src.backend.api.dev_auth import router as dev_router

    app.include_router(dev_router)
app.include_router(auth_router)
app.include_router(api_v1_router)
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

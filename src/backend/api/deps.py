import secrets
from urllib.parse import urlparse
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from src.backend.core.config import is_loopback, settings
from src.backend.core.database import SessionLocal
from src.backend.integrations.guilarde.client import core_client
from src.backend.integrations.guilarde.local import local_authorize, local_principal
from src.backend.integrations.guilarde.oidc import validate_access_token
from src.backend.tenancy.context import TenantContext


async def current_identity(request: Request):
    if settings.AUTH_MODE == "local":
        return local_principal(request.session.get("dev_user"))
    token = request.session.get("access_token")
    if not token:
        raise HTTPException(401, "Authentication required")
    return await run_in_threadpool(validate_access_token, token)


def csrf_check(request: Request):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        expected = request.session.get("csrf", "")
        actual = request.headers.get("X-CSRF-Token", "")
        if not expected or not secrets.compare_digest(expected, actual):
            raise HTTPException(403, "Invalid CSRF token")
        origin = request.headers.get("origin", "")
        valid_origin = origin == settings.PUBLIC_URL.rstrip("/")
        if settings.AUTH_MODE == "local":
            try:
                parsed, public = urlparse(origin), urlparse(settings.PUBLIC_URL)
                valid_origin = (
                    parsed.scheme == "http"
                    and is_loopback(parsed.hostname)
                    and (parsed.port or 80) == (public.port or 80)
                    and not parsed.username
                    and not parsed.password
                    and not parsed.query
                    and not parsed.fragment
                    and parsed.path == ""
                )
            except ValueError:
                valid_origin = False
        if not valid_origin:
            raise HTTPException(403, "Invalid request origin")


def require_permission(permission: str):
    async def dependency(
        request: Request, tenant_id: UUID = Header(alias="X-Tenant-ID"), principal=Depends(current_identity)
    ):
        csrf_check(request)
        if settings.AUTH_MODE == "local":
            grant = local_authorize(principal.sub, tenant_id)
        else:
            grant = await core_client.authorize(request.session["access_token"], tenant_id, permission)
        if (
            not grant.allowed
            or grant.sub != principal.sub
            or grant.tenant_id != tenant_id
            or grant.app_id != settings.APP_ID
            or not {"access", permission}.issubset(grant.permissions)
        ):
            raise HTTPException(403, "Tenant or permission denied")
        return TenantContext(tenant_id, principal.sub, frozenset(grant.permissions), frozenset(grant.features))

    return dependency


async def read_context(ctx=Depends(require_permission("read"))):
    return ctx


async def write_context(ctx=Depends(require_permission("write"))):
    return ctx


def tenant_transaction(ctx: TenantContext):
    # SET LOCAL survives only this transaction; no commit in repositories/services.
    with SessionLocal.begin() as db:
        if db.get_bind().dialect.name == "sqlite":
            db.info["tenant_id"] = ctx.tenant_id
        else:
            db.execute(text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(ctx.tenant_id)})
            db.execute(text("SELECT set_config('app.subject', :sub, true)"), {"sub": ctx.sub})
        yield db


def read_db(ctx=Depends(read_context)):
    yield from tenant_transaction(ctx)


def write_db(ctx=Depends(write_context)):
    yield from tenant_transaction(ctx)


def require_feature(feature: str):
    async def dependency(ctx=Depends(read_context)):
        if feature not in ctx.features:
            raise HTTPException(403, "Feature unavailable")
        return ctx

    return dependency

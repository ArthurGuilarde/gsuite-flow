import secrets

import httpx
from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from joserfc.errors import JoseError
from starlette.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse

from src.backend.api.deps import csrf_check, current_identity
from src.backend.core.config import settings
from src.backend.integrations.guilarde.client import core_client
from src.backend.integrations.guilarde.local import local_tenants
from src.backend.integrations.guilarde.oidc import oauth, validate_access_token

router = APIRouter(prefix="/auth", tags=["identity"])


@router.get("/login")
async def login(request: Request):
    if settings.AUTH_MODE == "local":
        return RedirectResponse("/auth/dev/login", status_code=303)
    if not settings.OIDC_CLIENT_ID or not settings.OIDC_CLIENT_SECRET:
        raise HTTPException(503, "OIDC provider not configured")
    return await oauth.guilarde.authorize_redirect(request, settings.PUBLIC_URL.rstrip("/") + "/auth/callback")


@router.get("/callback")
async def callback(request: Request):
    if settings.AUTH_MODE != "oidc":
        raise HTTPException(404, "Not found")
    try:
        token = await oauth.guilarde.authorize_access_token(request)
        principal = await run_in_threadpool(validate_access_token, token["access_token"])
        if not token.get("userinfo") or token["userinfo"].get("sub") != principal.sub:
            raise HTTPException(401, "OIDC subject mismatch")
    except (OAuthError, JoseError, KeyError) as exc:
        request.session.clear()
        raise HTTPException(401, "OIDC callback rejected") from exc
    except HTTPException:
        request.session.clear()
        raise
    except httpx.HTTPError as exc:
        request.session.clear()
        raise HTTPException(503, "Identity provider unavailable") from exc
    request.session.clear()
    request.scope["rotate_session"] = True
    request.session.update(access_token=token["access_token"], csrf=secrets.token_urlsafe(32))
    return RedirectResponse("/", status_code=303)


@router.get("/session")
async def session(request: Request, identity=Depends(current_identity)):
    return {"sub": identity.sub, "name": identity.name, "csrf_token": request.session["csrf"]}


@router.get("/tenants")
async def tenants(request: Request, _identity=Depends(current_identity)):
    if settings.AUTH_MODE == "local":
        return {"tenants": local_tenants(_identity.sub)}
    return {"tenants": await core_client.tenants(request.session["access_token"])}


@router.post("/logout", status_code=204)
async def logout(request: Request):
    csrf_check(request)
    request.session.clear()
    return Response(status_code=204)

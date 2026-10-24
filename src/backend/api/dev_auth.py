import secrets
from html import escape

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict
from starlette.responses import HTMLResponse

from src.backend.api.deps import csrf_check
from src.backend.integrations.guilarde.local import USERS, local_only, local_principal

router = APIRouter(prefix="/auth/dev", tags=["development-only"])


class DevLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str


@router.get("/login", response_class=HTMLResponse)
def page():
    local_only()
    names = ", ".join(escape(key) for key in USERS)
    return HTMLResponse(
        f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Login local · GFlow</title>'
        '<link rel="stylesheet" href="/css/suite.css"></head>'
        '<body><main class="login"><div class="login-marca"><span class="marca-logo" aria-hidden="true">G</span>'
        "<span>GFlow</span></div>"
        '<span class="login-selo">Somente desenvolvimento</span>'
        "<h1>Desenvolvimento local</h1>"
        f'<p class="login-aviso">Identidades fictícias: {names}. Este acesso não usa Authentik ou Core.</p>'
        '<form id="dev-login"><label class="campo"><span>Usuário</span><select id="dev-user"></select></label>'
        '<button type="submit">Entrar</button></form><p id="dev-status" role="status"></p>'
        '<script src="/js/dev-login.js" type="module"></script></main></body></html>'
    )


@router.get("/config")
def config(request: Request):
    local_only()
    request.session.setdefault("csrf", secrets.token_urlsafe(32))
    return {
        "users": [{"id": key, "name": value[0]} for key, value in USERS.items()],
        "csrf_token": request.session["csrf"],
    }


@router.post("/login", status_code=204)
def login(body: DevLogin, request: Request):
    local_only()
    csrf_check(request)
    local_principal(body.user_id)
    request.session.clear()
    request.scope["rotate_session"] = True
    request.session.update(dev_user=body.user_id, csrf=secrets.token_urlsafe(32))
    from fastapi import Response

    return Response(status_code=204)

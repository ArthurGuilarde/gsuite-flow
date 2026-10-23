"""Tratamento global e padronizado de exceções da aplicação FastAPI."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.backend.core.exceptions import DomainError
from src.backend.core.logging import get_request_id

logger = logging.getLogger("src.backend.errors")


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Converte exceções de domínio de negócio em respostas HTTP semânticas."""
    headers: dict[str, str] = {}
    if exc.status_code == 401:
        headers["WWW-Authenticate"] = "Bearer"

    req_id = getattr(request.state, "request_id", None) or get_request_id()
    if req_id:
        headers["X-Request-ID"] = req_id

    logger.warning(
        "Erro de domínio [%s]: %s (em %s %s)",
        exc.__class__.__name__,
        exc.message,
        request.method,
        request.url.path,
        extra={"status_code": exc.status_code, "domain_error": exc.__class__.__name__},
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
        headers=headers or None,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Trata erros de validação de schemas Pydantic/FastAPI com envelope padronizado."""
    req_id = getattr(request.state, "request_id", None) or get_request_id()
    headers: dict[str, str] = {}
    if req_id:
        headers["X-Request-ID"] = req_id

    logger.warning(
        "Erro de validação de payload: %s %s (%d inconformidades)",
        request.method,
        request.url.path,
        len(exc.errors()),
        extra={"status_code": 422, "validation_count": len(exc.errors())},
    )

    return JSONResponse(
        status_code=422,
        content={
            "detail": [{k: v for k, v in error.items() if k not in {"input", "ctx"}} for error in exc.errors()],
            "message": "Dados de requisição inválidos.",
        },
        headers=headers or None,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Padroniza exceções HTTP nativas do framework (ex: 404 Not Found, 405)."""
    req_id = getattr(request.state, "request_id", None) or get_request_id()
    headers = dict(exc.headers) if exc.headers else {}
    if req_id:
        headers["X-Request-ID"] = req_id

    if exc.status_code >= 500:
        logger.error("Exceção HTTP %d em %s: %s", exc.status_code, request.url.path, exc.detail)
    else:
        logger.warning("Exceção HTTP %d em %s: %s", exc.status_code, request.url.path, exc.detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers or None,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Captura falhas críticas inesperadas (500), ocultando tracebacks sensíveis em produção."""
    req_id = getattr(request.state, "request_id", None) or get_request_id() or "unknown"
    headers = {"X-Request-ID": req_id}

    logger.exception(
        "Exceção interna não tratada ao processar %s %s: %s",
        request.method,
        request.url.path,
        exc,
        extra={"status_code": 500, "request_id": req_id},
    )

    detail = "Erro interno do servidor."

    return JSONResponse(
        status_code=500,
        content={"detail": detail, "request_id": req_id},
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Registra todos os manipuladores de exceção na instância da aplicação FastAPI."""
    app.add_exception_handler(DomainError, domain_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

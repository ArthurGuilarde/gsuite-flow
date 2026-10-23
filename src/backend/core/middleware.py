"""Middlewares de observabilidade, correlação de requisições e logging de acesso."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.backend.core.config import settings
from src.backend.core.logging import reset_request_id, set_request_id

logger = logging.getLogger("src.backend.access")


class RequestIdAndLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware que gerencia o ciclo de vida do Request ID e emite logs estruturados de acesso.

    1. Extrai ou gera um identificador único de requisição (`X-Request-ID`).
    2. Injeta o identificador no contexto assíncrono e no cabeçalho de resposta.
    3. Mede o tempo de resposta em milissegundos.
    4. Emite log estruturado com método, caminho, status HTTP e duração.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extrai ou gera o Request ID (reutiliza se enviado pelo cliente/proxy)
        client_request_id = request.headers.get("X-Request-ID", "").strip()
        request_id = (
            client_request_id
            if client_request_id
            and len(client_request_id) <= 128
            and client_request_id.isascii()
            and all(c.isalnum() or c in "-_" for c in client_request_id)
            else str(uuid.uuid4())
        )

        # Define no contexto assíncrono para os formatadores de log e na requisição
        token = set_request_id(request_id)
        request.state.request_id = request_id

        # Captura IP do cliente (considerando cabeçalho X-Forwarded-For se atrás de proxy Nginx)
        client_ip = request.client.host if request.client else "unknown"

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                "Falha não tratada ao processar requisição: %s %s - %s (%.2fms)",
                request.method,
                request.url.path,
                exc,
                duration_ms,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                },
                exc_info=True,
            )
            raise
        finally:
            reset_request_id(token)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Garante a presença do cabeçalho de rastreamento na resposta
        response.headers["X-Request-ID"] = request_id

        # Determina o nível semântico do log
        path = request.url.path
        is_api_route = path.startswith(settings.API_V1_STR)

        log_extra = {
            "method": request.method,
            "path": path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
        }

        log_message = f"{request.method} {path} - {response.status_code} ({duration_ms:.2f}ms)"

        if response.status_code >= 500:
            logger.error(log_message, extra=log_extra)
        elif response.status_code >= 400:
            logger.warning(log_message, extra=log_extra)
        elif is_api_route:
            logger.info(log_message, extra=log_extra)
        else:
            # Arquivos estáticos e documentação não poluem o log em nível INFO
            logger.debug(log_message, extra=log_extra)

        return response

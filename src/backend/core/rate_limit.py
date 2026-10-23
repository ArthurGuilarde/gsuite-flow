"""Controle de taxa de requisições (Rate Limiting) em memória com janela deslizante.

Protege endpoints sensíveis (login/troca de senha) contra ataques de força bruta
e endpoints de API contra abuso/scraping, sem dependência externa de Redis.
"""

import logging
import threading
import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from src.backend.core.config import settings

logger = logging.getLogger("src.backend.security")


class InMemoryRateLimiter:
    """Implementa limitador de taxa baseado em janela deslizante (Sliding Window).

    Armazena os timestamps das requisições recentes e remove automaticamente
    registros expirados para evitar vazamento de memória.
    """

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str, max_requests: int, window_seconds: float = 60.0) -> tuple[bool, int, int]:
        """Verifica se a chave excedeu o limite dentro da janela de tempo.

        Args:
            key: Identificador único (ex: "auth:192.168.1.1").
            max_requests: Número máximo permitido de requisições na janela.
            window_seconds: Tamanho da janela deslizante em segundos.

        Returns:
            Uma tupla (permitido: bool, retry_after: int, remaining: int).
        """
        now = time.monotonic()
        cutoff = now - window_seconds

        with self._lock:
            timestamps = self._requests[key]

            # Remove timestamps fora da janela deslizante
            valid_timestamps = [t for t in timestamps if t > cutoff]
            self._requests[key] = valid_timestamps

            # Limpeza preventiva se o dicionário crescer excessivamente
            if len(self._requests) > 5000:
                self._prune_stale_keys(cutoff)

            if len(valid_timestamps) >= max_requests:
                oldest = valid_timestamps[0]
                retry_after = max(1, int(window_seconds - (now - oldest)) + 1)
                return False, retry_after, 0

            # Registra a requisição atual
            valid_timestamps.append(now)
            remaining = max(0, max_requests - len(valid_timestamps))
            return True, 0, remaining

    def _prune_stale_keys(self, cutoff: float) -> None:
        """Remove entradas vazias ou totalmente expiradas do mapa em memória."""
        stale_keys = [k for k, ts in self._requests.items() if not ts or max(ts) <= cutoff]
        for k in stale_keys:
            self._requests.pop(k, None)

    def reset(self, key: str | None = None) -> None:
        """Limpa o histórico de uma chave ou reseta todo o limitador (útil em testes)."""
        with self._lock:
            if key is not None:
                self._requests.pop(key, None)
            else:
                self._requests.clear()


# Instância global singleton do limitador em memória
limiter = InMemoryRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware HTTP para fiscalização de limites de taxa de requisições por IP."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        path = request.url.path
        api_prefix = settings.API_V1_STR

        # Isenta rotas de saúde e arquivos estáticos
        if not path.startswith((api_prefix, "/auth")):
            return await call_next(request)

        # Extrai IP do cliente (respeitando X-Forwarded-For de proxy Nginx)
        client_ip = request.client.host if request.client else "unknown"

        # Define política de acordo com a sensibilidade do endpoint
        is_auth_route = path.startswith("/auth/")
        if is_auth_route:
            rule_key = f"auth:{client_ip}"
            max_requests = settings.RATE_LIMIT_LOGIN_PER_MINUTE
        else:
            rule_key = f"api:{client_ip}"
            max_requests = settings.RATE_LIMIT_API_PER_MINUTE

        allowed, retry_after, remaining = limiter.check(rule_key, max_requests=max_requests, window_seconds=60.0)

        if not allowed:
            logger.warning(
                "Rate limit excedido para %s na rota %s (retry_after=%ds)",
                client_ip,
                path,
                retry_after,
                extra={"client_ip": client_ip, "path": path, "retry_after": retry_after},
            )
            headers = {
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(retry_after),
            }
            # Preserva Request ID se gerado/atribuído
            req_id = getattr(request.state, "request_id", None)
            if req_id:
                headers["X-Request-ID"] = req_id

            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Muitas requisições. Aguarde {retry_after} segundos antes de tentar novamente.",
                    "retry_after": retry_after,
                },
                headers=headers,
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse

from src.backend.core.config import is_loopback, settings


class LocalOnlyMiddleware:
    """Reject network access to the local fixture adapter, including forged Host headers."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and settings.AUTH_MODE == "local":
            connection = HTTPConnection(scope)
            peer = scope.get("client")
            if not peer or not is_loopback(peer[0]) or not is_loopback(connection.url.hostname):
                response = JSONResponse({"detail": "Local development is restricted to loopback"}, status_code=403)
                return await response(scope, receive, send)
        await self.app(scope, receive, send)

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import MutableHeaders
from starlette.requests import HTTPConnection

from src.backend.core.config import settings
from src.backend.core.database import SessionLocal
from src.backend.models.session import BrowserSession

# Development may use a temporary key; production config requires a persistent secret.
cipher = Fernet(settings.SESSION_ENCRYPTION_KEY.encode() if settings.SESSION_ENCRYPTION_KEY else Fernet.generate_key())


def session_hash(sid):
    return hashlib.sha256(sid.encode()).hexdigest()


def load_session(sid):
    with SessionLocal() as db:
        row = db.get(BrowserSession, session_hash(sid))
        if not row:
            return {}
        expires = row.expires_at.replace(tzinfo=UTC) if row.expires_at.tzinfo is None else row.expires_at
        if expires <= datetime.now(UTC):
            return {}
        try:
            return json.loads(cipher.decrypt(row.payload.encode()))
        except (InvalidToken, ValueError):
            return {}


def save_session(sid, data, old_sid=None):
    with SessionLocal.begin() as db:
        if old_sid:
            db.execute(delete(BrowserSession).where(BrowserSession.id == session_hash(old_sid)))
        if data:
            db.merge(
                BrowserSession(
                    id=session_hash(sid),
                    payload=cipher.encrypt(json.dumps(data).encode()).decode(),
                    expires_at=datetime.now(UTC) + timedelta(seconds=settings.SESSION_TTL_SECONDS),
                )
            )
        else:
            db.execute(delete(BrowserSession).where(BrowserSession.id == session_hash(sid)))


class ServerSessionMiddleware:
    """Opaque cookie; OAuth state, PKCE and tokens remain encrypted in PostgreSQL."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        connection = HTTPConnection(scope)
        sid = connection.cookies.get(settings.SESSION_COOKIE, "")
        # Anonymous/static/health requests do not connect to session storage.
        valid_sid = len(sid) == 43 and all(c.isalnum() or c in "-_" for c in sid)
        scope["session"] = await run_in_threadpool(load_session, sid) if valid_sid else {}
        original = json.dumps(scope["session"], sort_keys=True)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                changed = json.dumps(scope["session"], sort_keys=True) != original
                rotate = scope.get("rotate_session", False)
                if changed or rotate:
                    old_sid = sid if valid_sid else None
                    new_sid = secrets.token_urlsafe(32) if rotate or not valid_sid else sid
                    await run_in_threadpool(save_session, new_sid, scope["session"], old_sid if rotate else None)
                    headers = MutableHeaders(scope=message)
                    secure = "; Secure" if settings.COOKIE_SECURE else ""
                    value = new_sid if scope["session"] else ""
                    age = settings.SESSION_TTL_SECONDS if scope["session"] else 0
                    headers.append(
                        "set-cookie",
                        f"{settings.SESSION_COOKIE}={value}; Path=/; HttpOnly; SameSite=Lax; Max-Age={age}{secure}",
                    )
            await send(message)

        await self.app(scope, receive, send_wrapper)

from datetime import UTC, datetime

from sqlalchemy import delete

from src.backend.core.database import SessionLocal
from src.backend.models.session import BrowserSession

if __name__ == "__main__":
    with SessionLocal.begin() as db:
        db.execute(delete(BrowserSession).where(BrowserSession.expires_at < datetime.now(UTC)))

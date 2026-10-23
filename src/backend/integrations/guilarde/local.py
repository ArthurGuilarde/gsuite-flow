"""Development fixtures, not an identity provider or a production authorization source."""

from uuid import UUID

from fastapi import HTTPException

from src.backend.core.config import settings
from src.backend.integrations.guilarde.contracts import Authorization, Principal, TenantSummary

TENANT_A = UUID("11111111-1111-4111-8111-111111111111")
TENANT_B = UUID("22222222-2222-4222-8222-222222222222")
USERS = {
    "editor-a": ("Editor do espaço A", TENANT_A, frozenset({"access", "read", "write"})),
    "reader-a": ("Leitor do espaço A", TENANT_A, frozenset({"access", "read"})),
    "editor-b": ("Editor do espaço B", TENANT_B, frozenset({"access", "read", "write"})),
}


def local_only():
    if settings.ENVIRONMENT != "development" or settings.AUTH_MODE != "local":
        raise HTTPException(404, "Not found")


def local_principal(user_id: str | None) -> Principal:
    local_only()
    if user_id not in USERS:
        raise HTTPException(401, "Development login required")
    return Principal(sub=user_id, name=USERS[user_id][0])


def local_tenants(user_id: str) -> list[TenantSummary]:
    local_principal(user_id)
    tenant = USERS[user_id][1]
    return [TenantSummary(id=tenant, name="Espaço A" if tenant == TENANT_A else "Espaço B")]


def local_authorize(user_id: str, tenant_id: UUID) -> Authorization:
    local_principal(user_id)
    allowed = USERS[user_id][1] == tenant_id
    return Authorization(
        sub=user_id,
        tenant_id=tenant_id,
        app_id=settings.APP_ID,
        allowed=allowed,
        permissions=set(USERS[user_id][2]) if allowed else set(),
        features=set(),
    )

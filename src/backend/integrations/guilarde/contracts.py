from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Principal(BaseModel):
    sub: str
    name: str = ""


class Authorization(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sub: str
    tenant_id: UUID
    app_id: str
    allowed: bool
    permissions: set[str]
    features: set[str] = set()


class TenantSummary(BaseModel):
    id: UUID
    name: str

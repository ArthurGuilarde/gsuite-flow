from uuid import UUID

from pydantic import BaseModel


class ContextView(BaseModel):
    tenant_id: UUID
    permissions: list[str]
    features: list[str]

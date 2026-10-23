from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TenantContext:
    tenant_id: UUID
    sub: str
    permissions: frozenset[str]
    features: frozenset[str]

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from src.backend.models.demandas import Demanda, DemandaEvento

_RANK = case((Demanda.prioridade == "ALTA", 0), (Demanda.prioridade == "MEDIA", 1), else_=2)


def obter_demanda(db: Session, tenant_id: UUID, demanda_id: UUID) -> Demanda | None:
    stmt = select(Demanda).where(Demanda.tenant_id == tenant_id, Demanda.id == demanda_id)
    return db.scalars(stmt).first()


def listar_demandas(
    db: Session,
    tenant_id: UUID,
    status: str | None = None,
    grupo_id: UUID | None = None,
    solicitante_sub: str | None = None,
) -> Sequence[Demanda]:
    stmt = select(Demanda).where(Demanda.tenant_id == tenant_id)
    if status is not None:
        stmt = stmt.where(Demanda.status == status)
    if grupo_id is not None:
        stmt = stmt.where(Demanda.grupo_id == grupo_id)
    if solicitante_sub is not None:
        stmt = stmt.where(Demanda.solicitante_sub == solicitante_sub)
    return db.scalars(stmt.order_by(_RANK, Demanda.created_at, Demanda.id)).all()


def listar_eventos(db: Session, tenant_id: UUID, demanda_id: UUID) -> Sequence[DemandaEvento]:
    stmt = select(DemandaEvento).where(DemandaEvento.tenant_id == tenant_id, DemandaEvento.demanda_id == demanda_id)
    return db.scalars(stmt.order_by(DemandaEvento.created_at, DemandaEvento.id)).all()

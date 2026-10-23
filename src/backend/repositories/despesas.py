from collections.abc import Collection, Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.backend.models.despesas import Despesa, OrcamentoDespesa
from src.backend.models.finops import Fatura, Iniciativa


def listar_despesas(
    db: Session, tenant_id: UUID, *, status: str | None = None, categoria: str | None = None
) -> Sequence[Despesa]:
    stmt = select(Despesa).where(Despesa.tenant_id == tenant_id)
    if status is not None:
        stmt = stmt.where(Despesa.status_auditoria == status)
    if categoria is not None:
        stmt = stmt.where(Despesa.categoria == categoria)
    return db.scalars(stmt.order_by(Despesa.nome, Despesa.id)).all()


def obter_despesa(db: Session, tenant_id: UUID, despesa_id: UUID) -> Despesa | None:
    stmt = select(Despesa).where(Despesa.tenant_id == tenant_id, Despesa.id == despesa_id)
    return db.scalars(stmt).first()


def listar_despesas_da_fonte(db: Session, tenant_id: UUID, fonte_id: UUID) -> Sequence[Despesa]:
    stmt = select(Despesa).where(Despesa.tenant_id == tenant_id, Despesa.fonte_id == fonte_id)
    return db.scalars(stmt).all()


def listar_iniciativas_vinculadas(db: Session, tenant_id: UUID, despesa_id: UUID | None = None) -> Sequence[Iniciativa]:
    """Iniciativas ligadas a alguma despesa (ou a uma despesa específica)."""
    stmt = select(Iniciativa).where(Iniciativa.tenant_id == tenant_id)
    if despesa_id is not None:
        stmt = stmt.where(Iniciativa.despesa_id == despesa_id)
    else:
        stmt = stmt.where(Iniciativa.despesa_id.is_not(None))
    return db.scalars(stmt).all()


def listar_faturas_das_fontes(db: Session, tenant_id: UUID, fonte_ids: Collection[UUID]) -> Sequence[Fatura]:
    if not fonte_ids:
        return []
    stmt = select(Fatura).where(Fatura.tenant_id == tenant_id, Fatura.fonte_id.in_(list(fonte_ids)))
    return db.scalars(stmt).all()


def listar_orcamentos(
    db: Session, tenant_id: UUID, *, de: date | None = None, ate: date | None = None
) -> Sequence[OrcamentoDespesa]:
    stmt = select(OrcamentoDespesa).where(OrcamentoDespesa.tenant_id == tenant_id)
    if de is not None:
        stmt = stmt.where(OrcamentoDespesa.competencia >= de)
    if ate is not None:
        stmt = stmt.where(OrcamentoDespesa.competencia <= ate)
    return db.scalars(stmt.order_by(OrcamentoDespesa.competencia)).all()


def obter_orcamento(db: Session, tenant_id: UUID, competencia: date) -> OrcamentoDespesa | None:
    stmt = select(OrcamentoDespesa).where(
        OrcamentoDespesa.tenant_id == tenant_id, OrcamentoDespesa.competencia == competencia
    )
    return db.scalars(stmt).first()

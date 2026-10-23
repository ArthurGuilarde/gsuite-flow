from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.backend.models.capacidade import Semana
from src.backend.models.rotinas import Rotina, RotinaExecucao


def listar_rotinas(db: Session, tenant_id: UUID, *, ativo: bool | None = None) -> Sequence[Rotina]:
    stmt = select(Rotina).where(Rotina.tenant_id == tenant_id)
    if ativo is not None:
        stmt = stmt.where(Rotina.ativo.is_(ativo))
    return db.scalars(stmt.order_by(Rotina.ordem, Rotina.titulo, Rotina.id)).all()


def obter_rotina(db: Session, tenant_id: UUID, rotina_id: UUID) -> Rotina | None:
    return db.scalars(select(Rotina).where(Rotina.tenant_id == tenant_id, Rotina.id == rotina_id)).first()


def listar_semanas(db: Session, tenant_id: UUID) -> Sequence[Semana]:
    stmt = select(Semana).where(Semana.tenant_id == tenant_id).order_by(Semana.created_at.desc(), Semana.id)
    return db.scalars(stmt).all()


def obter_semana(db: Session, tenant_id: UUID, semana_id: UUID) -> Semana | None:
    return db.scalars(select(Semana).where(Semana.tenant_id == tenant_id, Semana.id == semana_id)).first()


def listar_execucoes(
    db: Session, tenant_id: UUID, *, semana_id: UUID | None = None, rotina_id: UUID | None = None
) -> Sequence[RotinaExecucao]:
    stmt = select(RotinaExecucao).where(RotinaExecucao.tenant_id == tenant_id)
    if semana_id is not None:
        stmt = stmt.where(RotinaExecucao.semana_id == semana_id)
    if rotina_id is not None:
        stmt = stmt.where(RotinaExecucao.rotina_id == rotina_id)
    return db.scalars(stmt).all()


def obter_execucao(
    db: Session, tenant_id: UUID, rotina_id: UUID, semana_id: UUID, ocorrencia: str
) -> RotinaExecucao | None:
    stmt = select(RotinaExecucao).where(
        RotinaExecucao.tenant_id == tenant_id,
        RotinaExecucao.rotina_id == rotina_id,
        RotinaExecucao.semana_id == semana_id,
        RotinaExecucao.ocorrencia == ocorrencia,
    )
    return db.scalars(stmt).first()

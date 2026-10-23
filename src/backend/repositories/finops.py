from collections.abc import Collection, Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.backend.models.finops import Fatura, FonteCusto, Iniciativa, IniciativaParticipante, PerfilCusto


def listar_perfis(db: Session, tenant_id: UUID) -> Sequence[PerfilCusto]:
    stmt = select(PerfilCusto).where(PerfilCusto.tenant_id == tenant_id)
    return db.scalars(stmt.order_by(PerfilCusto.nome, PerfilCusto.id)).all()


def obter_perfil(db: Session, tenant_id: UUID, perfil_id: UUID) -> PerfilCusto | None:
    stmt = select(PerfilCusto).where(PerfilCusto.tenant_id == tenant_id, PerfilCusto.id == perfil_id)
    return db.scalars(stmt).first()


def listar_fontes(db: Session, tenant_id: UUID) -> Sequence[FonteCusto]:
    stmt = select(FonteCusto).where(FonteCusto.tenant_id == tenant_id)
    return db.scalars(stmt.order_by(FonteCusto.nome, FonteCusto.id)).all()


def obter_fonte(db: Session, tenant_id: UUID, fonte_id: UUID) -> FonteCusto | None:
    stmt = select(FonteCusto).where(FonteCusto.tenant_id == tenant_id, FonteCusto.id == fonte_id)
    return db.scalars(stmt).first()


def listar_faturas(
    db: Session,
    tenant_id: UUID,
    *,
    fonte_id: UUID | None = None,
    de: date | None = None,
    ate: date | None = None,
) -> Sequence[Fatura]:
    stmt = select(Fatura).where(Fatura.tenant_id == tenant_id)
    if fonte_id is not None:
        stmt = stmt.where(Fatura.fonte_id == fonte_id)
    if de is not None:
        stmt = stmt.where(Fatura.competencia >= de)
    if ate is not None:
        stmt = stmt.where(Fatura.competencia <= ate)
    return db.scalars(stmt).all()


def obter_fatura(db: Session, tenant_id: UUID, fatura_id: UUID) -> Fatura | None:
    stmt = select(Fatura).where(Fatura.tenant_id == tenant_id, Fatura.id == fatura_id)
    return db.scalars(stmt).first()


def listar_iniciativas(db: Session, tenant_id: UUID, *, tipo: str | None = None) -> Sequence[Iniciativa]:
    stmt = select(Iniciativa).where(Iniciativa.tenant_id == tenant_id)
    if tipo is not None:
        stmt = stmt.where(Iniciativa.tipo == tipo)
    return db.scalars(stmt).all()


def listar_iniciativas_da_fonte(db: Session, tenant_id: UUID, fonte_id: UUID) -> Sequence[Iniciativa]:
    stmt = select(Iniciativa).where(Iniciativa.tenant_id == tenant_id, Iniciativa.fonte_id == fonte_id)
    return db.scalars(stmt).all()


def obter_iniciativa(db: Session, tenant_id: UUID, iniciativa_id: UUID) -> Iniciativa | None:
    stmt = select(Iniciativa).where(Iniciativa.tenant_id == tenant_id, Iniciativa.id == iniciativa_id)
    return db.scalars(stmt).first()


def listar_participantes(
    db: Session, tenant_id: UUID, iniciativa_ids: Collection[UUID] | None = None
) -> Sequence[IniciativaParticipante]:
    stmt = select(IniciativaParticipante).where(IniciativaParticipante.tenant_id == tenant_id)
    if iniciativa_ids is not None:
        if not iniciativa_ids:
            return []
        stmt = stmt.where(IniciativaParticipante.iniciativa_id.in_(list(iniciativa_ids)))
    return db.scalars(stmt.order_by(IniciativaParticipante.ordem, IniciativaParticipante.id)).all()

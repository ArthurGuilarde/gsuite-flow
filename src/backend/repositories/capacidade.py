from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.backend.models.capacidade import Grupo, Lancamento, Semana


def listar_grupos(db: Session, tenant_id: UUID, *, somente_ativos: bool = False) -> Sequence[Grupo]:
    stmt = select(Grupo).where(Grupo.tenant_id == tenant_id)
    if somente_ativos:
        stmt = stmt.where(Grupo.ativo.is_(True))
    return db.scalars(stmt.order_by(Grupo.categoria, Grupo.nome)).all()


def obter_grupo(db: Session, tenant_id: UUID, grupo_id: UUID) -> Grupo | None:
    return db.scalars(select(Grupo).where(Grupo.tenant_id == tenant_id, Grupo.id == grupo_id)).first()


def obter_grupo_por_nome(db: Session, tenant_id: UUID, nome: str) -> Grupo | None:
    return db.scalars(select(Grupo).where(Grupo.tenant_id == tenant_id, Grupo.nome == nome)).first()


def listar_semanas(db: Session, tenant_id: UUID) -> Sequence[Semana]:
    stmt = select(Semana).where(Semana.tenant_id == tenant_id).order_by(Semana.created_at.desc(), Semana.id)
    return db.scalars(stmt).all()


def obter_semana(db: Session, tenant_id: UUID, semana_id: UUID) -> Semana | None:
    return db.scalars(select(Semana).where(Semana.tenant_id == tenant_id, Semana.id == semana_id)).first()


def obter_semana_por_identificacao(db: Session, tenant_id: UUID, identificacao: str) -> Semana | None:
    stmt = select(Semana).where(Semana.tenant_id == tenant_id, Semana.identificacao == identificacao)
    return db.scalars(stmt).first()


def listar_lancamentos(
    db: Session, tenant_id: UUID, *, grupo_id: UUID | None = None, semana_id: UUID | None = None
) -> Sequence[Lancamento]:
    stmt = select(Lancamento).where(Lancamento.tenant_id == tenant_id)
    if grupo_id is not None:
        stmt = stmt.where(Lancamento.grupo_id == grupo_id)
    if semana_id is not None:
        stmt = stmt.where(Lancamento.semana_id == semana_id)
    return db.scalars(stmt).all()


def obter_lancamento(db: Session, tenant_id: UUID, lancamento_id: UUID) -> Lancamento | None:
    stmt = select(Lancamento).where(Lancamento.tenant_id == tenant_id, Lancamento.id == lancamento_id)
    return db.scalars(stmt).first()


def obter_lancamento_por_chave(
    db: Session, tenant_id: UUID, grupo_id: UUID, semana_id: UUID, status: str
) -> Lancamento | None:
    stmt = select(Lancamento).where(
        Lancamento.tenant_id == tenant_id,
        Lancamento.grupo_id == grupo_id,
        Lancamento.semana_id == semana_id,
        Lancamento.status == status,
    )
    return db.scalars(stmt).first()

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.backend.models.capacidade import Grupo, Lancamento, Semana
from src.backend.models.demandas import Demanda


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


def obter_grupo_sistema(db: Session, tenant_id: UUID) -> Grupo | None:
    return db.scalars(select(Grupo).where(Grupo.tenant_id == tenant_id, Grupo.sistema.is_(True))).first()


def contar_demandas_do_grupo(db: Session, tenant_id: UUID, grupo_id: UUID) -> int:
    stmt = select(func.count()).select_from(Demanda).where(Demanda.tenant_id == tenant_id, Demanda.grupo_id == grupo_id)
    return int(db.scalar(stmt) or 0)


def listar_demandas_painel(db: Session, tenant_id: UUID) -> Sequence[tuple[UUID, str, datetime, datetime | None]]:
    """(grupo_id, status, created_at, concluido_em) das demandas ABERTA e CONCLUIDA, para o painel."""
    stmt = select(Demanda.grupo_id, Demanda.status, Demanda.created_at, Demanda.concluido_em).where(
        Demanda.tenant_id == tenant_id, Demanda.status.in_(("ABERTA", "CONCLUIDA"))
    )
    return [(r[0], r[1], r[2], r[3]) for r in db.execute(stmt).all()]

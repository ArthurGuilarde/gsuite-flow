from collections.abc import Collection, Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.backend.models.planner import PlannerDia, PlannerItem

# Todas as consultas filtram por tenant_id E sub: o planner é pessoal dentro do tenant.


def obter_dia(db: Session, tenant_id: UUID, sub: str, data: date) -> PlannerDia | None:
    stmt = select(PlannerDia).where(PlannerDia.tenant_id == tenant_id, PlannerDia.sub == sub, PlannerDia.data == data)
    return db.scalars(stmt).first()


def listar_dias(db: Session, tenant_id: UUID, sub: str, de: date, ate: date) -> Sequence[PlannerDia]:
    stmt = select(PlannerDia).where(
        PlannerDia.tenant_id == tenant_id, PlannerDia.sub == sub, PlannerDia.data >= de, PlannerDia.data <= ate
    )
    return db.scalars(stmt.order_by(PlannerDia.data.desc())).all()


def listar_itens_do_dia(db: Session, tenant_id: UUID, sub: str, dia_id: UUID) -> Sequence[PlannerItem]:
    stmt = select(PlannerItem).where(
        PlannerItem.tenant_id == tenant_id, PlannerItem.sub == sub, PlannerItem.dia_id == dia_id
    )
    return db.scalars(stmt.order_by(PlannerItem.ordem, PlannerItem.created_at, PlannerItem.id)).all()


def listar_itens_dos_dias(db: Session, tenant_id: UUID, sub: str, dia_ids: Collection[UUID]) -> Sequence[PlannerItem]:
    if not dia_ids:
        return []
    stmt = select(PlannerItem).where(
        PlannerItem.tenant_id == tenant_id, PlannerItem.sub == sub, PlannerItem.dia_id.in_(list(dia_ids))
    )
    return db.scalars(stmt).all()


def obter_item(db: Session, tenant_id: UUID, sub: str, item_id: UUID) -> PlannerItem | None:
    stmt = select(PlannerItem).where(
        PlannerItem.tenant_id == tenant_id, PlannerItem.sub == sub, PlannerItem.id == item_id
    )
    return db.scalars(stmt).first()


def listar_pendentes(db: Session, tenant_id: UUID, sub: str, antes_de: date) -> list[tuple[PlannerItem, date]]:
    """Itens abertos de dias anteriores a `antes_de`: (item, data do dia de origem), data DESC e ordem."""
    stmt = (
        select(PlannerItem, PlannerDia)
        .join(PlannerDia, (PlannerDia.tenant_id == PlannerItem.tenant_id) & (PlannerDia.id == PlannerItem.dia_id))
        .where(
            PlannerItem.tenant_id == tenant_id,
            PlannerItem.sub == sub,
            PlannerDia.tenant_id == tenant_id,
            PlannerDia.sub == sub,
            PlannerDia.data < antes_de,
            PlannerItem.concluido.is_(False),
            PlannerItem.descartado.is_(False),
            PlannerItem.migrado_em.is_(None),
        )
        .order_by(PlannerDia.data.desc(), PlannerItem.ordem, PlannerItem.tipo, PlannerItem.created_at, PlannerItem.id)
    )
    return [(item, dia.data) for item, dia in db.execute(stmt).all()]

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.backend.models.base import TenantRecord


class PlannerDia(TenantRecord):
    """Um dia do planner de UMA pessoa (tenant_id + sub) — nunca compartilhado dentro do tenant."""

    __tablename__ = "planner_dias"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_planner_dias_tenant_id"),
        UniqueConstraint("tenant_id", "sub", "id", name="uq_planner_dias_tenant_sub_id"),
        UniqueConstraint("tenant_id", "sub", "data", name="uq_planner_dias_sub_data"),
        Index("ix_planner_dias_tenant_sub_data", "tenant_id", "sub", "data"),
    )
    sub: Mapped[str] = mapped_column(String(255), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    foco: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PlannerItem(TenantRecord):
    __tablename__ = "planner_itens"
    __table_args__ = (
        CheckConstraint("tipo IN ('PRIORIDADE','TAREFA')", name="ck_planner_itens_tipo"),
        ForeignKeyConstraint(
            ["tenant_id", "sub", "dia_id"],
            ["planner_dias.tenant_id", "planner_dias.sub", "planner_dias.id"],
            name="fk_planner_itens_dia",
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_planner_itens_tenant_id"),
        Index("ix_planner_itens_tenant_sub_dia", "tenant_id", "sub", "dia_id"),
    )
    sub: Mapped[str] = mapped_column(String(255), nullable=False)
    dia_id: Mapped[UUID] = mapped_column(nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    texto: Mapped[str] = mapped_column(String(500), nullable=False)
    concluido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    migrado_em: Mapped[date | None] = mapped_column(Date, nullable=True)
    descartado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    origem_item_id: Mapped[UUID | None] = mapped_column(nullable=True)

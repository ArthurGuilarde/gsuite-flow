from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.backend.models.base import TenantRecord


class Despesa(TenantRecord):
    __tablename__ = "despesas"
    __table_args__ = (
        CheckConstraint("tipo_custo IN ('RECORRENTE_MENSAL','PONTUAL')", name="ck_despesas_tipo_custo"),
        CheckConstraint(
            "status_auditoria IN ('EM_REVISAO','VALIDADO','DESPERDICIO','CANCELADO','RENEGOCIADO')",
            name="ck_despesas_status",
        ),
        CheckConstraint("valor >= 0 AND (valor_anterior IS NULL OR valor_anterior >= 0)", name="ck_despesas_valor"),
        ForeignKeyConstraint(
            ["tenant_id", "fonte_id"],
            ["fontes_custo.tenant_id", "fontes_custo.id"],
            name="fk_despesas_fonte",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_despesas_tenant_id"),
        Index("ix_despesas_tenant_status", "tenant_id", "status_auditoria"),
        Index("ix_despesas_tenant_renovacao", "tenant_id", "data_renovacao"),
    )
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    fornecedor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    categoria: Mapped[str] = mapped_column(String(60), nullable=False)
    tipo_custo: Mapped[str] = mapped_column(String(20), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    valor_anterior: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    status_auditoria: Mapped[str] = mapped_column(
        String(12), nullable=False, default="EM_REVISAO", server_default="EM_REVISAO"
    )
    data_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_renovacao: Mapped[date | None] = mapped_column(Date, nullable=True)
    responsavel: Mapped[str | None] = mapped_column(String(120), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    mes_acao: Mapped[date | None] = mapped_column(Date, nullable=True)
    fonte_id: Mapped[UUID | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OrcamentoDespesa(TenantRecord):
    __tablename__ = "orcamentos_despesas"
    __table_args__ = (
        CheckConstraint("valor >= 0", name="ck_orcamentos_despesas_valor"),
        UniqueConstraint("tenant_id", "id", name="uq_orcamentos_despesas_tenant_id"),
        UniqueConstraint("tenant_id", "competencia", name="uq_orcamentos_despesas_competencia"),
    )
    competencia: Mapped[date] = mapped_column(Date, nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

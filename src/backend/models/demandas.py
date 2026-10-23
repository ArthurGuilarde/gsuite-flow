from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.backend.models.base import TenantRecord


class Demanda(TenantRecord):
    __tablename__ = "demandas"
    __table_args__ = (
        CheckConstraint("prioridade IN ('BAIXA','MEDIA','ALTA')", name="ck_demandas_prioridade"),
        CheckConstraint("status IN ('ABERTA','CONCLUIDA','CANCELADA')", name="ck_demandas_status"),
        CheckConstraint("(concluido_em IS NOT NULL) = (status = 'CONCLUIDA')", name="ck_demandas_concluido"),
        ForeignKeyConstraint(
            ["tenant_id", "grupo_id"],
            ["grupos.tenant_id", "grupos.id"],
            name="fk_demandas_grupo",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_demandas_tenant_id"),
        Index("ix_demandas_tenant_status", "tenant_id", "status"),
        Index("ix_demandas_tenant_grupo", "tenant_id", "grupo_id"),
        Index("ix_demandas_tenant_solicitante", "tenant_id", "solicitante_sub"),
    )
    grupo_id: Mapped[UUID] = mapped_column(nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    prioridade: Mapped[str] = mapped_column(String(5), nullable=False, default="MEDIA", server_default="MEDIA")
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="ABERTA", server_default="ABERTA")
    solicitante_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    classificado_por: Mapped[str | None] = mapped_column(String(255), nullable=True)
    classificado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    concluido_por: Mapped[str | None] = mapped_column(String(255), nullable=True)
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DemandaEvento(TenantRecord):
    __tablename__ = "demanda_historico"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('ABERTURA','CLASSIFICACAO','CONCLUSAO','REABERTURA','CANCELAMENTO','COMENTARIO')",
            name="ck_demanda_historico_tipo",
        ),
        CheckConstraint("(tipo <> 'COMENTARIO') OR (texto IS NOT NULL)", name="ck_demanda_historico_texto"),
        ForeignKeyConstraint(
            ["tenant_id", "demanda_id"],
            ["demandas.tenant_id", "demandas.id"],
            name="fk_demanda_historico_demanda",
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_demanda_historico_tenant_id"),
        Index("ix_demanda_historico_tenant_demanda", "tenant_id", "demanda_id", "created_at"),
    )
    demanda_id: Mapped[UUID] = mapped_column(nullable=False)
    tipo: Mapped[str] = mapped_column(String(12), nullable=False)
    autor_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    grupo_nome: Mapped[str | None] = mapped_column(String(120), nullable=True)

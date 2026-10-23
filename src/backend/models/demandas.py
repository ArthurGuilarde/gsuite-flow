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

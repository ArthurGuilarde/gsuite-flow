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


class Grupo(TenantRecord):
    __tablename__ = "grupos"
    __table_args__ = (
        CheckConstraint("categoria IN ('BUILD','RUN')", name="ck_grupos_categoria"),
        UniqueConstraint("tenant_id", "id", name="uq_grupos_tenant_id"),
        UniqueConstraint("tenant_id", "nome", name="uq_grupos_tenant_nome"),
        Index(
            "uq_grupos_sistema",
            "tenant_id",
            unique=True,
            sqlite_where=text("sistema"),
            postgresql_where=text("sistema"),
        ),
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    categoria: Mapped[str] = mapped_column(String(5), nullable=False)
    icone: Mapped[str] = mapped_column(String(16), nullable=False, default="📋", server_default="📋")
    cor: Mapped[str] = mapped_column(String(7), nullable=False, default="#64748B", server_default="#64748B")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    sistema: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))


class Semana(TenantRecord):
    __tablename__ = "semanas"
    __table_args__ = (
        CheckConstraint(
            "data_inicio IS NULL OR data_fim IS NULL OR data_fim >= data_inicio", name="ck_semanas_periodo"
        ),
        UniqueConstraint("tenant_id", "id", name="uq_semanas_tenant_id"),
        UniqueConstraint("tenant_id", "identificacao", name="uq_semanas_tenant_identificacao"),
    )
    identificacao: Mapped[str] = mapped_column(String(60), nullable=False)
    data_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_fim: Mapped[date | None] = mapped_column(Date, nullable=True)


class Lancamento(TenantRecord):
    __tablename__ = "lancamentos"
    __table_args__ = (
        CheckConstraint("quantidade >= 0", name="ck_lancamentos_quantidade"),
        CheckConstraint("status IN ('ABERTO','RESOLVIDO')", name="ck_lancamentos_status"),
        ForeignKeyConstraint(
            ["tenant_id", "grupo_id"],
            ["grupos.tenant_id", "grupos.id"],
            name="fk_lancamentos_grupo",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "semana_id"],
            ["semanas.tenant_id", "semanas.id"],
            name="fk_lancamentos_semana",
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_lancamentos_tenant_id"),
        Index("ix_lancamentos_tenant_semana", "tenant_id", "semana_id"),
        Index("ix_lancamentos_tenant_grupo", "tenant_id", "grupo_id"),
    )
    grupo_id: Mapped[UUID] = mapped_column(nullable=False)
    semana_id: Mapped[UUID] = mapped_column(nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(9), nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

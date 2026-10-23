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
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.backend.models.base import TenantRecord


class Rotina(TenantRecord):
    __tablename__ = "rotinas"
    __table_args__ = (
        CheckConstraint("categoria IN ('BUILD','RUN')", name="ck_rotinas_categoria"),
        CheckConstraint(
            "tipo_agendamento IN ('SEMANAL','DIARIA','QUINZENAL','MENSAL_DIA_FIXO',"
            "'MENSAL_PRIMEIRO_UTIL','MENSAL_ULTIMO_UTIL')",
            name="ck_rotinas_tipo",
        ),
        CheckConstraint(
            "dia_semana IS NULL OR dia_semana IN ('Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo')",
            name="ck_rotinas_dia_semana",
        ),
        CheckConstraint("tipo_agendamento <> 'SEMANAL' OR dia_semana IS NOT NULL", name="ck_rotinas_semanal"),
        CheckConstraint("periodo IN ('Manhã','Tarde','Integral')", name="ck_rotinas_periodo"),
        CheckConstraint("dia_mes IS NULL OR dia_mes BETWEEN 1 AND 31", name="ck_rotinas_dia_mes"),
        CheckConstraint("tipo_agendamento <> 'MENSAL_DIA_FIXO' OR dia_mes IS NOT NULL", name="ck_rotinas_mensal_fixo"),
        CheckConstraint("esforco_estimado_min BETWEEN 0 AND 1440", name="ck_rotinas_esforco"),
        UniqueConstraint("tenant_id", "id", name="uq_rotinas_tenant_id"),
        Index("ix_rotinas_tenant_ordem", "tenant_id", "ordem"),
    )
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    categoria: Mapped[str] = mapped_column(String(5), nullable=False, default="RUN", server_default="RUN")
    responsavel: Mapped[str | None] = mapped_column(String(120), nullable=True)
    link_recurso: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tipo_agendamento: Mapped[str] = mapped_column(
        String(24), nullable=False, default="SEMANAL", server_default="SEMANAL"
    )
    dia_semana: Mapped[str | None] = mapped_column(String(7), nullable=True)
    periodo: Mapped[str] = mapped_column(String(8), nullable=False, default="Manhã", server_default="Manhã")
    dia_mes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    esforco_estimado_min: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    inicio_vigencia: Mapped[date] = mapped_column(Date, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RotinaExecucao(TenantRecord):
    __tablename__ = "rotina_execucoes"
    __table_args__ = (
        CheckConstraint(
            "ocorrencia IN ('SEMANA','Segunda','Terça','Quarta','Quinta','Sexta')",
            name="ck_rotina_execucoes_ocorrencia",
        ),
        CheckConstraint("status IN ('PENDENTE','CONCLUIDA')", name="ck_rotina_execucoes_status"),
        CheckConstraint(
            "esforco_real_min IS NULL OR esforco_real_min BETWEEN 0 AND 1440", name="ck_rotina_execucoes_esforco"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "rotina_id"],
            ["rotinas.tenant_id", "rotinas.id"],
            name="fk_rotina_execucoes_rotina",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "semana_id"],
            ["semanas.tenant_id", "semanas.id"],
            name="fk_rotina_execucoes_semana",
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_rotina_execucoes_tenant_id"),
        UniqueConstraint("tenant_id", "rotina_id", "semana_id", "ocorrencia", name="uq_rotina_execucoes_ocorrencia"),
        Index("ix_rotina_execucoes_tenant_semana", "tenant_id", "semana_id"),
    )
    rotina_id: Mapped[UUID] = mapped_column(nullable=False)
    semana_id: Mapped[UUID] = mapped_column(nullable=False)
    ocorrencia: Mapped[str] = mapped_column(String(7), nullable=False)
    status: Mapped[str] = mapped_column(String(9), nullable=False, default="PENDENTE", server_default="PENDENTE")
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    concluido_por: Mapped[str | None] = mapped_column(String, nullable=True)
    esforco_real_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

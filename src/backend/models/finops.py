from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.backend.models.base import TenantRecord


class PerfilCusto(TenantRecord):
    __tablename__ = "perfis_custo"
    __table_args__ = (
        CheckConstraint("custo_hora >= 0", name="ck_perfis_custo_custo_hora"),
        UniqueConstraint("tenant_id", "id", name="uq_perfis_custo_tenant_id"),
        UniqueConstraint("tenant_id", "nome", name="uq_perfis_custo_tenant_nome"),
    )
    nome: Mapped[str] = mapped_column(String(80), nullable=False)
    custo_hora: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class FonteCusto(TenantRecord):
    __tablename__ = "fontes_custo"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_fontes_custo_tenant_id"),
        UniqueConstraint("tenant_id", "nome", name="uq_fontes_custo_tenant_nome"),
    )
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrica_nome: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class Fatura(TenantRecord):
    __tablename__ = "faturas"
    __table_args__ = (
        CheckConstraint(
            "valor_realizado >= 0 AND (valor_orcado IS NULL OR valor_orcado >= 0) "
            "AND (metrica_valor IS NULL OR metrica_valor >= 0)",
            name="ck_faturas_valores",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "fonte_id"],
            ["fontes_custo.tenant_id", "fontes_custo.id"],
            name="fk_faturas_fonte",
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_faturas_tenant_id"),
        UniqueConstraint("tenant_id", "fonte_id", "competencia", name="uq_faturas_fonte_competencia"),
        Index("ix_faturas_tenant_competencia", "tenant_id", "competencia"),
    )
    fonte_id: Mapped[UUID] = mapped_column(nullable=False)
    competencia: Mapped[date] = mapped_column(Date, nullable=False)
    valor_orcado: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    valor_realizado: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    metrica_valor: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Iniciativa(TenantRecord):
    __tablename__ = "iniciativas"
    __table_args__ = (
        CheckConstraint("tipo IN ('MELHORIA','AUTOMACAO','OTIMIZACAO_CUSTO')", name="ck_iniciativas_tipo"),
        CheckConstraint("modo_calculo IN ('DIRETO_REAIS','POR_TEMPO')", name="ck_iniciativas_modo"),
        CheckConstraint("valor_mensal IS NULL OR valor_mensal >= 0", name="ck_iniciativas_valor_mensal"),
        CheckConstraint(
            "frequencia IS NULL OR frequencia IN ('DIARIA_UTIL','DIARIA_CORRIDA','SEMANAL','QUINZENAL','MENSAL')",
            name="ck_iniciativas_frequencia",
        ),
        CheckConstraint("janela_meses BETWEEN 1 AND 60", name="ck_iniciativas_janela"),
        CheckConstraint(
            "mes_encerramento IS NULL OR mes_encerramento >= mes_inicio", name="ck_iniciativas_encerramento"
        ),
        CheckConstraint(
            "investimento_reais >= 0 AND investimento_horas >= 0 AND investimento_custo_hora >= 0",
            name="ck_iniciativas_investimento",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "fonte_id"],
            ["fontes_custo.tenant_id", "fontes_custo.id"],
            name="fk_iniciativas_fonte",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_iniciativas_tenant_id"),
        Index("ix_iniciativas_tenant_inicio", "tenant_id", "mes_inicio"),
    )
    titulo: Mapped[str] = mapped_column(String(160), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    modo_calculo: Mapped[str] = mapped_column(String(12), nullable=False)
    valor_mensal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    frequencia: Mapped[str | None] = mapped_column(String(16), nullable=True)
    mes_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    janela_meses: Mapped[int] = mapped_column(Integer, nullable=False, default=6, server_default="6")
    mes_encerramento: Mapped[date | None] = mapped_column(Date, nullable=True)
    fonte_id: Mapped[UUID | None] = mapped_column(nullable=True)
    investimento_reais: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal(0), server_default="0"
    )
    investimento_horas: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal(0), server_default="0"
    )
    investimento_custo_hora: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal(0), server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class IniciativaParticipante(TenantRecord):
    __tablename__ = "iniciativa_participantes"
    __table_args__ = (
        CheckConstraint(
            "custo_hora >= 0 AND qtd_pessoas >= 1 AND horas_antes >= 0 AND horas_depois >= 0",
            name="ck_participantes_valores",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "iniciativa_id"],
            ["iniciativas.tenant_id", "iniciativas.id"],
            name="fk_participantes_iniciativa",
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "id", name="uq_iniciativa_participantes_tenant_id"),
        Index("ix_participantes_tenant_iniciativa", "tenant_id", "iniciativa_id"),
    )
    iniciativa_id: Mapped[UUID] = mapped_column(nullable=False)
    perfil_nome: Mapped[str] = mapped_column(String(80), nullable=False)
    custo_hora: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    qtd_pessoas: Mapped[int] = mapped_column(Integer, nullable=False)
    horas_antes: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    horas_depois: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

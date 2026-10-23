from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.backend.services.rotinas_agenda import DIAS_SEMANA, normalizar_tipo

Categoria = Literal["BUILD", "RUN"]
Periodo = Literal["Manhã", "Tarde", "Integral"]
StatusExecucao = Literal["PENDENTE", "CONCLUIDA"]


def _upper(value):
    return value.strip().upper() if isinstance(value, str) else value


def _tipo(value):
    if value is None:
        return value
    try:
        return normalizar_tipo(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError("tipo_agendamento inválido") from exc


def _dia_semana(value: str | None) -> str | None:
    if value is not None and value not in DIAS_SEMANA:
        raise ValueError("dia_semana inválido")
    return value


def _link(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not value.lower().startswith(("http://", "https://")):
        raise ValueError("link_recurso deve começar com http:// ou https://")
    return value


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RotinaCreate(_Entrada):
    titulo: str = Field(min_length=1, max_length=200)
    descricao: str | None = None
    categoria: Categoria = "RUN"
    responsavel: str | None = Field(default=None, max_length=120)
    link_recurso: str | None = Field(default=None, max_length=500)
    tipo_agendamento: str = "SEMANAL"
    dia_semana: str | None = None
    periodo: Periodo = "Manhã"
    dia_mes: int | None = Field(default=None, ge=1, le=31)
    esforco_estimado_min: int = Field(default=0, ge=0, le=1440)
    ordem: int = Field(default=0, ge=0)
    ativo: bool = True
    inicio_vigencia: date | None = None

    _categoria = field_validator("categoria", mode="before")(_upper)
    _tipo = field_validator("tipo_agendamento", mode="before")(_tipo)
    _dia = field_validator("dia_semana")(_dia_semana)
    _link = field_validator("link_recurso")(_link)


class RotinaUpdate(_Entrada):
    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    descricao: str | None = None
    categoria: Categoria | None = None
    responsavel: str | None = Field(default=None, max_length=120)
    link_recurso: str | None = Field(default=None, max_length=500)
    tipo_agendamento: str | None = None
    dia_semana: str | None = None
    periodo: Periodo | None = None
    dia_mes: int | None = Field(default=None, ge=1, le=31)
    esforco_estimado_min: int | None = Field(default=None, ge=0, le=1440)
    ordem: int | None = Field(default=None, ge=0)
    ativo: bool | None = None
    inicio_vigencia: date | None = None

    _categoria = field_validator("categoria", mode="before")(_upper)
    _tipo = field_validator("tipo_agendamento", mode="before")(_tipo)
    _dia = field_validator("dia_semana")(_dia_semana)
    _link = field_validator("link_recurso")(_link)


class ExecucaoUpdate(_Entrada):
    semana_id: UUID
    ocorrencia: str = Field(min_length=1, max_length=7)
    status: StatusExecucao
    esforco_real_min: int | None = Field(default=None, ge=0, le=1440)
    observacao: str | None = None

    _status = field_validator("status", mode="before")(_upper)


class ResetSemana(_Entrada):
    semana_id: UUID


class RotinaView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    titulo: str
    descricao: str | None
    categoria: str
    responsavel: str | None
    link_recurso: str | None
    tipo_agendamento: str
    dia_semana: str | None
    periodo: str
    dia_mes: int | None
    esforco_estimado_min: int
    ordem: int
    ativo: bool
    inicio_vigencia: date
    created_at: datetime
    updated_at: datetime


class OcorrenciaView(BaseModel):
    rotina_id: UUID
    semana_id: UUID
    semana_identificacao: str
    ocorrencia: str
    data_prevista: date | None
    status: str
    situacao: str
    titulo: str
    descricao: str | None
    categoria: str
    responsavel: str | None
    link_recurso: str | None
    tipo_agendamento: str
    dia_semana: str | None
    periodo: str
    dia_mes: int | None
    esforco_estimado_min: int
    esforco_real_min: int | None
    concluido_em: datetime | None
    concluido_por: str | None
    observacao: str | None


class ResumoEsforco(BaseModel):
    ocorrencias: int
    concluidas: int
    pendentes: int
    minutos_previstos: int
    minutos_executados: int


class ResumoSemana(BaseModel):
    BUILD: ResumoEsforco
    RUN: ResumoEsforco
    TOTAL: ResumoEsforco


class SemanaRotinasView(BaseModel):
    semana_id: UUID
    semana_identificacao: str
    hoje: date
    ocorrencias: list[OcorrenciaView]
    resumo: ResumoSemana


class PendenciasView(BaseModel):
    hoje: date
    vence_hoje: list[OcorrenciaView]
    atrasadas: list[OcorrenciaView]


class ResultadoPadrao(BaseModel):
    created: int
    skipped: int


class ResultadoReset(BaseModel):
    reset_count: int


class RotinaDashboard(BaseModel):
    categoria: str
    abertos: int
    resolvidos: int
    total: int
    minutos_previstos: int
    minutos_executados: int

import re
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.backend.schemas.rotinas import RotinaDashboard

Categoria = Literal["BUILD", "RUN"]
StatusLancamento = Literal["ABERTO", "RESOLVIDO"]
COR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _upper(value):
    return value.strip().upper() if isinstance(value, str) else value


def _validar_cor(value: str | None) -> str | None:
    if value is not None and not COR_RE.match(value):
        raise ValueError("cor deve estar no formato #RRGGBB")
    return value


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GrupoCreate(_Entrada):
    nome: str = Field(min_length=1, max_length=120)
    categoria: Categoria
    icone: str | None = Field(default=None, min_length=1, max_length=16)
    cor: str | None = None

    _categoria = field_validator("categoria", mode="before")(_upper)
    _cor = field_validator("cor")(_validar_cor)


class GrupoUpdate(_Entrada):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    categoria: Categoria | None = None
    icone: str | None = Field(default=None, min_length=1, max_length=16)
    cor: str | None = None
    ativo: bool | None = None

    _categoria = field_validator("categoria", mode="before")(_upper)
    _cor = field_validator("cor")(_validar_cor)


def _validar_periodo(inicio: date | None, fim: date | None) -> None:
    if inicio is not None and fim is not None and fim < inicio:
        raise ValueError("data_fim deve ser maior ou igual a data_inicio")


class SemanaCreate(_Entrada):
    identificacao: str = Field(min_length=1, max_length=60)
    data_inicio: date | None = None
    data_fim: date | None = None

    @model_validator(mode="after")
    def periodo(self):
        _validar_periodo(self.data_inicio, self.data_fim)
        return self


class SemanaUpdate(_Entrada):
    identificacao: str | None = Field(default=None, min_length=1, max_length=60)
    data_inicio: date | None = None
    data_fim: date | None = None

    @model_validator(mode="after")
    def periodo(self):
        _validar_periodo(self.data_inicio, self.data_fim)
        return self


class LancamentoCreate(_Entrada):
    grupo_id: UUID
    semana_id: UUID
    quantidade: int = Field(default=0, ge=0)
    status: StatusLancamento = "ABERTO"
    observacao: str | None = None

    _status = field_validator("status", mode="before")(_upper)


class LancamentoUpdate(_Entrada):
    grupo_id: UUID | None = None
    semana_id: UUID | None = None
    quantidade: int | None = Field(default=None, ge=0)
    status: StatusLancamento | None = None
    observacao: str | None = None

    _status = field_validator("status", mode="before")(_upper)


class InicializarSemana(_Entrada):
    semana_id: UUID
    grupo_ids: list[UUID] | None = None
    default_qtd: int = Field(default=0, ge=0)


class LancamentoPar(_Entrada):
    grupo_id: UUID
    semana_id: UUID
    qtd_aberto: int = Field(ge=0)
    qtd_resolvido: int = Field(ge=0)
    obs_aberto: str = ""
    obs_resolvido: str = ""


class _View(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GrupoView(_View):
    id: UUID
    nome: str
    categoria: str
    icone: str
    cor: str
    ativo: bool
    created_at: datetime


class SemanaView(_View):
    id: UUID
    identificacao: str
    data_inicio: date | None
    data_fim: date | None
    created_at: datetime


class LancamentoView(BaseModel):
    id: UUID
    grupo_id: UUID
    grupo_nome: str
    grupo_categoria: str
    grupo_icone: str
    grupo_cor: str
    semana_id: UUID
    semana_identificacao: str
    quantidade: int
    status: str
    observacao: str | None
    created_at: datetime
    updated_at: datetime


class ResultadoGrupos(BaseModel):
    created: int
    skipped: int


class ResultadoInicializar(BaseModel):
    created: int
    skipped: int
    total_grupos: int


class GrupoDashboard(BaseModel):
    id: UUID
    nome: str
    categoria: str
    icone: str
    cor: str
    abertos: int
    resolvidos: int
    total: int
    taxa_resolucao: float
    pct_aberto: float
    pct_resolvido: float


class DashboardView(BaseModel):
    semana_id: UUID | None
    periodo: str
    meta_build_min: float
    meta_run_max: float
    total: int
    total_abertos: int
    total_resolvidos: int
    taxa_resolucao: float
    qtd_build: int
    qtd_run: int
    perc_build: float
    perc_run: float
    build_atingiu_meta: bool
    run_atingiu_meta: bool
    gap_build_pp: float
    gap_run_pp: float
    resolvidos_build: int
    resolvidos_run: int
    perc_build_resolvidos: float
    perc_run_resolvidos: float
    resolvidos_build_atingiu_meta: bool
    resolvidos_run_atingiu_meta: bool
    gap_build_resolvidos_pp: float
    gap_run_resolvidos_pp: float
    abertos_build: int
    abertos_run: int
    perc_build_abertos: float
    perc_run_abertos: float
    groups: list[GrupoDashboard]
    rotinas: list[RotinaDashboard]

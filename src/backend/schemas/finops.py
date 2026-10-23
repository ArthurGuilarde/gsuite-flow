from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    field_validator,
    model_validator,
)

from src.backend.services.finops_calculos import (
    DIRETO_REAIS,
    JANELA_PADRAO,
    POR_TEMPO,
    fmt_competencia,
    parse_competencia,
)

Tipo = Literal["MELHORIA", "AUTOMACAO", "OTIMIZACAO_CUSTO"]
Modo = Literal["DIRETO_REAIS", "POR_TEMPO"]
Frequencia = Literal["DIARIA_UTIL", "DIARIA_CORRIDA", "SEMANAL", "QUINZENAL", "MENSAL"]
MAX_PARTICIPANTES = 20


def _upper(value):
    return value.strip().upper() if isinstance(value, str) else value


def _competencia(value):
    if value is None or isinstance(value, date):
        return value
    return parse_competencia(value)


# Competência: "YYYY-MM" na API, date no dia 1 internamente.
Competencia = Annotated[
    date,
    BeforeValidator(_competencia),
    PlainSerializer(fmt_competencia, return_type=str, when_used="json"),
]
# Dinheiro/horas: entram como Decimal validado; saem como número JSON.
Numero = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
Dinheiro = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
CustoHora = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Horas = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- perfis ---------------------------------------------------------------------------------------------------------


class PerfilCreate(_Entrada):
    nome: str = Field(min_length=1, max_length=80)
    custo_hora: CustoHora

    @field_validator("nome")
    @classmethod
    def _nome(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("nome obrigatório")
        return v


class PerfilUpdate(_Entrada):
    nome: str | None = Field(default=None, min_length=1, max_length=80)
    custo_hora: CustoHora | None = None
    ativo: bool | None = None


class PerfilView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    custo_hora: Numero
    ativo: bool
    created_at: datetime


# --- fontes ---------------------------------------------------------------------------------------------------------


class FonteCreate(_Entrada):
    nome: str = Field(min_length=1, max_length=120)
    descricao: str | None = None
    metrica_nome: str | None = Field(default=None, max_length=80)


class FonteUpdate(_Entrada):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    descricao: str | None = None
    metrica_nome: str | None = Field(default=None, max_length=80)
    ativo: bool | None = None


class FonteView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    descricao: str | None
    metrica_nome: str | None
    ativo: bool
    created_at: datetime


# --- faturas --------------------------------------------------------------------------------------------------------


class FaturaCreate(_Entrada):
    fonte_id: UUID
    competencia: Competencia
    valor_realizado: Dinheiro
    valor_orcado: Dinheiro | None = None
    metrica_valor: Dinheiro | None = None
    observacao: str | None = None


class FaturaUpdate(_Entrada):
    competencia: Competencia | None = None
    valor_realizado: Dinheiro | None = None
    valor_orcado: Dinheiro | None = None
    metrica_valor: Dinheiro | None = None
    observacao: str | None = None


class FaturaView(BaseModel):
    id: UUID
    fonte_id: UUID
    fonte_nome: str
    competencia: Competencia
    valor_orcado: Numero | None
    valor_realizado: Numero
    variacao: Numero | None
    metrica_valor: Numero | None
    custo_unitario: Numero | None
    observacao: str | None
    created_at: datetime
    updated_at: datetime


# --- iniciativas ----------------------------------------------------------------------------------------------------


class ParticipanteIn(_Entrada):
    perfil_nome: str = Field(min_length=1, max_length=80)
    custo_hora: CustoHora
    qtd_pessoas: int = Field(ge=1, le=100000)
    horas_antes: Horas
    horas_depois: Horas


class IniciativaIn(_Entrada):
    titulo: str = Field(min_length=1, max_length=160)
    descricao: str | None = None
    tipo: Tipo
    modo_calculo: Modo
    valor_mensal: Dinheiro | None = None
    frequencia: Frequencia | None = None
    participantes: list[ParticipanteIn] = Field(default_factory=list, max_length=MAX_PARTICIPANTES)
    mes_inicio: Competencia
    janela_meses: int = Field(default=JANELA_PADRAO, ge=1, le=60)
    mes_encerramento: Competencia | None = None
    fonte_id: UUID | None = None
    despesa_id: UUID | None = None
    investimento_reais: Dinheiro = Decimal(0)
    investimento_horas: Horas = Decimal(0)
    investimento_custo_hora: CustoHora = Decimal(0)

    _upper = field_validator("tipo", "modo_calculo", "frequencia", mode="before")(_upper)

    @model_validator(mode="after")
    def _regras(self):
        if self.mes_encerramento is not None and self.mes_encerramento < self.mes_inicio:
            raise ValueError("mes_encerramento deve ser maior ou igual a mes_inicio")
        if self.modo_calculo == DIRETO_REAIS:
            if self.valor_mensal is None:
                raise ValueError("valor_mensal é obrigatório em DIRETO_REAIS")
            if self.participantes:
                raise ValueError("participantes só se aplicam a POR_TEMPO")
            self.frequencia = None
        elif self.modo_calculo == POR_TEMPO:
            if self.frequencia is None:
                raise ValueError("frequencia é obrigatória em POR_TEMPO")
            if not self.participantes:
                raise ValueError("POR_TEMPO exige ao menos um participante")
            self.valor_mensal = None
        return self


class ParticipanteView(BaseModel):
    id: UUID | None = None
    perfil_nome: str
    custo_hora: Numero
    qtd_pessoas: int
    horas_antes: Numero
    horas_depois: Numero
    horas_mes: Numero
    valor_mensal: Numero


class ParticipanteSimulado(BaseModel):
    horas_mes: Numero
    valor_mensal: Numero


class CalculoView(BaseModel):
    valor_mensal: Numero
    horas_mes: Numero
    fte: Numero
    perc_reducao: Numero | None
    fim_janela: Competencia
    meses_janela: int
    status: str
    meses_contados: int
    saving_acumulado: Numero
    saving_janela: Numero
    investimento_total: Numero
    roi_janela_pct: Numero | None
    payback_meses: int | None
    se_paga_na_janela: bool


class IniciativaView(BaseModel):
    id: UUID
    titulo: str
    descricao: str | None
    tipo: str
    modo_calculo: str
    valor_mensal: Numero | None
    frequencia: str | None
    mes_inicio: Competencia
    janela_meses: int
    mes_encerramento: Competencia | None
    fonte_id: UUID | None
    fonte_nome: str | None
    despesa_id: UUID | None
    despesa_nome: str | None
    conversao_despesa: bool
    investimento_reais: Numero
    investimento_horas: Numero
    investimento_custo_hora: Numero
    participantes: list[ParticipanteView]
    calculo: CalculoView
    created_at: datetime
    updated_at: datetime


class SimulacaoView(BaseModel):
    participantes: list[ParticipanteSimulado]
    calculo: CalculoView


# --- dashboard ------------------------------------------------------------------------------------------------------


class StatusContagem(BaseModel):
    PLANEJADA: int
    EM_SAVING: int
    NOVO_NORMAL: int
    ENCERRADA: int


class KpisView(BaseModel):
    saving_realizado: Numero
    saving_projetado: Numero
    saving_mensal_em_curso: Numero
    saving_direto_em_curso: Numero
    saving_horas_em_curso: Numero
    horas_mes_liberadas: Numero
    fte_liberado: Numero
    novo_normal_mensal: Numero
    investimento_total: Numero
    saving_janela_total: Numero
    roi_pct: Numero | None
    iniciativas_por_status: StatusContagem


class PontoSerieView(BaseModel):
    competencia: Competencia
    saving_direto: Numero
    saving_horas: Numero
    saving_total: Numero
    projetado: bool
    orcado: Numero | None
    realizado: Numero | None
    variacao: Numero | None


class PorTipoView(BaseModel):
    tipo: str
    quantidade: int
    saving_periodo: Numero


class PontoFonteView(BaseModel):
    competencia: Competencia
    orcado: Numero | None
    realizado: Numero | None
    variacao: Numero | None
    metrica_valor: Numero | None
    custo_unitario: Numero | None


class FonteDashboardView(BaseModel):
    id: UUID
    nome: str
    metrica_nome: str | None
    orcado_periodo: Numero | None
    realizado_periodo: Numero
    variacao_periodo: Numero | None
    saving_iniciativas_mensal: Numero
    serie: list[PontoFonteView]


class IniciativaDashboardView(BaseModel):
    id: UUID
    titulo: str
    tipo: str
    modo_calculo: str
    status: str
    valor_mensal: Numero
    horas_mes: Numero
    saving_periodo: Numero
    saving_janela: Numero
    investimento_total: Numero
    roi_janela_pct: Numero | None
    payback_meses: int | None
    se_paga_na_janela: bool
    mes_inicio: Competencia
    fim_janela: Competencia


class DashboardView(BaseModel):
    de: Competencia
    ate: Competencia
    referencia: Competencia
    janela_padrao: int
    horas_fte_mes: int
    kpis: KpisView
    serie: list[PontoSerieView]
    por_tipo: list[PorTipoView]
    fontes: list[FonteDashboardView]
    iniciativas: list[IniciativaDashboardView]

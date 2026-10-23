from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.backend.schemas.finops import Competencia, Dinheiro, IniciativaView, Numero, _Entrada, _upper
from src.backend.services.finops_calculos import JANELA_PADRAO

TipoCusto = Literal["RECORRENTE_MENSAL", "PONTUAL"]
# Status que o usuário pode definir diretamente; CANCELADO/RENEGOCIADO só pelas ações.
StatusEditavel = Literal["EM_REVISAO", "VALIDADO", "DESPERDICIO"]
StatusAuditoria = Literal["EM_REVISAO", "VALIDADO", "DESPERDICIO", "CANCELADO", "RENEGOCIADO"]


def _texto_obrigatorio(valor: str) -> str:
    valor = valor.strip()
    if not valor:
        raise ValueError("campo obrigatório")
    return valor


# --- despesas -------------------------------------------------------------------------------------------------------


class DespesaCreate(_Entrada):
    nome: str = Field(min_length=1, max_length=160)
    fornecedor: str | None = Field(default=None, max_length=120)
    categoria: str = Field(min_length=1, max_length=60)
    tipo_custo: TipoCusto
    valor: Dinheiro
    status_auditoria: StatusEditavel = "EM_REVISAO"
    data_inicio: date | None = None
    data_renovacao: date | None = None
    responsavel: str | None = Field(default=None, max_length=120)
    observacoes: str | None = None
    fonte_id: UUID | None = None

    _upper = field_validator("tipo_custo", "status_auditoria", mode="before")(_upper)
    _nome = field_validator("nome", "categoria")(_texto_obrigatorio)


class DespesaUpdate(_Entrada):
    nome: str | None = Field(default=None, min_length=1, max_length=160)
    fornecedor: str | None = Field(default=None, max_length=120)
    categoria: str | None = Field(default=None, min_length=1, max_length=60)
    tipo_custo: TipoCusto | None = None
    valor: Dinheiro | None = None
    status_auditoria: StatusEditavel | None = None
    data_inicio: date | None = None
    data_renovacao: date | None = None
    responsavel: str | None = Field(default=None, max_length=120)
    observacoes: str | None = None
    fonte_id: UUID | None = None

    _upper = field_validator("tipo_custo", "status_auditoria", mode="before")(_upper)


class CancelarIn(_Entrada):
    mes: Competencia | None = None
    janela_meses: int = Field(default=JANELA_PADRAO, ge=1, le=60)
    observacao: str | None = None


class RenegociarIn(_Entrada):
    novo_valor: Dinheiro
    mes: Competencia | None = None
    janela_meses: int = Field(default=JANELA_PADRAO, ge=1, le=60)
    observacao: str | None = None


class ReverterIn(_Entrada):
    novo_status: StatusEditavel = "EM_REVISAO"

    _upper = field_validator("novo_status", mode="before")(_upper)


class IniciativaResumoView(BaseModel):
    id: UUID
    titulo: str
    status: str
    valor_mensal: Numero
    conversao_despesa: bool


class DespesaView(BaseModel):
    id: UUID
    nome: str
    fornecedor: str | None
    categoria: str
    tipo_custo: str
    valor: Numero
    valor_anterior: Numero | None
    status_auditoria: str
    data_inicio: date | None
    data_renovacao: date | None
    responsavel: str | None
    observacoes: str | None
    mes_acao: Competencia | None
    fonte_id: UUID | None
    fonte_nome: str | None
    custo_mensal_considerado: Numero
    origem_custo: str
    competencia_fatura: Competencia | None
    custo_anual: Numero
    dias_para_renovacao: int | None
    iniciativas: list[IniciativaResumoView]
    created_at: datetime
    updated_at: datetime


class AcaoResultado(BaseModel):
    despesa: DespesaView
    iniciativa: IniciativaView | None


# --- orçamento ------------------------------------------------------------------------------------------------------


class OrcamentoIn(_Entrada):
    valor: Dinheiro
    observacao: str | None = None


class OrcamentoAnualIn(_Entrada):
    ano: int = Field(ge=2000, le=2200)
    valor_anual: Dinheiro
    sobrescrever: bool = False


class OrcamentoView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    competencia: Competencia
    valor: Numero
    observacao: str | None
    updated_at: datetime


class OrcamentoAnualResultado(BaseModel):
    criados: int
    atualizados: int
    ignorados: int


# --- dashboard ------------------------------------------------------------------------------------------------------


class ContagemStatus(BaseModel):
    EM_REVISAO: int
    VALIDADO: int
    DESPERDICIO: int
    CANCELADO: int
    RENEGOCIADO: int


class KpisDespesasView(BaseModel):
    run_rate_mensal: Numero
    run_rate_anual: Numero
    pontuais_ano: Numero
    desperdicio_mensal: Numero
    saving_capturado_mensal: Numero
    novo_normal_mensal: Numero
    orcado_mes: Numero | None
    variacao_orcamento: Numero | None
    auditoria_pct: Numero
    total_despesas: int
    por_status: ContagemStatus


class AlertaRenovacaoView(BaseModel):
    id: UUID
    nome: str
    fornecedor: str | None
    data_renovacao: date
    dias: int
    nivel: str
    custo_mensal: Numero
    status_auditoria: str


class PorCategoriaView(BaseModel):
    categoria: str
    quantidade: int
    custo_mensal: Numero


class PorStatusView(BaseModel):
    status: str
    quantidade: int
    custo_mensal: Numero


class PontoSerieDespesasView(BaseModel):
    competencia: Competencia
    recorrente: Numero
    pontual: Numero
    total: Numero
    orcado: Numero | None
    variacao: Numero | None


class DashboardDespesasView(BaseModel):
    referencia: Competencia
    hoje: date
    ano: int
    kpis: KpisDespesasView
    alertas_renovacao: list[AlertaRenovacaoView]
    por_categoria: list[PorCategoriaView]
    por_status: list[PorStatusView]
    serie: list[PontoSerieDespesasView]

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.backend.schemas.finops import Numero
from src.backend.schemas.rotinas import OcorrenciaView

TipoItem = Literal["PRIORIDADE", "TAREFA"]
MAX_NOTAS = 20_000


def _upper(value):
    return value.strip().upper() if isinstance(value, str) else value


def _texto(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("campo obrigatório")
    return value


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DiaUpdate(_Entrada):
    foco: str | None = Field(default=None, max_length=500)
    notas: str | None = Field(default=None, max_length=MAX_NOTAS)
    versao: int = Field(default=0, ge=0)

    @field_validator("foco")
    @classmethod
    def _foco(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None


class ItemCreate(_Entrada):
    tipo: TipoItem
    texto: str = Field(min_length=1, max_length=500)
    concluido: bool = False

    _upper = field_validator("tipo", mode="before")(_upper)
    _texto = field_validator("texto")(_texto)


class ItemUpdate(_Entrada):
    texto: str | None = Field(default=None, min_length=1, max_length=500)
    concluido: bool | None = None
    tipo: TipoItem | None = None
    ordem: int | None = Field(default=None, ge=0)

    _upper = field_validator("tipo", mode="before")(_upper)

    @field_validator("texto")
    @classmethod
    def _texto_ok(cls, value: str | None) -> str | None:
        return _texto(value) if value is not None else None

    @model_validator(mode="after")
    def _sem_nulos(self):
        for campo in self.model_fields_set:
            if getattr(self, campo) is None:
                raise ValueError(f"{campo} não pode ser nulo")
        return self


class TrazerPendentesIn(_Entrada):
    item_ids: list[UUID] | None = Field(default=None, max_length=200)


class DescartarPendentesIn(_Entrada):
    item_ids: list[UUID] = Field(min_length=1, max_length=200)


class ItemView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tipo: str
    texto: str
    concluido: bool
    concluido_em: datetime | None
    ordem: int
    origem_item_id: UUID | None


class PendenteView(BaseModel):
    id: UUID
    tipo: str
    texto: str
    data_origem: date


class DiaView(BaseModel):
    id: UUID | None
    foco: str | None
    notas: str | None
    versao: int
    updated_at: datetime | None


class RotinasDoDiaView(BaseModel):
    vence_hoje: list[OcorrenciaView]
    atrasadas: list[OcorrenciaView]


class RenovacaoView(BaseModel):
    id: UUID
    nome: str
    fornecedor: str | None
    data_renovacao: date
    dias: int
    custo_mensal: Numero


class ResumoDiaView(BaseModel):
    itens_total: int
    itens_concluidos: int
    prioridades_concluidas: int
    rotinas_pendentes: int


class MeuDiaView(BaseModel):
    data: date
    dia: DiaView
    prioridades: list[ItemView]
    tarefas: list[ItemView]
    pendentes_anteriores: list[PendenteView]
    rotinas: RotinasDoDiaView
    renovacoes: list[RenovacaoView]
    resumo: ResumoDiaView


class DiaResumoView(BaseModel):
    data: date
    foco: str | None
    itens_total: int
    itens_concluidos: int


class TrazerPendentesOut(BaseModel):
    trazidos: int
    como_tarefa: int


class DescartarPendentesOut(BaseModel):
    descartados: int

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Prioridade = Literal["BAIXA", "MEDIA", "ALTA"]
MAX_DESCRICAO = 10_000


def _upper(value):
    return value.strip().upper() if isinstance(value, str) else value


def _texto(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("campo obrigatório")
    return value


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DemandaCreate(_Entrada):
    titulo: str = Field(min_length=1, max_length=200)
    descricao: str | None = Field(default=None, max_length=MAX_DESCRICAO)
    prioridade: Prioridade = "MEDIA"

    _titulo = field_validator("titulo")(_texto)
    _upper = field_validator("prioridade", mode="before")(_upper)


class ClassificarIn(_Entrada):
    grupo_id: UUID
    prioridade: Prioridade | None = None

    _upper = field_validator("prioridade", mode="before")(_upper)


class DemandaView(BaseModel):
    id: UUID
    titulo: str
    descricao: str | None
    prioridade: str
    status: str
    grupo_id: UUID
    grupo_nome: str
    solicitante_sub: str
    created_at: datetime | None
    updated_at: datetime | None
    classificado_por: str | None
    classificado_em: datetime | None
    concluido_por: str | None
    concluido_em: datetime | None
    cancelado_em: datetime | None

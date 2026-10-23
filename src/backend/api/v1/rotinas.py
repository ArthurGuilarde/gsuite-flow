from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from src.backend.api.deps import read_context, read_db, write_context, write_db
from src.backend.schemas.rotinas import (
    ExecucaoUpdate,
    OcorrenciaView,
    PendenciasView,
    ResetSemana,
    ResultadoPadrao,
    ResultadoReset,
    RotinaCreate,
    RotinaUpdate,
    RotinaView,
    SemanaRotinasView,
)
from src.backend.services import rotinas as service
from src.backend.services.rotinas_agenda import normalizar_tipo
from src.backend.tenancy.context import TenantContext

router = APIRouter(tags=["rotinas"])
ReadDB = Annotated[Session, Depends(read_db, scope="function")]
WriteDB = Annotated[Session, Depends(write_db, scope="function")]
ReadContext = Annotated[TenantContext, Depends(read_context)]
WriteContext = Annotated[TenantContext, Depends(write_context)]


@router.get("/rotinas", response_model=list[RotinaView])
def listar_rotinas(db: ReadDB, ctx: ReadContext, ativo: bool | None = None):
    return service.listar_rotinas(db, ctx, ativo)


@router.post("/rotinas", response_model=RotinaView, status_code=201)
def criar_rotina(body: RotinaCreate, db: WriteDB, ctx: WriteContext):
    return service.criar_rotina(db, ctx, body)


# Rotas fixas antes de /rotinas/{rotina_id}.
@router.post("/rotinas/padrao", response_model=ResultadoPadrao)
def criar_rotinas_padrao(db: WriteDB, ctx: WriteContext):
    return service.criar_rotinas_padrao(db, ctx)


@router.get("/rotinas/semana", response_model=SemanaRotinasView)
def visao_semana(
    db: ReadDB,
    ctx: ReadContext,
    semana_id: UUID,
    hoje: date | None = None,
    categoria: Literal["BUILD", "RUN"] | None = None,
    status: Literal["PENDENTE", "CONCLUIDA"] | None = None,
    tipo_agendamento: str | None = None,
):
    tipo = None
    if tipo_agendamento:
        try:
            tipo = normalizar_tipo(tipo_agendamento)
        except ValueError as exc:
            raise HTTPException(422, "tipo_agendamento inválido") from exc
    return service.visao_semana(db, ctx, semana_id, hoje, categoria, status, tipo)


@router.post("/rotinas/semana/reset", response_model=ResultadoReset)
def resetar_semana(body: ResetSemana, db: WriteDB, ctx: WriteContext):
    return service.resetar_semana(db, ctx, body)


@router.get("/rotinas/pendencias", response_model=PendenciasView)
def pendencias(db: ReadDB, ctx: ReadContext, hoje: date | None = None):
    return service.pendencias(db, ctx, hoje)


@router.get("/rotinas/{rotina_id}", response_model=RotinaView)
def obter_rotina(rotina_id: UUID, db: ReadDB, ctx: ReadContext):
    return service.obter_rotina(db, ctx, rotina_id)


@router.patch("/rotinas/{rotina_id}", response_model=RotinaView)
def atualizar_rotina(rotina_id: UUID, body: RotinaUpdate, db: WriteDB, ctx: WriteContext):
    return service.atualizar_rotina(db, ctx, rotina_id, body)


@router.delete("/rotinas/{rotina_id}", status_code=204)
def remover_rotina(rotina_id: UUID, db: WriteDB, ctx: WriteContext):
    service.remover_rotina(db, ctx, rotina_id)
    return Response(status_code=204)


@router.put("/rotinas/{rotina_id}/execucao", response_model=OcorrenciaView)
def salvar_execucao(rotina_id: UUID, body: ExecucaoUpdate, db: WriteDB, ctx: WriteContext):
    return service.salvar_execucao(db, ctx, rotina_id, body)

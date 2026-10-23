from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from src.backend.api.deps import read_context, read_db, write_context, write_db
from src.backend.schemas.capacidade import (
    DashboardView,
    GrupoCreate,
    GrupoUpdate,
    GrupoView,
    InicializarSemana,
    LancamentoCreate,
    LancamentoPar,
    LancamentoUpdate,
    LancamentoView,
    ResultadoGrupos,
    ResultadoInicializar,
    SemanaCreate,
    SemanaUpdate,
    SemanaView,
)
from src.backend.services import capacidade as service
from src.backend.tenancy.context import TenantContext

router = APIRouter(tags=["capacidade"])
ReadDB = Annotated[Session, Depends(read_db, scope="function")]
WriteDB = Annotated[Session, Depends(write_db, scope="function")]
ReadContext = Annotated[TenantContext, Depends(read_context)]
WriteContext = Annotated[TenantContext, Depends(write_context)]


@router.get("/dashboard", response_model=DashboardView)
def dashboard(db: ReadDB, ctx: ReadContext, semana_id: UUID | None = None):
    return service.dashboard(db, ctx, semana_id)


@router.get("/grupos", response_model=list[GrupoView])
def listar_grupos(db: ReadDB, ctx: ReadContext):
    return service.listar_grupos(db, ctx)


@router.post("/grupos", response_model=GrupoView, status_code=201)
def criar_grupo(body: GrupoCreate, db: WriteDB, ctx: WriteContext):
    return service.criar_grupo(db, ctx, body)


@router.post("/grupos/padrao", response_model=ResultadoGrupos)
def criar_grupos_padrao(db: WriteDB, ctx: WriteContext):
    return service.criar_grupos_padrao(db, ctx)


@router.patch("/grupos/{grupo_id}", response_model=GrupoView)
def atualizar_grupo(grupo_id: UUID, body: GrupoUpdate, db: WriteDB, ctx: WriteContext):
    return service.atualizar_grupo(db, ctx, grupo_id, body)


@router.delete("/grupos/{grupo_id}", status_code=204)
def remover_grupo(grupo_id: UUID, db: WriteDB, ctx: WriteContext):
    service.remover_grupo(db, ctx, grupo_id)
    return Response(status_code=204)


@router.get("/semanas", response_model=list[SemanaView])
def listar_semanas(db: ReadDB, ctx: ReadContext):
    return service.listar_semanas(db, ctx)


@router.post("/semanas", response_model=SemanaView, status_code=201)
def criar_semana(body: SemanaCreate, db: WriteDB, ctx: WriteContext):
    return service.criar_semana(db, ctx, body)


@router.patch("/semanas/{semana_id}", response_model=SemanaView)
def atualizar_semana(semana_id: UUID, body: SemanaUpdate, db: WriteDB, ctx: WriteContext):
    return service.atualizar_semana(db, ctx, semana_id, body)


@router.delete("/semanas/{semana_id}", status_code=204)
def remover_semana(semana_id: UUID, db: WriteDB, ctx: WriteContext):
    service.remover_semana(db, ctx, semana_id)
    return Response(status_code=204)


@router.get("/lancamentos", response_model=list[LancamentoView])
def listar_lancamentos(db: ReadDB, ctx: ReadContext, grupo_id: UUID | None = None, semana_id: UUID | None = None):
    return service.listar_lancamentos(db, ctx, grupo_id, semana_id)


@router.post("/lancamentos", response_model=LancamentoView, status_code=201)
def criar_lancamento(body: LancamentoCreate, db: WriteDB, ctx: WriteContext):
    return service.criar_lancamento(db, ctx, body)


# Rotas fixas antes de /lancamentos/{id}.
@router.post("/lancamentos/inicializar", response_model=ResultadoInicializar)
def inicializar_semana(body: InicializarSemana, db: WriteDB, ctx: WriteContext):
    return service.inicializar_semana(db, ctx, body)


@router.put("/lancamentos/par", response_model=list[LancamentoView])
def salvar_par(body: LancamentoPar, db: WriteDB, ctx: WriteContext):
    return service.salvar_par(db, ctx, body)


@router.patch("/lancamentos/{lancamento_id}", response_model=LancamentoView)
def atualizar_lancamento(lancamento_id: UUID, body: LancamentoUpdate, db: WriteDB, ctx: WriteContext):
    return service.atualizar_lancamento(db, ctx, lancamento_id, body)


@router.delete("/lancamentos/{lancamento_id}", status_code=204)
def remover_lancamento(lancamento_id: UUID, db: WriteDB, ctx: WriteContext):
    service.remover_lancamento(db, ctx, lancamento_id)
    return Response(status_code=204)

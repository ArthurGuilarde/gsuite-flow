from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from src.backend.api.deps import read_context, read_db, write_context, write_db
from src.backend.schemas.planner import (
    DescartarPendentesIn,
    DescartarPendentesOut,
    DiaResumoView,
    DiaUpdate,
    DiaView,
    ItemCreate,
    ItemUpdate,
    ItemView,
    MeuDiaView,
    TrazerPendentesIn,
    TrazerPendentesOut,
)
from src.backend.services import planner as service
from src.backend.tenancy.context import TenantContext

router = APIRouter(prefix="/planner", tags=["planner"])
ReadDB = Annotated[Session, Depends(read_db, scope="function")]
WriteDB = Annotated[Session, Depends(write_db, scope="function")]
ReadContext = Annotated[TenantContext, Depends(read_context)]
WriteContext = Annotated[TenantContext, Depends(write_context)]


@router.get("/meu-dia", response_model=MeuDiaView)
def meu_dia(db: ReadDB, ctx: ReadContext, data: date | None = None):
    return service.meu_dia(db, ctx, data)


@router.get("/dias", response_model=list[DiaResumoView])
def listar_dias(db: ReadDB, ctx: ReadContext, de: date | None = None, ate: date | None = None):
    return service.listar_dias(db, ctx, de, ate)


@router.put("/dias/{data}", response_model=DiaView)
def salvar_dia(data: date, body: DiaUpdate, db: WriteDB, ctx: WriteContext):
    return service.salvar_dia(db, ctx, data, body)


@router.delete("/dias/{data}", status_code=204)
def remover_dia(data: date, db: WriteDB, ctx: WriteContext):
    service.remover_dia(db, ctx, data)
    return Response(status_code=204)


@router.post("/dias/{data}/itens", response_model=ItemView, status_code=201)
def criar_item(data: date, body: ItemCreate, db: WriteDB, ctx: WriteContext):
    return service.criar_item(db, ctx, data, body)


@router.post("/dias/{data}/trazer-pendentes", response_model=TrazerPendentesOut)
def trazer_pendentes(data: date, db: WriteDB, ctx: WriteContext, body: TrazerPendentesIn | None = None):
    return service.trazer_pendentes(db, ctx, data, body or TrazerPendentesIn())


@router.post("/dias/{data}/descartar-pendentes", response_model=DescartarPendentesOut)
def descartar_pendentes(data: date, body: DescartarPendentesIn, db: WriteDB, ctx: WriteContext):
    return service.descartar_pendentes(db, ctx, data, body)


@router.patch("/itens/{item_id}", response_model=ItemView)
def atualizar_item(item_id: UUID, body: ItemUpdate, db: WriteDB, ctx: WriteContext):
    return service.atualizar_item(db, ctx, item_id, body)


@router.delete("/itens/{item_id}", status_code=204)
def remover_item(item_id: UUID, db: WriteDB, ctx: WriteContext):
    service.remover_item(db, ctx, item_id)
    return Response(status_code=204)

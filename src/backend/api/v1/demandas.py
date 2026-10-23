from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.backend.api.deps import read_context, read_db, write_context, write_db
from src.backend.schemas.demandas import ClassificarIn, DemandaCreate, DemandaView
from src.backend.services import demandas as service
from src.backend.tenancy.context import TenantContext

router = APIRouter(prefix="/demandas", tags=["demandas"])
ReadDB = Annotated[Session, Depends(read_db, scope="function")]
WriteDB = Annotated[Session, Depends(write_db, scope="function")]
ReadContext = Annotated[TenantContext, Depends(read_context)]
WriteContext = Annotated[TenantContext, Depends(write_context)]


@router.post("", response_model=DemandaView, status_code=201)
def abrir_demanda(body: DemandaCreate, db: ReadDB, ctx: ReadContext):
    return service.abrir_demanda(db, ctx, body)


@router.get("", response_model=list[DemandaView])
def listar_demandas(
    db: ReadDB, ctx: ReadContext, status: str | None = None, grupo_id: UUID | None = None, minhas: bool = False
):
    return service.listar_demandas(db, ctx, status, grupo_id, minhas)


@router.get("/{demanda_id}", response_model=DemandaView)
def obter_demanda(demanda_id: UUID, db: ReadDB, ctx: ReadContext):
    return service.obter_demanda(db, ctx, demanda_id)


@router.post("/{demanda_id}/classificar", response_model=DemandaView)
def classificar(demanda_id: UUID, body: ClassificarIn, db: WriteDB, ctx: WriteContext):
    return service.classificar(db, ctx, demanda_id, body)


@router.post("/{demanda_id}/concluir", response_model=DemandaView)
def concluir(demanda_id: UUID, db: WriteDB, ctx: WriteContext):
    return service.concluir(db, ctx, demanda_id)


@router.post("/{demanda_id}/reabrir", response_model=DemandaView)
def reabrir(demanda_id: UUID, db: WriteDB, ctx: WriteContext):
    return service.reabrir(db, ctx, demanda_id)


@router.post("/{demanda_id}/cancelar", response_model=DemandaView)
def cancelar(demanda_id: UUID, db: WriteDB, ctx: WriteContext):
    return service.cancelar(db, ctx, demanda_id)

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from src.backend.api.deps import read_context, read_db, write_context, write_db
from src.backend.schemas.finops import (
    DashboardView,
    FaturaCreate,
    FaturaUpdate,
    FaturaView,
    FonteCreate,
    FonteUpdate,
    FonteView,
    IniciativaIn,
    IniciativaView,
    PerfilCreate,
    PerfilUpdate,
    PerfilView,
    SimulacaoView,
)
from src.backend.services import finops as service
from src.backend.services.finops import parse_mes_param
from src.backend.tenancy.context import TenantContext

router = APIRouter(prefix="/finops", tags=["finops"])
ReadDB = Annotated[Session, Depends(read_db, scope="function")]
WriteDB = Annotated[Session, Depends(write_db, scope="function")]
ReadContext = Annotated[TenantContext, Depends(read_context)]
WriteContext = Annotated[TenantContext, Depends(write_context)]
TIPOS = ("MELHORIA", "AUTOMACAO", "OTIMIZACAO_CUSTO")
STATUS = ("PLANEJADA", "EM_SAVING", "NOVO_NORMAL", "ENCERRADA")


def _upper(valor: str | None) -> str | None:
    return valor.strip().upper() if valor else None


# --- perfis ---
@router.get("/perfis", response_model=list[PerfilView])
def listar_perfis(db: ReadDB, ctx: ReadContext):
    return service.listar_perfis(db, ctx)


@router.post("/perfis", response_model=PerfilView, status_code=201)
def criar_perfil(body: PerfilCreate, db: WriteDB, ctx: WriteContext):
    return service.criar_perfil(db, ctx, body)


@router.patch("/perfis/{perfil_id}", response_model=PerfilView)
def atualizar_perfil(perfil_id: UUID, body: PerfilUpdate, db: WriteDB, ctx: WriteContext):
    return service.atualizar_perfil(db, ctx, perfil_id, body)


@router.delete("/perfis/{perfil_id}", status_code=204)
def remover_perfil(perfil_id: UUID, db: WriteDB, ctx: WriteContext):
    service.remover_perfil(db, ctx, perfil_id)
    return Response(status_code=204)


# --- fontes ---
@router.get("/fontes", response_model=list[FonteView])
def listar_fontes(db: ReadDB, ctx: ReadContext):
    return service.listar_fontes(db, ctx)


@router.post("/fontes", response_model=FonteView, status_code=201)
def criar_fonte(body: FonteCreate, db: WriteDB, ctx: WriteContext):
    return service.criar_fonte(db, ctx, body)


@router.patch("/fontes/{fonte_id}", response_model=FonteView)
def atualizar_fonte(fonte_id: UUID, body: FonteUpdate, db: WriteDB, ctx: WriteContext):
    return service.atualizar_fonte(db, ctx, fonte_id, body)


@router.delete("/fontes/{fonte_id}", status_code=204)
def remover_fonte(fonte_id: UUID, db: WriteDB, ctx: WriteContext):
    service.remover_fonte(db, ctx, fonte_id)
    return Response(status_code=204)


# --- faturas ---
@router.get("/faturas", response_model=list[FaturaView])
def listar_faturas(
    db: ReadDB, ctx: ReadContext, fonte_id: UUID | None = None, de: str | None = None, ate: str | None = None
):
    return service.listar_faturas(db, ctx, fonte_id, parse_mes_param(de, "de"), parse_mes_param(ate, "ate"))


@router.post("/faturas", response_model=FaturaView, status_code=201)
def criar_fatura(body: FaturaCreate, db: WriteDB, ctx: WriteContext):
    return service.criar_fatura(db, ctx, body)


@router.patch("/faturas/{fatura_id}", response_model=FaturaView)
def atualizar_fatura(fatura_id: UUID, body: FaturaUpdate, db: WriteDB, ctx: WriteContext):
    return service.atualizar_fatura(db, ctx, fatura_id, body)


@router.delete("/faturas/{fatura_id}", status_code=204)
def remover_fatura(fatura_id: UUID, db: WriteDB, ctx: WriteContext):
    service.remover_fatura(db, ctx, fatura_id)
    return Response(status_code=204)


# --- iniciativas ---
@router.get("/iniciativas", response_model=list[IniciativaView])
def listar_iniciativas(
    db: ReadDB, ctx: ReadContext, tipo: str | None = None, status: str | None = None, referencia: str | None = None
):
    tipo_n, status_n = _upper(tipo), _upper(status)
    if tipo_n is not None and tipo_n not in TIPOS:
        raise HTTPException(422, "tipo inválido")
    if status_n is not None and status_n not in STATUS:
        raise HTTPException(422, "status inválido")
    return service.listar_iniciativas(db, ctx, tipo_n, status_n, parse_mes_param(referencia, "referencia"))


@router.post("/iniciativas", response_model=IniciativaView, status_code=201)
def criar_iniciativa(body: IniciativaIn, db: WriteDB, ctx: WriteContext):
    return service.criar_iniciativa(db, ctx, body)


@router.get("/iniciativas/{iniciativa_id}", response_model=IniciativaView)
def obter_iniciativa(iniciativa_id: UUID, db: ReadDB, ctx: ReadContext, referencia: str | None = None):
    return service.obter_iniciativa(db, ctx, iniciativa_id, parse_mes_param(referencia, "referencia"))


@router.put("/iniciativas/{iniciativa_id}", response_model=IniciativaView)
def atualizar_iniciativa(iniciativa_id: UUID, body: IniciativaIn, db: WriteDB, ctx: WriteContext):
    return service.atualizar_iniciativa(db, ctx, iniciativa_id, body)


@router.delete("/iniciativas/{iniciativa_id}", status_code=204)
def remover_iniciativa(iniciativa_id: UUID, db: WriteDB, ctx: WriteContext):
    service.remover_iniciativa(db, ctx, iniciativa_id)
    return Response(status_code=204)


# --- simulação e dashboard ---
@router.post("/simular", response_model=SimulacaoView)
def simular(body: IniciativaIn, db: ReadDB, ctx: ReadContext, referencia: str | None = None):
    return service.simular(body, parse_mes_param(referencia, "referencia"))


@router.get("/dashboard", response_model=DashboardView)
def dashboard(
    db: ReadDB, ctx: ReadContext, de: str | None = None, ate: str | None = None, referencia: str | None = None
):
    return service.dashboard(
        db, ctx, parse_mes_param(de, "de"), parse_mes_param(ate, "ate"), parse_mes_param(referencia, "referencia")
    )

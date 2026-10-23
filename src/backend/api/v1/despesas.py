from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from src.backend.api.deps import read_context, read_db, write_context, write_db
from src.backend.schemas.despesas import (
    AcaoResultado,
    CancelarIn,
    DashboardDespesasView,
    DespesaCreate,
    DespesaUpdate,
    DespesaView,
    OrcamentoAnualIn,
    OrcamentoAnualResultado,
    OrcamentoIn,
    OrcamentoView,
    RenegociarIn,
    ReverterIn,
)
from src.backend.services import despesas as service
from src.backend.services.despesas import parse_data_param
from src.backend.services.finops import parse_mes_param
from src.backend.tenancy.context import TenantContext

router = APIRouter(prefix="/despesas", tags=["despesas"])
ReadDB = Annotated[Session, Depends(read_db, scope="function")]
WriteDB = Annotated[Session, Depends(write_db, scope="function")]
ReadContext = Annotated[TenantContext, Depends(read_context)]
WriteContext = Annotated[TenantContext, Depends(write_context)]
STATUS = ("EM_REVISAO", "VALIDADO", "DESPERDICIO", "CANCELADO", "RENEGOCIADO")


def _competencia(valor: str, nome: str):
    parsed = parse_mes_param(valor, nome)
    if parsed is None:
        raise HTTPException(422, f"{nome} deve estar no formato YYYY-MM")
    return parsed


# --- orçamento e painel (rotas fixas antes de /{despesa_id}) ---
@router.get("/orcamentos", response_model=list[OrcamentoView])
def listar_orcamentos(db: ReadDB, ctx: ReadContext, ano: int | None = None):
    if ano is not None and not 1 <= ano <= 9999:
        raise HTTPException(422, "ano inválido")
    return service.listar_orcamentos(db, ctx, ano)


@router.post("/orcamentos/anual", response_model=OrcamentoAnualResultado)
def orcamento_anual(body: OrcamentoAnualIn, db: WriteDB, ctx: WriteContext):
    return service.orcamento_anual(db, ctx, body)


@router.put("/orcamentos/{competencia}", response_model=OrcamentoView)
def salvar_orcamento(competencia: str, body: OrcamentoIn, db: WriteDB, ctx: WriteContext):
    return service.salvar_orcamento(db, ctx, _competencia(competencia, "competencia"), body)


@router.delete("/orcamentos/{competencia}", status_code=204)
def remover_orcamento(competencia: str, db: WriteDB, ctx: WriteContext):
    service.remover_orcamento(db, ctx, _competencia(competencia, "competencia"))
    return Response(status_code=204)


@router.get("/dashboard", response_model=DashboardDespesasView)
def dashboard(db: ReadDB, ctx: ReadContext, referencia: str | None = None, hoje: str | None = None):
    return service.dashboard(db, ctx, parse_mes_param(referencia, "referencia"), parse_data_param(hoje, "hoje"))


# --- inventário ---
@router.get("", response_model=list[DespesaView])
def listar_despesas(
    db: ReadDB,
    ctx: ReadContext,
    status: str | None = None,
    categoria: str | None = None,
    referencia: str | None = None,
    hoje: str | None = None,
):
    status_n = status.strip().upper() if status else None
    if status_n is not None and status_n not in STATUS:
        raise HTTPException(422, "status inválido")
    return service.listar_despesas(
        db, ctx, status_n, categoria or None, parse_mes_param(referencia, "referencia"), parse_data_param(hoje, "hoje")
    )


@router.post("", response_model=DespesaView, status_code=201)
def criar_despesa(body: DespesaCreate, db: WriteDB, ctx: WriteContext):
    return service.criar_despesa(db, ctx, body)


@router.get("/{despesa_id}", response_model=DespesaView)
def obter_despesa(
    despesa_id: UUID, db: ReadDB, ctx: ReadContext, referencia: str | None = None, hoje: str | None = None
):
    return service.obter_despesa(
        db, ctx, despesa_id, parse_mes_param(referencia, "referencia"), parse_data_param(hoje, "hoje")
    )


@router.patch("/{despesa_id}", response_model=DespesaView)
def atualizar_despesa(despesa_id: UUID, body: DespesaUpdate, db: WriteDB, ctx: WriteContext):
    return service.atualizar_despesa(db, ctx, despesa_id, body)


@router.delete("/{despesa_id}", status_code=204)
def remover_despesa(despesa_id: UUID, db: WriteDB, ctx: WriteContext):
    service.remover_despesa(db, ctx, despesa_id)
    return Response(status_code=204)


@router.post("/{despesa_id}/cancelar", response_model=AcaoResultado)
def cancelar(
    despesa_id: UUID, db: WriteDB, ctx: WriteContext, body: Annotated[CancelarIn, Body(default_factory=CancelarIn)]
):
    return service.cancelar(db, ctx, despesa_id, body)


@router.post("/{despesa_id}/renegociar", response_model=AcaoResultado)
def renegociar(despesa_id: UUID, body: RenegociarIn, db: WriteDB, ctx: WriteContext):
    return service.renegociar(db, ctx, despesa_id, body)


@router.post("/{despesa_id}/reverter", response_model=DespesaView)
def reverter(
    despesa_id: UUID, db: WriteDB, ctx: WriteContext, body: Annotated[ReverterIn, Body(default_factory=ReverterIn)]
):
    return service.reverter(db, ctx, despesa_id, body)

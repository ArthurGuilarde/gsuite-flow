"""Demandas e Triagem. Abrir demanda exige só read; o solicitante sem write vê apenas as próprias."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.backend.core.exceptions import ConflictError, NotFoundError
from src.backend.models.demandas import Demanda, DemandaEvento
from src.backend.repositories import capacidade as grupos_repo
from src.backend.repositories import demandas as repo
from src.backend.schemas.demandas import ClassificarIn, ComentarioCreate, DemandaCreate
from src.backend.services.capacidade import garantir_triagem
from src.backend.tenancy.context import TenantContext

ABERTA, CONCLUIDA, CANCELADA = "ABERTA", "CONCLUIDA", "CANCELADA"


def _agora() -> datetime:
    return datetime.now(UTC)


def _tem_write(ctx: TenantContext) -> bool:
    return "write" in ctx.permissions


def _demanda_ou_404(db: Session, ctx: TenantContext, demanda_id: UUID) -> Demanda:
    demanda = repo.obter_demanda(db, ctx.tenant_id, demanda_id)
    if demanda is None or (not _tem_write(ctx) and demanda.solicitante_sub != ctx.sub):
        raise NotFoundError("Demanda não encontrada")
    return demanda


def _nomes(db: Session, ctx: TenantContext) -> dict[UUID, str]:
    return {g.id: g.nome for g in grupos_repo.listar_grupos(db, ctx.tenant_id)}


def _view(demanda: Demanda, nomes: dict[UUID, str]) -> dict[str, Any]:
    return {
        "id": demanda.id,
        "titulo": demanda.titulo,
        "descricao": demanda.descricao,
        "prioridade": demanda.prioridade,
        "status": demanda.status,
        "grupo_id": demanda.grupo_id,
        "grupo_nome": nomes.get(demanda.grupo_id, ""),
        "solicitante_sub": demanda.solicitante_sub,
        "created_at": demanda.created_at,
        "updated_at": demanda.updated_at,
        "classificado_por": demanda.classificado_por,
        "classificado_em": demanda.classificado_em,
        "concluido_por": demanda.concluido_por,
        "concluido_em": demanda.concluido_em,
        "cancelado_em": demanda.cancelado_em,
    }


def _evento(
    db: Session,
    ctx: TenantContext,
    demanda: Demanda,
    tipo: str,
    texto: str | None = None,
    grupo_nome: str | None = None,
    quando: datetime | None = None,
) -> DemandaEvento:
    evento = DemandaEvento(
        tenant_id=ctx.tenant_id,
        created_by=ctx.sub,
        created_at=quando or _agora(),
        demanda_id=demanda.id,
        tipo=tipo,
        autor_sub=ctx.sub,
        texto=texto,
        grupo_nome=grupo_nome,
    )
    db.add(evento)
    return evento


def _salvar(db: Session, ctx: TenantContext, demanda: Demanda) -> dict[str, Any]:
    db.flush()
    db.refresh(demanda)
    return _view(demanda, _nomes(db, ctx))


def abrir_demanda(db: Session, ctx: TenantContext, body: DemandaCreate) -> dict[str, Any]:
    triagem = garantir_triagem(db, ctx)
    demanda = Demanda(
        id=uuid4(),
        tenant_id=ctx.tenant_id,
        created_by=ctx.sub,
        grupo_id=triagem.id,
        titulo=body.titulo,
        descricao=body.descricao,
        prioridade=body.prioridade,
        status=ABERTA,
        solicitante_sub=ctx.sub,
    )
    db.add(demanda)
    _evento(db, ctx, demanda, "ABERTURA")
    return _salvar(db, ctx, demanda)


def listar_demandas(
    db: Session, ctx: TenantContext, status: str | None, grupo_id: UUID | None, minhas: bool
) -> list[dict[str, Any]]:
    garantir_triagem(db, ctx)
    proprio = ctx.sub if (minhas or not _tem_write(ctx)) else None
    itens = repo.listar_demandas(db, ctx.tenant_id, status.strip().upper() if status else None, grupo_id, proprio)
    nomes = _nomes(db, ctx)
    return [_view(d, nomes) for d in itens]


def obter_demanda(db: Session, ctx: TenantContext, demanda_id: UUID) -> dict[str, Any]:
    garantir_triagem(db, ctx)
    return _view(_demanda_ou_404(db, ctx, demanda_id), _nomes(db, ctx))


def classificar(db: Session, ctx: TenantContext, demanda_id: UUID, body: ClassificarIn) -> dict[str, Any]:
    garantir_triagem(db, ctx)
    demanda = _demanda_ou_404(db, ctx, demanda_id)
    if demanda.status != ABERTA:
        raise ConflictError("Só demandas abertas podem ser classificadas")
    grupo = grupos_repo.obter_grupo(db, ctx.tenant_id, body.grupo_id)
    if grupo is None:
        raise NotFoundError("Grupo não encontrado")
    if grupo.sistema:
        raise HTTPException(422, "O grupo de sistema não pode ser destino de classificação")
    if not grupo.ativo:
        raise HTTPException(422, "Grupo inativo não pode receber demandas")
    demanda.grupo_id = grupo.id
    if body.prioridade is not None:
        demanda.prioridade = body.prioridade
    demanda.classificado_por = ctx.sub
    demanda.classificado_em = _agora()
    _evento(db, ctx, demanda, "CLASSIFICACAO", grupo_nome=grupo.nome, quando=demanda.classificado_em)
    return _salvar(db, ctx, demanda)


def concluir(db: Session, ctx: TenantContext, demanda_id: UUID) -> dict[str, Any]:
    garantir_triagem(db, ctx)
    demanda = _demanda_ou_404(db, ctx, demanda_id)
    if demanda.status != ABERTA:
        raise ConflictError("Só demandas abertas podem ser concluídas")
    demanda.status = CONCLUIDA
    demanda.concluido_por = ctx.sub
    demanda.concluido_em = _agora()
    _evento(db, ctx, demanda, "CONCLUSAO", quando=demanda.concluido_em)
    return _salvar(db, ctx, demanda)


def reabrir(db: Session, ctx: TenantContext, demanda_id: UUID) -> dict[str, Any]:
    garantir_triagem(db, ctx)
    demanda = _demanda_ou_404(db, ctx, demanda_id)
    if demanda.status != CONCLUIDA:
        raise ConflictError("Só demandas concluídas podem ser reabertas")
    demanda.status = ABERTA
    demanda.concluido_por = None
    demanda.concluido_em = None
    _evento(db, ctx, demanda, "REABERTURA")
    return _salvar(db, ctx, demanda)


def cancelar(db: Session, ctx: TenantContext, demanda_id: UUID) -> dict[str, Any]:
    garantir_triagem(db, ctx)
    demanda = _demanda_ou_404(db, ctx, demanda_id)
    if demanda.status != ABERTA:
        raise ConflictError("Só demandas abertas podem ser canceladas")
    demanda.status = CANCELADA
    demanda.cancelado_em = _agora()
    _evento(db, ctx, demanda, "CANCELAMENTO", quando=demanda.cancelado_em)
    return _salvar(db, ctx, demanda)


def historico(db: Session, ctx: TenantContext, demanda_id: UUID) -> list[DemandaEvento]:
    garantir_triagem(db, ctx)
    demanda = _demanda_ou_404(db, ctx, demanda_id)
    return list(repo.listar_eventos(db, ctx.tenant_id, demanda.id))


def comentar(db: Session, ctx: TenantContext, demanda_id: UUID, body: ComentarioCreate) -> DemandaEvento:
    garantir_triagem(db, ctx)
    demanda = _demanda_ou_404(db, ctx, demanda_id)
    if demanda.status == CANCELADA:
        raise ConflictError("Demandas canceladas não aceitam comentários")
    evento = _evento(db, ctx, demanda, "COMENTARIO", texto=body.texto)
    db.flush()
    db.refresh(evento)
    return evento

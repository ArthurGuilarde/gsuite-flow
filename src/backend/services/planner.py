"""Planner pessoal (Meu Dia). Cada registro pertence a (tenant_id, sub); o sub vem sempre do contexto."""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.backend.core.exceptions import NotFoundError
from src.backend.models.planner import PlannerDia, PlannerItem
from src.backend.repositories import planner as repo
from src.backend.schemas.planner import DescartarPendentesIn, DiaUpdate, ItemCreate, ItemUpdate, TrazerPendentesIn
from src.backend.services import despesas as despesas_service
from src.backend.services import rotinas as rotinas_service
from src.backend.tenancy.context import TenantContext

MAX_PRIORIDADES = 3
MAX_ITENS_DIA = 200
MAX_INTERVALO_DIAS = 366
JANELA_HISTORICO_DIAS = 30
PRIORIDADE, TAREFA = "PRIORIDADE", "TAREFA"


def hoje_servidor() -> date:
    return date.today()


def _dia_ou_404(db: Session, ctx: TenantContext, data: date) -> PlannerDia:
    dia = repo.obter_dia(db, ctx.tenant_id, ctx.sub, data)
    if dia is None:
        raise NotFoundError("Dia não encontrado")
    return dia


def _item_ou_404(db: Session, ctx: TenantContext, item_id: UUID) -> PlannerItem:
    item = repo.obter_item(db, ctx.tenant_id, ctx.sub, item_id)
    if item is None:
        raise NotFoundError("Item não encontrado")
    return item


def _dia_para_escrita(db: Session, ctx: TenantContext, data: date) -> PlannerDia:
    """Upsert sob demanda: o dia só passa a existir na primeira escrita."""
    dia = repo.obter_dia(db, ctx.tenant_id, ctx.sub, data)
    if dia is not None:
        return dia
    dia = PlannerDia(tenant_id=ctx.tenant_id, created_by=ctx.sub, sub=ctx.sub, data=data, versao=1)
    try:
        with db.begin_nested():
            db.add(dia)
            db.flush()
    except IntegrityError:
        # Outra requisição criou o mesmo dia ao mesmo tempo: usa o existente.
        existente = repo.obter_dia(db, ctx.tenant_id, ctx.sub, data)
        if existente is None:
            raise
        return existente
    db.refresh(dia)
    return dia


def _ordenar(itens: Sequence[PlannerItem]) -> list[PlannerItem]:
    return sorted(itens, key=lambda i: (i.ordem, i.created_at is None, i.created_at, str(i.id)))


def _proxima_ordem(itens: Sequence[PlannerItem], tipo: str) -> int:
    return max((i.ordem for i in itens if i.tipo == tipo), default=-1) + 1


def _validar_capacidade(itens: Sequence[PlannerItem], tipo: str, ignorar: UUID | None = None) -> None:
    """Valida a inclusão de mais um item `tipo` entre os itens atuais do dia."""
    atuais = [i for i in itens if i.id != ignorar]
    if len(atuais) + 1 > MAX_ITENS_DIA:
        raise HTTPException(422, f"Limite de {MAX_ITENS_DIA} itens por dia")
    if tipo == PRIORIDADE and sum(1 for i in atuais if i.tipo == PRIORIDADE) >= MAX_PRIORIDADES:
        raise HTTPException(422, f"Limite de {MAX_PRIORIDADES} prioridades por dia")


def _dia_view(dia: PlannerDia | None) -> dict[str, Any]:
    if dia is None:
        return {"id": None, "foco": None, "notas": None, "versao": 0, "updated_at": None}
    return {"id": dia.id, "foco": dia.foco, "notas": dia.notas, "versao": dia.versao, "updated_at": dia.updated_at}


def _pendentes_view(pares: Sequence[tuple[PlannerItem, date]]) -> list[dict[str, Any]]:
    return [{"id": i.id, "tipo": i.tipo, "texto": i.texto, "data_origem": origem} for i, origem in pares]


# --- Meu Dia ----------------------------------------------------------------------------------------------------


def meu_dia(db: Session, ctx: TenantContext, data: date | None) -> dict[str, Any]:
    """Visão do dia. Somente leitura: nunca cria o dia."""
    data = data or hoje_servidor()
    dia = repo.obter_dia(db, ctx.tenant_id, ctx.sub, data)
    itens = _ordenar(repo.listar_itens_do_dia(db, ctx.tenant_id, ctx.sub, dia.id)) if dia is not None else []
    prioridades = [i for i in itens if i.tipo == PRIORIDADE]
    tarefas = [i for i in itens if i.tipo == TAREFA]
    pend = rotinas_service.pendencias(db, ctx, data)
    rotinas = {"vence_hoje": pend["vence_hoje"], "atrasadas": pend["atrasadas"]}
    return {
        "data": data,
        "dia": _dia_view(dia),
        "prioridades": prioridades,
        "tarefas": tarefas,
        "pendentes_anteriores": _pendentes_view(repo.listar_pendentes(db, ctx.tenant_id, ctx.sub, data)),
        "rotinas": rotinas,
        "renovacoes": despesas_service.renovacoes_urgentes(db, ctx, data),
        "resumo": {
            "itens_total": len(itens),
            "itens_concluidos": sum(1 for i in itens if i.concluido),
            "prioridades_concluidas": sum(1 for i in prioridades if i.concluido),
            "rotinas_pendentes": len(rotinas["vence_hoje"]) + len(rotinas["atrasadas"]),
        },
    }


def salvar_dia(db: Session, ctx: TenantContext, data: date, dados: DiaUpdate) -> dict[str, Any]:
    dia = repo.obter_dia(db, ctx.tenant_id, ctx.sub, data)
    atual = dia.versao if dia is not None else 0
    if dados.versao != atual:
        raise HTTPException(409, {"mensagem": "Dia alterado em outro lugar", "versao_atual": atual})
    if dia is None:
        dia = _dia_para_escrita(db, ctx, data)
        if dia.versao != 1:
            raise HTTPException(409, {"mensagem": "Dia alterado em outro lugar", "versao_atual": dia.versao})
    if "foco" in dados.model_fields_set:
        dia.foco = dados.foco
    if "notas" in dados.model_fields_set:
        dia.notas = dados.notas
    dia.versao = dia.versao + 1
    dia.updated_at = datetime.now(UTC)
    db.flush()
    db.refresh(dia)
    return _dia_view(dia)


def remover_dia(db: Session, ctx: TenantContext, data: date) -> None:
    dia = _dia_ou_404(db, ctx, data)
    for item in repo.listar_itens_do_dia(db, ctx.tenant_id, ctx.sub, dia.id):
        db.delete(item)
    db.flush()
    db.delete(dia)
    db.flush()


def listar_dias(db: Session, ctx: TenantContext, de: date | None, ate: date | None) -> list[dict[str, Any]]:
    ate = ate or hoje_servidor()
    de = de or ate - timedelta(days=JANELA_HISTORICO_DIAS - 1)
    if de > ate:
        raise HTTPException(422, "de deve ser anterior ou igual a ate")
    if (ate - de).days >= MAX_INTERVALO_DIAS:
        raise HTTPException(422, f"Intervalo máximo de {MAX_INTERVALO_DIAS} dias")
    dias = repo.listar_dias(db, ctx.tenant_id, ctx.sub, de, ate)
    itens = repo.listar_itens_dos_dias(db, ctx.tenant_id, ctx.sub, [d.id for d in dias])
    total: dict[UUID, int] = {}
    feitos: dict[UUID, int] = {}
    for i in itens:
        total[i.dia_id] = total.get(i.dia_id, 0) + 1
        feitos[i.dia_id] = feitos.get(i.dia_id, 0) + (1 if i.concluido else 0)
    return [
        {"data": d.data, "foco": d.foco, "itens_total": total.get(d.id, 0), "itens_concluidos": feitos.get(d.id, 0)}
        for d in dias
    ]


# --- itens ------------------------------------------------------------------------------------------------------


def criar_item(db: Session, ctx: TenantContext, data: date, dados: ItemCreate) -> PlannerItem:
    dia = _dia_para_escrita(db, ctx, data)
    itens = repo.listar_itens_do_dia(db, ctx.tenant_id, ctx.sub, dia.id)
    _validar_capacidade(itens, dados.tipo)
    item = PlannerItem(
        tenant_id=ctx.tenant_id,
        created_by=ctx.sub,
        sub=ctx.sub,
        dia_id=dia.id,
        tipo=dados.tipo,
        texto=dados.texto,
        concluido=dados.concluido,
        concluido_em=datetime.now(UTC) if dados.concluido else None,
        ordem=_proxima_ordem(itens, dados.tipo),
    )
    db.add(item)
    db.flush()
    db.refresh(item)
    return item


def atualizar_item(db: Session, ctx: TenantContext, item_id: UUID, dados: ItemUpdate) -> PlannerItem:
    item = _item_ou_404(db, ctx, item_id)
    campos = dados.model_fields_set
    if "tipo" in campos and dados.tipo is not None and dados.tipo != item.tipo:
        itens = repo.listar_itens_do_dia(db, ctx.tenant_id, ctx.sub, item.dia_id)
        _validar_capacidade(itens, dados.tipo, ignorar=item.id)
        item.tipo = dados.tipo
        if "ordem" not in campos:
            item.ordem = _proxima_ordem([i for i in itens if i.id != item.id], dados.tipo)
    if "texto" in campos and dados.texto is not None:
        item.texto = dados.texto
    if "ordem" in campos and dados.ordem is not None:
        item.ordem = dados.ordem
    if "concluido" in campos and dados.concluido is not None and dados.concluido != item.concluido:
        item.concluido = dados.concluido
        item.concluido_em = datetime.now(UTC) if dados.concluido else None
    db.flush()
    db.refresh(item)
    return item


def remover_item(db: Session, ctx: TenantContext, item_id: UUID) -> None:
    db.delete(_item_ou_404(db, ctx, item_id))
    db.flush()


# --- pendentes de dias anteriores -------------------------------------------------------------------------------


def _selecionar_pendentes(
    db: Session, ctx: TenantContext, data: date, item_ids: Sequence[UUID] | None
) -> list[tuple[PlannerItem, date]]:
    """Pendentes anteriores a `data` escolhidos (todos se `item_ids` vazio). 404 se inexistente, 409 se não pendente."""
    pendentes = repo.listar_pendentes(db, ctx.tenant_id, ctx.sub, data)
    if not item_ids:
        return pendentes
    escolhidos = set(item_ids)
    for item_id in escolhidos:
        _item_ou_404(db, ctx, item_id)
    por_id = {item.id: item for item, _origem in pendentes}
    if any(item_id not in por_id for item_id in escolhidos):
        raise HTTPException(409, "Item não é um pendente de dia anterior")
    return [(item, origem) for item, origem in pendentes if item.id in escolhidos]


def trazer_pendentes(db: Session, ctx: TenantContext, data: date, dados: TrazerPendentesIn) -> dict[str, int]:
    selecionados = _selecionar_pendentes(db, ctx, data, dados.item_ids)
    if not selecionados:
        return {"trazidos": 0, "como_tarefa": 0}
    dia = _dia_para_escrita(db, ctx, data)
    itens = list(repo.listar_itens_do_dia(db, ctx.tenant_id, ctx.sub, dia.id))
    if len(itens) + len(selecionados) > MAX_ITENS_DIA:
        raise HTTPException(422, f"Limite de {MAX_ITENS_DIA} itens por dia")
    prioridades = sum(1 for i in itens if i.tipo == PRIORIDADE)
    ordens = {PRIORIDADE: _proxima_ordem(itens, PRIORIDADE), TAREFA: _proxima_ordem(itens, TAREFA)}
    como_tarefa = 0
    for original, _origem in selecionados:
        tipo = original.tipo
        if tipo == PRIORIDADE:
            if prioridades >= MAX_PRIORIDADES:
                tipo = TAREFA
                como_tarefa += 1
            else:
                prioridades += 1
        db.add(
            PlannerItem(
                tenant_id=ctx.tenant_id,
                created_by=ctx.sub,
                sub=ctx.sub,
                dia_id=dia.id,
                tipo=tipo,
                texto=original.texto,
                ordem=ordens[tipo],
                origem_item_id=original.id,
            )
        )
        ordens[tipo] += 1
        original.migrado_em = data
    db.flush()
    return {"trazidos": len(selecionados), "como_tarefa": como_tarefa}


def descartar_pendentes(db: Session, ctx: TenantContext, data: date, dados: DescartarPendentesIn) -> dict[str, int]:
    selecionados = _selecionar_pendentes(db, ctx, data, dados.item_ids)
    for item, _origem in selecionados:
        item.descartado = True
        item.migrado_em = data
    db.flush()
    return {"descartados": len(selecionados)}

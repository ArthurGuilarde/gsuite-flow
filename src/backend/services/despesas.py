"""Despesas & Contratos: inventário, ações de economia (cancelar/renegociar/reverter), orçamento e painel."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.backend.core.exceptions import ConflictError, NotFoundError
from src.backend.models.despesas import Despesa, OrcamentoDespesa
from src.backend.models.finops import Fatura, Iniciativa, IniciativaParticipante
from src.backend.repositories import despesas as repo
from src.backend.repositories import finops as repo_finops
from src.backend.schemas.despesas import (
    CancelarIn,
    DespesaCreate,
    DespesaUpdate,
    OrcamentoAnualIn,
    OrcamentoIn,
    RenegociarIn,
    ReverterIn,
)
from src.backend.services import despesas_calculos as dc
from src.backend.services import finops as finops_service
from src.backend.services import finops_calculos as fc
from src.backend.services.finops import _aplicar, _persistir, mes_atual
from src.backend.tenancy.context import TenantContext

ZERO = Decimal(0)
STATUS_ACAO = (dc.CANCELADO, dc.RENEGOCIADO)


# --- helpers ----------------------------------------------------------------------------------------------------


def hoje_servidor() -> date:
    return date.today()


def parse_data_param(valor: str | None, nome: str) -> date | None:
    if valor is None or valor == "":
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError as exc:
        raise HTTPException(422, f"{nome} deve estar no formato YYYY-MM-DD") from exc


def _despesa_ou_404(db: Session, ctx: TenantContext, despesa_id: UUID) -> Despesa:
    despesa = repo.obter_despesa(db, ctx.tenant_id, despesa_id)
    if despesa is None:
        raise NotFoundError("Despesa não encontrada")
    return despesa


def _fonte_ou_404(db: Session, ctx: TenantContext, fonte_id: UUID) -> None:
    if repo_finops.obter_fonte(db, ctx.tenant_id, fonte_id) is None:
        raise NotFoundError("Fonte de custo não encontrada")


def _entrada(d: Despesa) -> dc.DespesaEntrada:
    return dc.DespesaEntrada(
        tipo_custo=d.tipo_custo,
        valor=d.valor,
        status_auditoria=d.status_auditoria,
        valor_anterior=d.valor_anterior,
        data_inicio=d.data_inicio,
        mes_acao=d.mes_acao,
    )


def _faturas_por_fonte(faturas: Iterable[Fatura]) -> dict[UUID, dict[date, Decimal]]:
    mapa: dict[UUID, dict[date, Decimal]] = defaultdict(dict)
    for f in faturas:
        mapa[f.fonte_id][fc.primeiro_dia(f.competencia)] = f.valor_realizado
    return mapa


def _considerado(
    d: Despesa, mes: date, faturas: dict[UUID, dict[date, Decimal]], *, referencia: bool = False
) -> dc.CustoConsiderado:
    mapa = faturas.get(d.fonte_id) if d.fonte_id else None
    return dc.custo_considerado(_entrada(d), mes, mapa, ultima_anterior=referencia)


def _agrupar_participantes(partes: Sequence[IniciativaParticipante]) -> dict[UUID, list[IniciativaParticipante]]:
    grupos: dict[UUID, list[IniciativaParticipante]] = defaultdict(list)
    for p in partes:
        grupos[p.iniciativa_id].append(p)
    return grupos


class _Contexto:
    """Dados auxiliares carregados uma vez por requisição para montar views."""

    def __init__(self, db: Session, ctx: TenantContext, despesas: Sequence[Despesa], ref: date) -> None:
        self.ref = ref
        fontes = {f.id: f.nome for f in repo_finops.listar_fontes(db, ctx.tenant_id)}
        self.nomes_fonte = fontes
        fonte_ids = {d.fonte_id for d in despesas if d.fonte_id}
        self.faturas = _faturas_por_fonte(repo.listar_faturas_das_fontes(db, ctx.tenant_id, fonte_ids))
        ids = {d.id for d in despesas}
        vinculadas = [i for i in repo.listar_iniciativas_vinculadas(db, ctx.tenant_id) if i.despesa_id in ids]
        partes = _agrupar_participantes(repo_finops.listar_participantes(db, ctx.tenant_id, [i.id for i in vinculadas]))
        self.iniciativas: dict[UUID, list[tuple[Iniciativa, fc.Calculo]]] = defaultdict(list)
        for ini in vinculadas:
            if ini.despesa_id is not None:
                self.iniciativas[ini.despesa_id].append(
                    (ini, finops_service.calculo_da_iniciativa(ini, partes[ini.id], ref))
                )


def _despesa_view(d: Despesa, c: _Contexto, hoje: date) -> dict:
    custo = _considerado(d, c.ref, c.faturas, referencia=True)
    if d.tipo_custo == dc.PONTUAL:
        anual = d.valor
    else:
        anual = custo.valor * 12
    return {
        "id": d.id,
        "nome": d.nome,
        "fornecedor": d.fornecedor,
        "categoria": d.categoria,
        "tipo_custo": d.tipo_custo,
        "valor": d.valor,
        "valor_anterior": d.valor_anterior,
        "status_auditoria": d.status_auditoria,
        "data_inicio": d.data_inicio,
        "data_renovacao": d.data_renovacao,
        "responsavel": d.responsavel,
        "observacoes": d.observacoes,
        "mes_acao": d.mes_acao,
        "fonte_id": d.fonte_id,
        "fonte_nome": c.nomes_fonte.get(d.fonte_id) if d.fonte_id else None,
        "custo_mensal_considerado": fc.q2(custo.valor),
        "origem_custo": custo.origem,
        "competencia_fatura": custo.competencia_fatura,
        "custo_anual": fc.q2(anual),
        "dias_para_renovacao": (d.data_renovacao - hoje).days if d.data_renovacao else None,
        "iniciativas": [
            {
                "id": ini.id,
                "titulo": ini.titulo,
                "status": calculo.status,
                "valor_mensal": fc.q2(calculo.valor_mensal),
                "conversao_despesa": ini.conversao_despesa,
            }
            for ini, calculo in sorted(c.iniciativas.get(d.id, []), key=lambda x: (x[0].titulo, x[0].id))
        ],
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    }


def _view_unica(db: Session, ctx: TenantContext, d: Despesa, referencia: date, hoje: date) -> dict:
    db.refresh(d)
    return _despesa_view(d, _Contexto(db, ctx, [d], referencia), hoje)


# --- inventário -------------------------------------------------------------------------------------------------


def listar_despesas(
    db: Session,
    ctx: TenantContext,
    status: str | None,
    categoria: str | None,
    referencia: date | None,
    hoje: date | None,
) -> list[dict]:
    despesas = repo.listar_despesas(db, ctx.tenant_id, status=status, categoria=categoria)
    contexto = _Contexto(db, ctx, despesas, referencia or mes_atual())
    h = hoje or hoje_servidor()
    return [_despesa_view(d, contexto, h) for d in despesas]


def obter_despesa(
    db: Session, ctx: TenantContext, despesa_id: UUID, referencia: date | None, hoje: date | None
) -> dict:
    d = _despesa_ou_404(db, ctx, despesa_id)
    return _view_unica(db, ctx, d, referencia or mes_atual(), hoje or hoje_servidor())


def criar_despesa(db: Session, ctx: TenantContext, dados: DespesaCreate) -> dict:
    if dados.fonte_id is not None:
        _fonte_ou_404(db, ctx, dados.fonte_id)
    despesa = Despesa(tenant_id=ctx.tenant_id, created_by=ctx.sub, **dados.model_dump())
    db.add(despesa)
    _persistir(db, "Conflito ao criar despesa")
    return _view_unica(db, ctx, despesa, mes_atual(), hoje_servidor())


def atualizar_despesa(db: Session, ctx: TenantContext, despesa_id: UUID, dados: DespesaUpdate) -> dict:
    despesa = _despesa_ou_404(db, ctx, despesa_id)
    enviados = dados.model_dump(exclude_unset=True)
    if despesa.status_auditoria in STATUS_ACAO:
        mudou_valor = "valor" in enviados and enviados["valor"] != despesa.valor
        mudou_tipo = "tipo_custo" in enviados and enviados["tipo_custo"] != despesa.tipo_custo
        if "status_auditoria" in enviados or mudou_valor or mudou_tipo:
            raise ConflictError("Despesa cancelada/renegociada: reverta antes de mudar status, valor ou tipo de custo")
    if enviados.get("fonte_id") is not None:
        _fonte_ou_404(db, ctx, enviados["fonte_id"])
    _aplicar(
        despesa,
        enviados,
        ("fornecedor", "data_inicio", "data_renovacao", "responsavel", "observacoes", "fonte_id"),
        ("nome", "categoria", "tipo_custo", "valor", "status_auditoria"),
    )
    _persistir(db, "Conflito ao atualizar despesa")
    return _view_unica(db, ctx, despesa, mes_atual(), hoje_servidor())


def remover_despesa(db: Session, ctx: TenantContext, despesa_id: UUID) -> None:
    despesa = _despesa_ou_404(db, ctx, despesa_id)
    if repo.listar_iniciativas_vinculadas(db, ctx.tenant_id, despesa.id):
        raise ConflictError("Despesa vinculada a iniciativas: reverta ou desvincule antes de excluir")
    db.delete(despesa)
    db.flush()


# --- ações ------------------------------------------------------------------------------------------------------


def _criar_conversao(
    db: Session,
    ctx: TenantContext,
    d: Despesa,
    prefixo: str,
    valor_mensal: Decimal,
    mes: date,
    janela: int,
    obs: str | None,
) -> Iniciativa:
    ini = Iniciativa(
        tenant_id=ctx.tenant_id,
        created_by=ctx.sub,
        titulo=f"{prefixo}: {d.nome}"[:160],
        descricao=obs,
        tipo="OTIMIZACAO_CUSTO",
        modo_calculo=fc.DIRETO_REAIS,
        valor_mensal=valor_mensal,
        mes_inicio=mes,
        janela_meses=janela,
        fonte_id=d.fonte_id,
        despesa_id=d.id,
        conversao_despesa=True,
    )
    db.add(ini)
    _persistir(db, "Conflito ao criar iniciativa de conversão")
    return ini


def _resultado_acao(db: Session, ctx: TenantContext, d: Despesa, ini: Iniciativa | None) -> dict:
    ref = mes_atual()
    return {
        "despesa": _view_unica(db, ctx, d, ref, hoje_servidor()),
        "iniciativa": finops_service.view_completa(db, ctx, ini, ref) if ini is not None else None,
    }


def cancelar(db: Session, ctx: TenantContext, despesa_id: UUID, dados: CancelarIn) -> dict:
    d = _despesa_ou_404(db, ctx, despesa_id)
    if d.status_auditoria in STATUS_ACAO:
        raise ConflictError("Despesa já cancelada ou renegociada")
    mes = fc.primeiro_dia(dados.mes) if dados.mes else mes_atual()
    ini = None
    valor = d.valor
    d.status_auditoria = dc.CANCELADO
    d.mes_acao = mes
    _persistir(db, "Conflito ao cancelar despesa")
    if d.tipo_custo == dc.RECORRENTE_MENSAL and valor > 0:
        ini = _criar_conversao(db, ctx, d, "Cancelamento", valor, mes, dados.janela_meses, dados.observacao)
    return _resultado_acao(db, ctx, d, ini)


def renegociar(db: Session, ctx: TenantContext, despesa_id: UUID, dados: RenegociarIn) -> dict:
    d = _despesa_ou_404(db, ctx, despesa_id)
    if d.tipo_custo != dc.RECORRENTE_MENSAL:
        raise HTTPException(422, "Só despesas recorrentes mensais podem ser renegociadas")
    if d.status_auditoria in STATUS_ACAO:
        raise ConflictError("Despesa já cancelada ou renegociada")
    if dados.novo_valor >= d.valor:
        raise HTTPException(422, "novo_valor deve ser menor que o valor atual")
    mes = fc.primeiro_dia(dados.mes) if dados.mes else mes_atual()
    economia = d.valor - dados.novo_valor
    d.valor_anterior = d.valor
    d.valor = dados.novo_valor
    d.status_auditoria = dc.RENEGOCIADO
    d.mes_acao = mes
    _persistir(db, "Conflito ao renegociar despesa")
    ini = _criar_conversao(db, ctx, d, "Renegociação", economia, mes, dados.janela_meses, dados.observacao)
    return _resultado_acao(db, ctx, d, ini)


def reverter(db: Session, ctx: TenantContext, despesa_id: UUID, dados: ReverterIn) -> dict:
    d = _despesa_ou_404(db, ctx, despesa_id)
    if d.status_auditoria not in STATUS_ACAO:
        raise ConflictError("Só despesas canceladas ou renegociadas podem ser revertidas")
    for ini in repo.listar_iniciativas_vinculadas(db, ctx.tenant_id, d.id):
        if ini.conversao_despesa:
            for p in repo_finops.listar_participantes(db, ctx.tenant_id, [ini.id]):
                db.delete(p)
            db.delete(ini)
    db.flush()
    if d.status_auditoria == dc.RENEGOCIADO and d.valor_anterior is not None:
        d.valor = d.valor_anterior
    d.valor_anterior = None
    d.mes_acao = None
    d.status_auditoria = dados.novo_status
    _persistir(db, "Conflito ao reverter despesa")
    return _view_unica(db, ctx, d, mes_atual(), hoje_servidor())


# --- orçamento --------------------------------------------------------------------------------------------------


def listar_orcamentos(db: Session, ctx: TenantContext, ano: int | None) -> Sequence[OrcamentoDespesa]:
    ano = ano or mes_atual().year
    return repo.listar_orcamentos(db, ctx.tenant_id, de=date(ano, 1, 1), ate=date(ano, 12, 1))


def salvar_orcamento(db: Session, ctx: TenantContext, competencia: date, dados: OrcamentoIn) -> OrcamentoDespesa:
    mes = fc.primeiro_dia(competencia)
    orc = repo.obter_orcamento(db, ctx.tenant_id, mes)
    if orc is None:
        orc = OrcamentoDespesa(
            tenant_id=ctx.tenant_id, created_by=ctx.sub, competencia=mes, valor=dados.valor, observacao=dados.observacao
        )
        db.add(orc)
    else:
        orc.valor = dados.valor
        orc.observacao = dados.observacao
    _persistir(db, "Conflito ao salvar orçamento")
    db.refresh(orc)
    return orc


def remover_orcamento(db: Session, ctx: TenantContext, competencia: date) -> None:
    orc = repo.obter_orcamento(db, ctx.tenant_id, fc.primeiro_dia(competencia))
    if orc is None:
        raise NotFoundError("Orçamento não encontrado")
    db.delete(orc)
    db.flush()


def orcamento_anual(db: Session, ctx: TenantContext, dados: OrcamentoAnualIn) -> dict:
    existentes = {
        o.competencia: o
        for o in repo.listar_orcamentos(db, ctx.tenant_id, de=date(dados.ano, 1, 1), ate=date(dados.ano, 12, 1))
    }
    criados = atualizados = ignorados = 0
    for indice, valor in enumerate(dc.distribuir_anual(dados.valor_anual), start=1):
        mes = date(dados.ano, indice, 1)
        atual = existentes.get(mes)
        if atual is None:
            db.add(OrcamentoDespesa(tenant_id=ctx.tenant_id, created_by=ctx.sub, competencia=mes, valor=valor))
            criados += 1
        elif dados.sobrescrever:
            atual.valor = valor
            atualizados += 1
        else:
            ignorados += 1
    _persistir(db, "Conflito ao distribuir orçamento anual")
    return {"criados": criados, "atualizados": atualizados, "ignorados": ignorados}


def _alertas_renovacao(despesas: Iterable[Despesa], custo_ref: dict[UUID, Decimal], hoje: date) -> list[dict[str, Any]]:
    """Alertas de renovação (URGENTE/ATENCAO) ordenados por data; regra única do painel e do Meu Dia."""
    alertas: list[dict[str, Any]] = []
    for d in despesas:
        alerta = dc.alerta_renovacao(d.status_auditoria, d.data_renovacao, hoje)
        if alerta is not None and d.data_renovacao is not None:
            dias, nivel = alerta
            alertas.append(
                {
                    "id": d.id,
                    "nome": d.nome,
                    "fornecedor": d.fornecedor,
                    "data_renovacao": d.data_renovacao,
                    "dias": dias,
                    "nivel": nivel,
                    "custo_mensal": fc.q2(custo_ref[d.id]),
                    "status_auditoria": d.status_auditoria,
                }
            )
    alertas.sort(key=lambda a: (a["data_renovacao"], a["nome"]))
    return alertas


def renovacoes_urgentes(db: Session, ctx: TenantContext, hoje: date) -> list[dict[str, Any]]:
    """Contratos não cancelados com renovação em até 30 dias (alerta URGENTE) a partir de `hoje`."""
    candidatas = [
        d
        for d in repo.listar_despesas(db, ctx.tenant_id)
        if (a := dc.alerta_renovacao(d.status_auditoria, d.data_renovacao, hoje)) is not None and a[1] == dc.URGENTE
    ]
    fonte_ids = {d.fonte_id for d in candidatas if d.fonte_id}
    faturas = _faturas_por_fonte(repo.listar_faturas_das_fontes(db, ctx.tenant_id, fonte_ids))
    ref = fc.primeiro_dia(hoje)
    custo_ref = {d.id: _considerado(d, ref, faturas, referencia=True).valor for d in candidatas}
    return [
        {k: a[k] for k in ("id", "nome", "fornecedor", "data_renovacao", "dias", "custo_mensal")}
        for a in _alertas_renovacao(candidatas, custo_ref, hoje)
    ]


# --- painel -----------------------------------------------------------------------------------------------------


def dashboard(db: Session, ctx: TenantContext, referencia: date | None, hoje: date | None) -> dict:
    ref = referencia or mes_atual()
    h = hoje or hoje_servidor()
    ano = ref.year
    despesas = repo.listar_despesas(db, ctx.tenant_id)
    c = _Contexto(db, ctx, despesas, ref)
    meses = [date(ano, m, 1) for m in range(1, 13)]
    orcamentos = {o.competencia: o.valor for o in repo.listar_orcamentos(db, ctx.tenant_id, de=meses[0], ate=meses[-1])}

    recorrentes = [d for d in despesas if d.tipo_custo == dc.RECORRENTE_MENSAL]
    custo_ref = {d.id: _considerado(d, ref, c.faturas, referencia=True).valor for d in despesas}
    run_rate = sum((custo_ref[d.id] for d in recorrentes if d.status_auditoria != dc.CANCELADO), ZERO)
    pontuais_ano = sum(
        (
            d.valor
            for d in despesas
            if d.tipo_custo == dc.PONTUAL
            and d.status_auditoria != dc.CANCELADO
            and d.data_inicio is not None
            and d.data_inicio.year == ano
        ),
        ZERO,
    )
    desperdicio = sum((custo_ref[d.id] for d in despesas if d.status_auditoria == dc.DESPERDICIO), ZERO)
    saving = novo_normal = ZERO
    for pares in c.iniciativas.values():
        for _, calculo in pares:
            if calculo.status == fc.EM_SAVING:
                saving += calculo.valor_mensal
            elif calculo.status == fc.NOVO_NORMAL:
                novo_normal += calculo.valor_mensal
    pontual_ref = sum((dc.pontual_no_mes(_entrada(d), ref) for d in despesas), ZERO)
    orcado_mes = orcamentos.get(ref)
    variacao = None if orcado_mes is None else orcado_mes - (run_rate + pontual_ref)
    contagem = {s: 0 for s in dc.STATUS_AUDITORIA}
    custo_status = {s: ZERO for s in dc.STATUS_AUDITORIA}
    for d in despesas:
        contagem[d.status_auditoria] += 1
        custo_status[d.status_auditoria] += custo_ref[d.id]

    alertas = _alertas_renovacao(despesas, custo_ref, h)

    categorias: dict[str, list[Despesa]] = defaultdict(list)
    for d in despesas:
        if d.status_auditoria != dc.CANCELADO:
            categorias[d.categoria].append(d)
    por_categoria: list[dict[str, Any]] = [
        {
            "categoria": nome,
            "quantidade": len(itens),
            "custo_mensal": fc.q2(sum((custo_ref[d.id] for d in itens), ZERO)),
        }
        for nome, itens in categorias.items()
    ]
    por_categoria.sort(key=lambda x: (-x["custo_mensal"], x["categoria"]))

    serie = []
    for mes in meses:
        recorrente = sum((_considerado(d, mes, c.faturas).valor for d in recorrentes), ZERO)
        pontual = sum((dc.pontual_no_mes(_entrada(d), mes) for d in despesas), ZERO)
        total = recorrente + pontual
        orcado = orcamentos.get(mes)
        serie.append(
            {
                "competencia": mes,
                "recorrente": fc.q2(recorrente),
                "pontual": fc.q2(pontual),
                "total": fc.q2(total),
                "orcado": None if orcado is None else fc.q2(orcado),
                "variacao": None if orcado is None else fc.q2(orcado - total),
            }
        )

    return {
        "referencia": ref,
        "hoje": h,
        "ano": ano,
        "kpis": {
            "run_rate_mensal": fc.q2(run_rate),
            "run_rate_anual": fc.q2(run_rate * 12),
            "pontuais_ano": fc.q2(pontuais_ano),
            "desperdicio_mensal": fc.q2(desperdicio),
            "saving_capturado_mensal": fc.q2(saving),
            "novo_normal_mensal": fc.q2(novo_normal),
            "orcado_mes": None if orcado_mes is None else fc.q2(orcado_mes),
            "variacao_orcamento": None if variacao is None else fc.q2(variacao),
            "auditoria_pct": dc.auditoria_pct(d.status_auditoria for d in despesas),
            "total_despesas": len(despesas),
            "por_status": contagem,
        },
        "alertas_renovacao": alertas,
        "por_categoria": por_categoria,
        "por_status": [
            {"status": s, "quantidade": contagem[s], "custo_mensal": fc.q2(custo_status[s])}
            for s in dc.STATUS_AUDITORIA
        ],
        "serie": serie,
    }

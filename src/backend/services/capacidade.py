from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.backend.core.exceptions import ConflictError, NotFoundError
from src.backend.models.capacidade import Grupo, Lancamento, Semana
from src.backend.repositories import capacidade as repo
from src.backend.schemas.capacidade import (
    GrupoCreate,
    GrupoUpdate,
    InicializarSemana,
    LancamentoCreate,
    LancamentoPar,
    LancamentoUpdate,
    SemanaCreate,
    SemanaUpdate,
)
from src.backend.services import rotinas as rotinas_service
from src.backend.tenancy.context import TenantContext

META_BUILD_MIN = 0.70
META_RUN_MAX = 0.30
ABERTO = "ABERTO"
RESOLVIDO = "RESOLVIDO"

GRUPOS_PADRAO: tuple[dict[str, str], ...] = (
    {"nome": "EngDados - Projetos", "categoria": "BUILD", "icone": "🚀", "cor": "#00AE9D"},
    {"nome": "EngDados - Suporte e Acessos (N2)", "categoria": "RUN", "icone": "🔑", "cor": "#3B82F6"},
    {"nome": "EngDados - Operações de Dados (N2)", "categoria": "RUN", "icone": "⚙️", "cor": "#6366F1"},
    {"nome": "EngDados - Sustentação e Incidentes (N2)", "categoria": "RUN", "icone": "🛡️", "cor": "#EC4899"},
    {"nome": "EngDados - Triagem N1", "categoria": "RUN", "icone": "📥", "cor": "#8B5CF6"},
    {"nome": "Rotinas (N0)", "categoria": "RUN", "icone": "⚡", "cor": "#0284C7"},
)


# --- cálculo puro -----------------------------------------------------------------------------------------------


def _ratio(parte: int, total: int) -> float:
    return parte / total if total > 0 else 0.0


def _arred(valor: float, casas: int) -> float:
    return round(valor, casas) + 0.0  # evita -0.0


def calcular_dashboard(
    grupos: Iterable[Grupo],
    lancamentos: Iterable[Lancamento],
    semana: Semana | None = None,
    rotinas: dict[str, dict[str, int]] | None = None,
) -> dict[str, Any]:
    """Agrega BUILD x RUN em Python sobre entidades já carregadas (somente grupos ativos).

    Se `semana` vier informada, os lançamentos devem ser os dessa semana; caso contrário, de todas.
    `rotinas` é a saída de `resumo_esforco`: ocorrências pendentes contam como abertas e concluídas como resolvidas,
    pela categoria da própria rotina.
    """
    ativos = sorted((g for g in grupos if g.ativo), key=lambda g: (g.categoria, g.nome))
    abertos_por_grupo: dict[UUID, int] = {g.id: 0 for g in ativos}
    resolvidos_por_grupo: dict[UUID, int] = {g.id: 0 for g in ativos}
    for lanc in lancamentos:
        if lanc.grupo_id not in abertos_por_grupo:
            continue  # grupo inativo ou desconhecido
        destino = resolvidos_por_grupo if lanc.status == RESOLVIDO else abertos_por_grupo
        destino[lanc.grupo_id] += lanc.quantidade

    itens: list[dict[str, Any]] = []
    totais = {"BUILD": [0, 0], "RUN": [0, 0]}  # [abertos, resolvidos]
    for g in ativos:
        abertos, resolvidos = abertos_por_grupo[g.id], resolvidos_por_grupo[g.id]
        total = abertos + resolvidos
        totais[g.categoria][0] += abertos
        totais[g.categoria][1] += resolvidos
        itens.append(
            {
                "id": g.id,
                "nome": g.nome,
                "categoria": g.categoria,
                "icone": g.icone,
                "cor": g.cor,
                "abertos": abertos,
                "resolvidos": resolvidos,
                "total": total,
                "taxa_resolucao": _arred(_ratio(resolvidos, total) * 100, 1),
                "pct_aberto": _arred(_ratio(abertos, total) * 100, 1),
                "pct_resolvido": _arred(_ratio(resolvidos, total) * 100, 1),
            }
        )

    itens_rotinas: list[dict[str, Any]] = []
    for categoria in ("BUILD", "RUN"):
        resumo = (rotinas or {}).get(categoria)
        if not resumo or resumo["ocorrencias"] <= 0:
            continue
        totais[categoria][0] += resumo["pendentes"]
        totais[categoria][1] += resumo["concluidas"]
        itens_rotinas.append(
            {
                "categoria": categoria,
                "abertos": resumo["pendentes"],
                "resolvidos": resumo["concluidas"],
                "total": resumo["ocorrencias"],
                "minutos_previstos": resumo["minutos_previstos"],
                "minutos_executados": resumo["minutos_executados"],
            }
        )

    abertos_build, resolvidos_build = totais["BUILD"]
    abertos_run, resolvidos_run = totais["RUN"]
    qtd_build = abertos_build + resolvidos_build
    qtd_run = abertos_run + resolvidos_run
    total_abertos = abertos_build + abertos_run
    total_resolvidos = resolvidos_build + resolvidos_run
    total = qtd_build + qtd_run

    perc_build = _ratio(qtd_build, total)
    perc_run = _ratio(qtd_run, total)
    perc_build_res = _ratio(resolvidos_build, total_resolvidos)
    perc_run_res = _ratio(resolvidos_run, total_resolvidos)
    perc_build_ab = _ratio(abertos_build, total_abertos)
    perc_run_ab = _ratio(abertos_run, total_abertos)

    return {
        "semana_id": semana.id if semana is not None else None,
        "periodo": semana.identificacao if semana is not None else "Todas as semanas",
        "meta_build_min": META_BUILD_MIN,
        "meta_run_max": META_RUN_MAX,
        "total": total,
        "total_abertos": total_abertos,
        "total_resolvidos": total_resolvidos,
        "taxa_resolucao": _arred(_ratio(total_resolvidos, total) * 100, 1),
        "qtd_build": qtd_build,
        "qtd_run": qtd_run,
        "perc_build": _arred(perc_build, 4),
        "perc_run": _arred(perc_run, 4),
        "build_atingiu_meta": perc_build >= META_BUILD_MIN,
        "run_atingiu_meta": perc_run <= META_RUN_MAX,
        "gap_build_pp": _arred((perc_build - META_BUILD_MIN) * 100, 1),
        "gap_run_pp": _arred((perc_run - META_RUN_MAX) * 100, 1),
        "resolvidos_build": resolvidos_build,
        "resolvidos_run": resolvidos_run,
        "perc_build_resolvidos": _arred(perc_build_res, 4),
        "perc_run_resolvidos": _arred(perc_run_res, 4),
        "resolvidos_build_atingiu_meta": perc_build_res >= META_BUILD_MIN,
        "resolvidos_run_atingiu_meta": perc_run_res <= META_RUN_MAX,
        "gap_build_resolvidos_pp": _arred((perc_build_res - META_BUILD_MIN) * 100, 1),
        "gap_run_resolvidos_pp": _arred((perc_run_res - META_RUN_MAX) * 100, 1),
        "abertos_build": abertos_build,
        "abertos_run": abertos_run,
        "perc_build_abertos": _arred(perc_build_ab, 4),
        "perc_run_abertos": _arred(perc_run_ab, 4),
        "groups": itens,
        "rotinas": itens_rotinas,
    }


# --- helpers ----------------------------------------------------------------------------------------------------


def _persistir(db: Session, mensagem: str) -> None:
    """Flush dentro de savepoint: conflito vira 409 sem invalidar a transação externa."""
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError as exc:
        raise ConflictError(mensagem) from exc


def _grupo_ou_404(db: Session, ctx: TenantContext, grupo_id: UUID) -> Grupo:
    grupo = repo.obter_grupo(db, ctx.tenant_id, grupo_id)
    if grupo is None:
        raise NotFoundError("Grupo não encontrado")
    return grupo


def _semana_ou_404(db: Session, ctx: TenantContext, semana_id: UUID) -> Semana:
    semana = repo.obter_semana(db, ctx.tenant_id, semana_id)
    if semana is None:
        raise NotFoundError("Semana não encontrada")
    return semana


def _lancamento_ou_404(db: Session, ctx: TenantContext, lancamento_id: UUID) -> Lancamento:
    lanc = repo.obter_lancamento(db, ctx.tenant_id, lancamento_id)
    if lanc is None:
        raise NotFoundError("Lançamento não encontrado")
    return lanc


def _view_lancamento(lanc: Lancamento, grupo: Grupo, semana: Semana) -> dict[str, Any]:
    return {
        "id": lanc.id,
        "grupo_id": lanc.grupo_id,
        "grupo_nome": grupo.nome,
        "grupo_categoria": grupo.categoria,
        "grupo_icone": grupo.icone,
        "grupo_cor": grupo.cor,
        "semana_id": lanc.semana_id,
        "semana_identificacao": semana.identificacao,
        "quantidade": lanc.quantidade,
        "status": lanc.status,
        "observacao": lanc.observacao,
        "created_at": lanc.created_at,
        "updated_at": lanc.updated_at,
    }


def _views(db: Session, ctx: TenantContext, itens: Sequence[Lancamento]) -> list[dict[str, Any]]:
    grupos = {g.id: g for g in repo.listar_grupos(db, ctx.tenant_id)}
    semanas = {s.id: s for s in repo.listar_semanas(db, ctx.tenant_id)}
    return [_view_lancamento(i, grupos[i.grupo_id], semanas[i.semana_id]) for i in itens]


# --- dashboard --------------------------------------------------------------------------------------------------


def dashboard(db: Session, ctx: TenantContext, semana_id: UUID | None) -> dict[str, Any]:
    semana = _semana_ou_404(db, ctx, semana_id) if semana_id is not None else None
    grupos = repo.listar_grupos(db, ctx.tenant_id, somente_ativos=True)
    lancamentos = repo.listar_lancamentos(db, ctx.tenant_id, semana_id=semana_id)
    resumo = rotinas_service.resumo_para_painel(db, ctx, semana, date.today())
    return calcular_dashboard(grupos, lancamentos, semana, resumo)


# --- grupos -----------------------------------------------------------------------------------------------------


def listar_grupos(db: Session, ctx: TenantContext) -> Sequence[Grupo]:
    return repo.listar_grupos(db, ctx.tenant_id)


def criar_grupo(db: Session, ctx: TenantContext, dados: GrupoCreate) -> Grupo:
    if repo.obter_grupo_por_nome(db, ctx.tenant_id, dados.nome) is not None:
        raise ConflictError("Já existe um grupo com este nome")
    grupo = Grupo(tenant_id=ctx.tenant_id, created_by=ctx.sub, nome=dados.nome, categoria=dados.categoria)
    if dados.icone is not None:
        grupo.icone = dados.icone
    if dados.cor is not None:
        grupo.cor = dados.cor
    db.add(grupo)
    _persistir(db, "Já existe um grupo com este nome")
    return grupo


def criar_grupos_padrao(db: Session, ctx: TenantContext) -> dict[str, int]:
    existentes = {g.nome for g in repo.listar_grupos(db, ctx.tenant_id)}
    criados = 0
    for padrao in GRUPOS_PADRAO:
        if padrao["nome"] in existentes:
            continue
        db.add(Grupo(tenant_id=ctx.tenant_id, created_by=ctx.sub, **padrao))
        criados += 1
    _persistir(db, "Conflito ao criar grupos padrão")
    return {"created": criados, "skipped": len(GRUPOS_PADRAO) - criados}


def atualizar_grupo(db: Session, ctx: TenantContext, grupo_id: UUID, dados: GrupoUpdate) -> Grupo:
    grupo = _grupo_ou_404(db, ctx, grupo_id)
    campos = dados.model_dump(exclude_unset=True)
    if campos.get("nome") is not None:
        outro = repo.obter_grupo_por_nome(db, ctx.tenant_id, campos["nome"])
        if outro is not None and outro.id != grupo.id:
            raise ConflictError("Já existe um grupo com este nome")
    for nome in ("nome", "categoria", "icone", "cor", "ativo"):
        if campos.get(nome) is not None:
            setattr(grupo, nome, campos[nome])
    _persistir(db, "Já existe um grupo com este nome")
    return grupo


def remover_grupo(db: Session, ctx: TenantContext, grupo_id: UUID) -> None:
    db.delete(_grupo_ou_404(db, ctx, grupo_id))
    db.flush()


# --- semanas ----------------------------------------------------------------------------------------------------


def listar_semanas(db: Session, ctx: TenantContext) -> Sequence[Semana]:
    return repo.listar_semanas(db, ctx.tenant_id)


def criar_semana(db: Session, ctx: TenantContext, dados: SemanaCreate) -> Semana:
    if repo.obter_semana_por_identificacao(db, ctx.tenant_id, dados.identificacao) is not None:
        raise ConflictError("Já existe uma semana com esta identificação")
    semana = Semana(
        tenant_id=ctx.tenant_id,
        created_by=ctx.sub,
        identificacao=dados.identificacao,
        data_inicio=dados.data_inicio,
        data_fim=dados.data_fim,
    )
    db.add(semana)
    _persistir(db, "Já existe uma semana com esta identificação")
    return semana


def atualizar_semana(db: Session, ctx: TenantContext, semana_id: UUID, dados: SemanaUpdate) -> Semana:
    semana = _semana_ou_404(db, ctx, semana_id)
    campos = dados.model_dump(exclude_unset=True)
    inicio: date | None = campos.get("data_inicio", semana.data_inicio)
    fim: date | None = campos.get("data_fim", semana.data_fim)
    if inicio is not None and fim is not None and fim < inicio:
        raise HTTPException(422, "data_fim deve ser maior ou igual a data_inicio")
    nova = campos.get("identificacao")
    if nova is not None and nova != semana.identificacao:
        outra = repo.obter_semana_por_identificacao(db, ctx.tenant_id, nova)
        if outra is not None and outra.id != semana.id:
            raise ConflictError("Já existe uma semana com esta identificação")
        semana.identificacao = nova
    semana.data_inicio = inicio
    semana.data_fim = fim
    _persistir(db, "Já existe uma semana com esta identificação")
    return semana


def remover_semana(db: Session, ctx: TenantContext, semana_id: UUID) -> None:
    db.delete(_semana_ou_404(db, ctx, semana_id))
    db.flush()


# --- lançamentos ------------------------------------------------------------------------------------------------


def listar_lancamentos(
    db: Session, ctx: TenantContext, grupo_id: UUID | None, semana_id: UUID | None
) -> list[dict[str, Any]]:
    itens = repo.listar_lancamentos(db, ctx.tenant_id, grupo_id=grupo_id, semana_id=semana_id)
    grupos = {g.id: g for g in repo.listar_grupos(db, ctx.tenant_id)}
    semanas = {s.id: s for s in repo.listar_semanas(db, ctx.tenant_id)}
    # Ordenação estável em passes: do critério menos para o mais significativo.
    ordenados = sorted(itens, key=lambda i: i.status)
    ordenados.sort(key=lambda i: (grupos[i.grupo_id].categoria, grupos[i.grupo_id].nome))
    ordenados.sort(key=lambda i: (semanas[i.semana_id].created_at, str(i.semana_id)), reverse=True)
    return [_view_lancamento(i, grupos[i.grupo_id], semanas[i.semana_id]) for i in ordenados]


def obter_lancamento(db: Session, ctx: TenantContext, lancamento_id: UUID) -> dict[str, Any]:
    return _views(db, ctx, [_lancamento_ou_404(db, ctx, lancamento_id)])[0]


def criar_lancamento(db: Session, ctx: TenantContext, dados: LancamentoCreate) -> dict[str, Any]:
    grupo = _grupo_ou_404(db, ctx, dados.grupo_id)
    semana = _semana_ou_404(db, ctx, dados.semana_id)
    lanc = Lancamento(
        tenant_id=ctx.tenant_id,
        created_by=ctx.sub,
        grupo_id=grupo.id,
        semana_id=semana.id,
        quantidade=dados.quantidade,
        status=dados.status,
        observacao=dados.observacao,
    )
    db.add(lanc)
    _persistir(db, "Conflito ao criar lançamento")
    db.refresh(lanc)
    return _view_lancamento(lanc, grupo, semana)


def atualizar_lancamento(
    db: Session, ctx: TenantContext, lancamento_id: UUID, dados: LancamentoUpdate
) -> dict[str, Any]:
    lanc = _lancamento_ou_404(db, ctx, lancamento_id)
    campos = dados.model_dump(exclude_unset=True)
    grupo = _grupo_ou_404(db, ctx, campos["grupo_id"]) if campos.get("grupo_id") else None
    semana = _semana_ou_404(db, ctx, campos["semana_id"]) if campos.get("semana_id") else None
    for nome in ("grupo_id", "semana_id", "quantidade", "status"):
        if campos.get(nome) is not None:
            setattr(lanc, nome, campos[nome])
    if "observacao" in campos:
        lanc.observacao = campos["observacao"]
    _persistir(db, "Conflito ao atualizar lançamento")
    db.refresh(lanc)
    grupo = grupo or _grupo_ou_404(db, ctx, lanc.grupo_id)
    semana = semana or _semana_ou_404(db, ctx, lanc.semana_id)
    return _view_lancamento(lanc, grupo, semana)


def remover_lancamento(db: Session, ctx: TenantContext, lancamento_id: UUID) -> None:
    db.delete(_lancamento_ou_404(db, ctx, lancamento_id))
    db.flush()


def inicializar_semana(db: Session, ctx: TenantContext, dados: InicializarSemana) -> dict[str, int]:
    semana = _semana_ou_404(db, ctx, dados.semana_id)
    todos = repo.listar_grupos(db, ctx.tenant_id)
    if dados.grupo_ids:
        por_id = {g.id: g for g in todos}
        pedidos = list(dict.fromkeys(dados.grupo_ids))
        if any(gid not in por_id for gid in pedidos):
            raise NotFoundError("Grupo não encontrado")
        alvo = [por_id[gid] for gid in pedidos]
    else:
        alvo = list(todos)
    existentes = {(i.grupo_id, i.status) for i in repo.listar_lancamentos(db, ctx.tenant_id, semana_id=semana.id)}
    criados = pulados = 0
    for grupo in alvo:
        for status in (ABERTO, RESOLVIDO):
            if (grupo.id, status) in existentes:
                pulados += 1
                continue
            db.add(
                Lancamento(
                    tenant_id=ctx.tenant_id,
                    created_by=ctx.sub,
                    grupo_id=grupo.id,
                    semana_id=semana.id,
                    quantidade=dados.default_qtd,
                    status=status,
                )
            )
            criados += 1
    _persistir(db, "Conflito ao inicializar semana")
    return {"created": criados, "skipped": pulados, "total_grupos": len(alvo)}


def salvar_par(db: Session, ctx: TenantContext, dados: LancamentoPar) -> list[dict[str, Any]]:
    grupo = _grupo_ou_404(db, ctx, dados.grupo_id)
    semana = _semana_ou_404(db, ctx, dados.semana_id)
    valores = ((ABERTO, dados.qtd_aberto, dados.obs_aberto), (RESOLVIDO, dados.qtd_resolvido, dados.obs_resolvido))
    resultado: list[Lancamento] = []
    for status, quantidade, obs in valores:
        lanc = repo.obter_lancamento_por_chave(db, ctx.tenant_id, grupo.id, semana.id, status)
        if lanc is None:
            lanc = Lancamento(
                tenant_id=ctx.tenant_id,
                created_by=ctx.sub,
                grupo_id=grupo.id,
                semana_id=semana.id,
                status=status,
                quantidade=quantidade,
                observacao=obs or None,
            )
            db.add(lanc)
        else:
            lanc.quantidade = quantidade
            lanc.observacao = obs or None
        resultado.append(lanc)
    _persistir(db, "Conflito ao salvar lançamentos")
    for lanc in resultado:
        db.refresh(lanc)
    return [_view_lancamento(lanc, grupo, semana) for lanc in resultado]

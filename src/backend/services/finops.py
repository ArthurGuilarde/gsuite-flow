from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.backend.core.exceptions import ConflictError, NotFoundError
from src.backend.models.finops import Fatura, FonteCusto, Iniciativa, IniciativaParticipante, PerfilCusto
from src.backend.repositories import finops as repo
from src.backend.schemas.finops import (
    FaturaCreate,
    FaturaUpdate,
    FonteCreate,
    FonteUpdate,
    IniciativaIn,
    PerfilCreate,
    PerfilUpdate,
)
from src.backend.services import finops_calculos as calc
from src.backend.tenancy.context import TenantContext

TIPOS = ("MELHORIA", "AUTOMACAO", "OTIMIZACAO_CUSTO")
ZERO = Decimal(0)
MAX_MESES_DASHBOARD = 36


# --- helpers ----------------------------------------------------------------------------------------------------


def _persistir(db: Session, mensagem: str) -> None:
    """Flush dentro de savepoint: conflito vira 409 sem invalidar a transação externa."""
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError as exc:
        raise ConflictError(mensagem) from exc


def mes_atual() -> date:
    return calc.primeiro_dia(date.today())


def parse_mes_param(valor: str | None, nome: str) -> date | None:
    if valor is None or valor == "":
        return None
    try:
        return calc.parse_competencia(valor)
    except ValueError as exc:
        raise HTTPException(422, f"{nome} deve estar no formato YYYY-MM") from exc


def _aplicar(obj: object, dados: dict, nulaveis: tuple[str, ...], obrigatorios: tuple[str, ...]) -> None:
    for campo, valor in dados.items():
        if valor is None and campo in obrigatorios:
            raise HTTPException(422, f"{campo} não pode ser nulo")
        if campo in nulaveis or campo in obrigatorios:
            setattr(obj, campo, valor)


def _perfil_ou_404(db: Session, ctx: TenantContext, perfil_id: UUID) -> PerfilCusto:
    perfil = repo.obter_perfil(db, ctx.tenant_id, perfil_id)
    if perfil is None:
        raise NotFoundError("Perfil não encontrado")
    return perfil


def _fonte_ou_404(db: Session, ctx: TenantContext, fonte_id: UUID) -> FonteCusto:
    fonte = repo.obter_fonte(db, ctx.tenant_id, fonte_id)
    if fonte is None:
        raise NotFoundError("Fonte de custo não encontrada")
    return fonte


def _fatura_ou_404(db: Session, ctx: TenantContext, fatura_id: UUID) -> Fatura:
    fatura = repo.obter_fatura(db, ctx.tenant_id, fatura_id)
    if fatura is None:
        raise NotFoundError("Fatura não encontrada")
    return fatura


def _iniciativa_ou_404(db: Session, ctx: TenantContext, iniciativa_id: UUID) -> Iniciativa:
    ini = repo.obter_iniciativa(db, ctx.tenant_id, iniciativa_id)
    if ini is None:
        raise NotFoundError("Iniciativa não encontrada")
    return ini


# --- perfis -----------------------------------------------------------------------------------------------------


def listar_perfis(db: Session, ctx: TenantContext) -> Sequence[PerfilCusto]:
    return repo.listar_perfis(db, ctx.tenant_id)


def criar_perfil(db: Session, ctx: TenantContext, dados: PerfilCreate) -> PerfilCusto:
    perfil = PerfilCusto(tenant_id=ctx.tenant_id, created_by=ctx.sub, **dados.model_dump())
    db.add(perfil)
    _persistir(db, "Já existe um perfil com este nome")
    db.refresh(perfil)
    return perfil


def atualizar_perfil(db: Session, ctx: TenantContext, perfil_id: UUID, dados: PerfilUpdate) -> PerfilCusto:
    perfil = _perfil_ou_404(db, ctx, perfil_id)
    _aplicar(perfil, dados.model_dump(exclude_unset=True), (), ("nome", "custo_hora", "ativo"))
    _persistir(db, "Já existe um perfil com este nome")
    db.refresh(perfil)
    return perfil


def remover_perfil(db: Session, ctx: TenantContext, perfil_id: UUID) -> None:
    # Participantes guardam snapshot do custo/hora; remover o perfil não os afeta.
    db.delete(_perfil_ou_404(db, ctx, perfil_id))
    db.flush()


# --- fontes -----------------------------------------------------------------------------------------------------


def listar_fontes(db: Session, ctx: TenantContext) -> Sequence[FonteCusto]:
    return repo.listar_fontes(db, ctx.tenant_id)


def criar_fonte(db: Session, ctx: TenantContext, dados: FonteCreate) -> FonteCusto:
    fonte = FonteCusto(tenant_id=ctx.tenant_id, created_by=ctx.sub, **dados.model_dump())
    db.add(fonte)
    _persistir(db, "Já existe uma fonte de custo com este nome")
    db.refresh(fonte)
    return fonte


def atualizar_fonte(db: Session, ctx: TenantContext, fonte_id: UUID, dados: FonteUpdate) -> FonteCusto:
    fonte = _fonte_ou_404(db, ctx, fonte_id)
    _aplicar(fonte, dados.model_dump(exclude_unset=True), ("descricao", "metrica_nome"), ("nome", "ativo"))
    _persistir(db, "Já existe uma fonte de custo com este nome")
    db.refresh(fonte)
    return fonte


def remover_fonte(db: Session, ctx: TenantContext, fonte_id: UUID) -> None:
    fonte = _fonte_ou_404(db, ctx, fonte_id)
    if repo.listar_iniciativas_da_fonte(db, ctx.tenant_id, fonte.id):
        raise ConflictError("Fonte de custo vinculada a iniciativas")
    for fatura in repo.listar_faturas(db, ctx.tenant_id, fonte_id=fonte.id):
        db.delete(fatura)
    db.flush()
    db.delete(fonte)
    db.flush()


# --- faturas ----------------------------------------------------------------------------------------------------


def _fatura_view(f: Fatura, fonte_nome: str) -> dict:
    return {
        "id": f.id,
        "fonte_id": f.fonte_id,
        "fonte_nome": fonte_nome,
        "competencia": f.competencia,
        "valor_orcado": f.valor_orcado,
        "valor_realizado": f.valor_realizado,
        "variacao": calc.variacao(f.valor_orcado, f.valor_realizado),
        "metrica_valor": f.metrica_valor,
        "custo_unitario": _q4(calc.custo_unitario(f.valor_realizado, f.metrica_valor)),
        "observacao": f.observacao,
        "created_at": f.created_at,
        "updated_at": f.updated_at,
    }


def _q4(valor: Decimal | None) -> Decimal | None:
    return None if valor is None else calc.q4(valor)


def _fatura_completa(db: Session, ctx: TenantContext, fatura: Fatura) -> dict:
    db.refresh(fatura)
    fonte = repo.obter_fonte(db, ctx.tenant_id, fatura.fonte_id)
    return _fatura_view(fatura, fonte.nome if fonte else "")


def listar_faturas(
    db: Session, ctx: TenantContext, fonte_id: UUID | None, de: date | None, ate: date | None
) -> list[dict]:
    faturas = repo.listar_faturas(db, ctx.tenant_id, fonte_id=fonte_id, de=de, ate=ate)
    nomes = {f.id: f.nome for f in repo.listar_fontes(db, ctx.tenant_id)}
    ordenadas = sorted(faturas, key=lambda f: (nomes.get(f.fonte_id, ""), f.id))
    ordenadas.sort(key=lambda f: f.competencia, reverse=True)
    return [_fatura_view(f, nomes.get(f.fonte_id, "")) for f in ordenadas]


def criar_fatura(db: Session, ctx: TenantContext, dados: FaturaCreate) -> dict:
    _fonte_ou_404(db, ctx, dados.fonte_id)
    campos = dados.model_dump()
    campos["competencia"] = calc.primeiro_dia(campos["competencia"])
    fatura = Fatura(tenant_id=ctx.tenant_id, created_by=ctx.sub, **campos)
    db.add(fatura)
    _persistir(db, "Já existe fatura desta fonte nesta competência")
    return _fatura_completa(db, ctx, fatura)


def atualizar_fatura(db: Session, ctx: TenantContext, fatura_id: UUID, dados: FaturaUpdate) -> dict:
    fatura = _fatura_ou_404(db, ctx, fatura_id)
    enviados = dados.model_dump(exclude_unset=True)
    if enviados.get("competencia") is not None:
        enviados["competencia"] = calc.primeiro_dia(enviados["competencia"])
    _aplicar(fatura, enviados, ("valor_orcado", "metrica_valor", "observacao"), ("competencia", "valor_realizado"))
    _persistir(db, "Já existe fatura desta fonte nesta competência")
    return _fatura_completa(db, ctx, fatura)


def remover_fatura(db: Session, ctx: TenantContext, fatura_id: UUID) -> None:
    db.delete(_fatura_ou_404(db, ctx, fatura_id))
    db.flush()


# --- iniciativas ------------------------------------------------------------------------------------------------


def _entrada_orm(ini: Iniciativa, partes: Sequence[IniciativaParticipante]) -> calc.IniciativaEntrada:
    return calc.IniciativaEntrada(
        modo_calculo=ini.modo_calculo,
        mes_inicio=ini.mes_inicio,
        janela_meses=ini.janela_meses,
        mes_encerramento=ini.mes_encerramento,
        valor_mensal=ini.valor_mensal,
        frequencia=ini.frequencia,
        participantes=[
            calc.ParticipanteEntrada(p.custo_hora, p.qtd_pessoas, p.horas_antes, p.horas_depois) for p in partes
        ],
        investimento_reais=ini.investimento_reais,
        investimento_horas=ini.investimento_horas,
        investimento_custo_hora=ini.investimento_custo_hora,
    )


def _entrada_dto(dados: IniciativaIn) -> calc.IniciativaEntrada:
    return calc.IniciativaEntrada(
        modo_calculo=dados.modo_calculo,
        mes_inicio=calc.primeiro_dia(dados.mes_inicio),
        janela_meses=dados.janela_meses,
        mes_encerramento=calc.primeiro_dia(dados.mes_encerramento) if dados.mes_encerramento else None,
        valor_mensal=dados.valor_mensal,
        frequencia=dados.frequencia,
        participantes=[
            calc.ParticipanteEntrada(p.custo_hora, p.qtd_pessoas, p.horas_antes, p.horas_depois)
            for p in dados.participantes
        ],
        investimento_reais=dados.investimento_reais,
        investimento_horas=dados.investimento_horas,
        investimento_custo_hora=dados.investimento_custo_hora,
    )


def _calculo_view(c: calc.Calculo) -> dict:
    return {
        "valor_mensal": calc.q2(c.valor_mensal),
        "horas_mes": calc.q2(c.horas_mes),
        "fte": calc.q2(c.fte),
        "perc_reducao": None if c.perc_reducao is None else calc.q2(c.perc_reducao),
        "fim_janela": c.fim_janela,
        "meses_janela": c.meses_janela,
        "status": c.status,
        "meses_contados": c.meses_contados,
        "saving_acumulado": calc.q2(c.saving_acumulado),
        "saving_janela": calc.q2(c.saving_janela),
        "investimento_total": calc.q2(c.investimento_total),
        "roi_janela_pct": None if c.roi_janela_pct is None else calc.q1(c.roi_janela_pct),
        "payback_meses": c.payback_meses,
        "se_paga_na_janela": c.se_paga_na_janela,
    }


def _iniciativa_view(
    ini: Iniciativa, partes: Sequence[IniciativaParticipante], fonte_nome: str | None, referencia: date
) -> dict:
    resultado = calc.calcular_iniciativa(_entrada_orm(ini, partes), referencia)
    return {
        "id": ini.id,
        "titulo": ini.titulo,
        "descricao": ini.descricao,
        "tipo": ini.tipo,
        "modo_calculo": ini.modo_calculo,
        "valor_mensal": ini.valor_mensal,
        "frequencia": ini.frequencia,
        "mes_inicio": ini.mes_inicio,
        "janela_meses": ini.janela_meses,
        "mes_encerramento": ini.mes_encerramento,
        "fonte_id": ini.fonte_id,
        "fonte_nome": fonte_nome,
        "investimento_reais": ini.investimento_reais,
        "investimento_horas": ini.investimento_horas,
        "investimento_custo_hora": ini.investimento_custo_hora,
        "participantes": [
            {
                "id": p.id,
                "perfil_nome": p.perfil_nome,
                "custo_hora": p.custo_hora,
                "qtd_pessoas": p.qtd_pessoas,
                "horas_antes": p.horas_antes,
                "horas_depois": p.horas_depois,
                "horas_mes": calc.q2(c.horas_mes),
                "valor_mensal": calc.q2(c.valor_mensal),
            }
            for p, c in zip(partes, resultado.participantes, strict=True)
        ],
        "calculo": _calculo_view(resultado),
        "created_at": ini.created_at,
        "updated_at": ini.updated_at,
    }


def _view_completa(db: Session, ctx: TenantContext, ini: Iniciativa, referencia: date) -> dict:
    db.refresh(ini)
    partes = repo.listar_participantes(db, ctx.tenant_id, [ini.id])
    fonte = repo.obter_fonte(db, ctx.tenant_id, ini.fonte_id) if ini.fonte_id else None
    return _iniciativa_view(ini, partes, fonte.nome if fonte else None, referencia)


def _campos_iniciativa(dados: IniciativaIn) -> dict:
    campos = dados.model_dump(exclude={"participantes"})
    campos["mes_inicio"] = calc.primeiro_dia(campos["mes_inicio"])
    if campos["mes_encerramento"] is not None:
        campos["mes_encerramento"] = calc.primeiro_dia(campos["mes_encerramento"])
    return campos


def _novos_participantes(ctx: TenantContext, ini_id: UUID, dados: IniciativaIn) -> list[IniciativaParticipante]:
    return [
        IniciativaParticipante(
            tenant_id=ctx.tenant_id, created_by=ctx.sub, iniciativa_id=ini_id, ordem=i, **p.model_dump()
        )
        for i, p in enumerate(dados.participantes)
    ]


def listar_iniciativas(
    db: Session, ctx: TenantContext, tipo: str | None, status: str | None, referencia: date | None
) -> list[dict]:
    ref = referencia or mes_atual()
    iniciativas = repo.listar_iniciativas(db, ctx.tenant_id, tipo=tipo)
    partes = _agrupar_participantes(repo.listar_participantes(db, ctx.tenant_id, [i.id for i in iniciativas]))
    nomes = {f.id: f.nome for f in repo.listar_fontes(db, ctx.tenant_id)}
    views = [_iniciativa_view(i, partes[i.id], nomes.get(i.fonte_id) if i.fonte_id else None, ref) for i in iniciativas]
    if status is not None:
        views = [v for v in views if v["calculo"]["status"] == status]
    views.sort(key=lambda v: v["titulo"])
    views.sort(key=lambda v: v["mes_inicio"], reverse=True)
    return views


def _agrupar_participantes(partes: Sequence[IniciativaParticipante]) -> dict[UUID, list[IniciativaParticipante]]:
    grupos: dict[UUID, list[IniciativaParticipante]] = defaultdict(list)
    for p in partes:
        grupos[p.iniciativa_id].append(p)
    return grupos


def obter_iniciativa(db: Session, ctx: TenantContext, iniciativa_id: UUID, referencia: date | None) -> dict:
    ini = _iniciativa_ou_404(db, ctx, iniciativa_id)
    return _view_completa(db, ctx, ini, referencia or mes_atual())


def criar_iniciativa(db: Session, ctx: TenantContext, dados: IniciativaIn) -> dict:
    if dados.fonte_id is not None:
        _fonte_ou_404(db, ctx, dados.fonte_id)
    ini = Iniciativa(tenant_id=ctx.tenant_id, created_by=ctx.sub, **_campos_iniciativa(dados))
    db.add(ini)
    _persistir(db, "Conflito ao criar iniciativa")
    db.add_all(_novos_participantes(ctx, ini.id, dados))
    _persistir(db, "Conflito ao criar participantes")
    return _view_completa(db, ctx, ini, mes_atual())


def atualizar_iniciativa(db: Session, ctx: TenantContext, iniciativa_id: UUID, dados: IniciativaIn) -> dict:
    ini = _iniciativa_ou_404(db, ctx, iniciativa_id)
    if dados.fonte_id is not None:
        _fonte_ou_404(db, ctx, dados.fonte_id)
    for campo, valor in _campos_iniciativa(dados).items():
        setattr(ini, campo, valor)
    for antigo in repo.listar_participantes(db, ctx.tenant_id, [ini.id]):
        db.delete(antigo)
    db.flush()
    db.add_all(_novos_participantes(ctx, ini.id, dados))
    _persistir(db, "Conflito ao atualizar iniciativa")
    return _view_completa(db, ctx, ini, mes_atual())


def remover_iniciativa(db: Session, ctx: TenantContext, iniciativa_id: UUID) -> None:
    ini = _iniciativa_ou_404(db, ctx, iniciativa_id)
    for p in repo.listar_participantes(db, ctx.tenant_id, [ini.id]):
        db.delete(p)
    db.flush()
    db.delete(ini)
    db.flush()


def simular(dados: IniciativaIn, referencia: date | None) -> dict:
    """Prévia sem gravar: só cálculo, nenhum acesso ao banco."""
    resultado = calc.calcular_iniciativa(_entrada_dto(dados), referencia or mes_atual())
    return {
        "participantes": [
            {"horas_mes": calc.q2(c.horas_mes), "valor_mensal": calc.q2(c.valor_mensal)}
            for c in resultado.participantes
        ],
        "calculo": _calculo_view(resultado),
    }


# --- dashboard --------------------------------------------------------------------------------------------------


def _soma(valores: Sequence[Decimal]) -> Decimal:
    return sum(valores, ZERO)


def _orcado_realizado(faturas: Sequence[Fatura]) -> tuple[Decimal | None, Decimal | None]:
    if not faturas:
        return None, None
    orcados = [f.valor_orcado for f in faturas if f.valor_orcado is not None]
    return (_soma(orcados) if orcados else None), _soma([f.valor_realizado for f in faturas])


def _q2n(valor: Decimal | None) -> Decimal | None:
    return None if valor is None else calc.q2(valor)


def dashboard(db: Session, ctx: TenantContext, de: date | None, ate: date | None, referencia: date | None) -> dict:
    ref = referencia or mes_atual()
    if de is None:
        de = date(ref.year, 1, 1)
    if ate is None:
        ate = date(de.year, 12, 1)
    if ate < de:
        raise HTTPException(422, "ate deve ser maior ou igual a de")
    meses = calc.intervalo_meses(de, ate)
    if len(meses) > MAX_MESES_DASHBOARD:
        raise HTTPException(422, f"Intervalo máximo de {MAX_MESES_DASHBOARD} meses")

    iniciativas = repo.listar_iniciativas(db, ctx.tenant_id)
    partes = _agrupar_participantes(repo.listar_participantes(db, ctx.tenant_id, [i.id for i in iniciativas]))
    fontes = repo.listar_fontes(db, ctx.tenant_id)
    faturas = repo.listar_faturas(db, ctx.tenant_id, de=de, ate=ate)

    resumos: list[tuple[Iniciativa, calc.IniciativaResumo]] = []
    for ini in iniciativas:
        c = calc.calcular_iniciativa(_entrada_orm(ini, partes[ini.id]), ref)
        resumos.append(
            (
                ini,
                calc.IniciativaResumo(
                    ini.modo_calculo, ini.tipo, ini.mes_inicio, ini.janela_meses, ini.mes_encerramento, c
                ),
            )
        )
    serie = calc.serie_mensal((r for _, r in resumos), de, ate, ref)

    por_mes: dict[date, list[Fatura]] = defaultdict(list)
    por_fonte_mes: dict[tuple[UUID, date], Fatura] = {}
    por_fonte: dict[UUID, list[Fatura]] = defaultdict(list)
    for f in faturas:
        por_mes[f.competencia].append(f)
        por_fonte_mes[(f.fonte_id, f.competencia)] = f
        por_fonte[f.fonte_id].append(f)

    serie_view = []
    for p in serie:
        orc, real = _orcado_realizado(por_mes.get(p.competencia, []))
        serie_view.append(
            {
                "competencia": p.competencia,
                "saving_direto": calc.q2(p.saving_direto),
                "saving_horas": calc.q2(p.saving_horas),
                "saving_total": calc.q2(p.saving_total),
                "projetado": p.projetado,
                "orcado": _q2n(orc),
                "realizado": _q2n(real),
                "variacao": _q2n(calc.variacao(orc, real)),
            }
        )

    saving_realizado = _soma([p.saving_total for p in serie if not p.projetado])
    saving_projetado = _soma([p.saving_total for p in serie if p.projetado])
    em_saving = [(i, r) for i, r in resumos if r.calculo.status == calc.EM_SAVING]
    novo_normal = [r for _, r in resumos if r.calculo.status == calc.NOVO_NORMAL]
    direto = _soma([r.calculo.valor_mensal for _, r in em_saving if r.modo_calculo == calc.DIRETO_REAIS])
    horas_valor = _soma([r.calculo.valor_mensal for _, r in em_saving if r.modo_calculo == calc.POR_TEMPO])
    horas_liberadas = _soma([r.calculo.horas_mes for _, r in em_saving])
    no_escopo = [r for i, r in resumos if i.mes_inicio <= ate]
    invest_total = _soma([r.calculo.investimento_total for r in no_escopo])
    saving_janela_total = _soma([r.calculo.saving_janela for r in no_escopo])
    roi = (saving_janela_total - invest_total) / invest_total * 100 if invest_total != 0 else None
    contagem = {s: 0 for s in calc.STATUS}
    for _, r in resumos:
        contagem[r.calculo.status] += 1

    saving_periodo: dict[UUID, Decimal] = {}
    for ini, r in resumos:
        saving_periodo[ini.id] = _soma(
            [
                calc.saving_no_mes(r.calculo.valor_mensal, r.mes_inicio, r.janela_meses, r.mes_encerramento, m)
                for m in meses
            ]
        )

    por_tipo = [
        {
            "tipo": tipo,
            "quantidade": sum(1 for i, _ in resumos if i.tipo == tipo),
            "saving_periodo": calc.q2(_soma([saving_periodo[i.id] for i, _ in resumos if i.tipo == tipo])),
        }
        for tipo in TIPOS
    ]

    fontes_view = []
    for fonte in fontes:
        lancadas = por_fonte.get(fonte.id, [])
        if not fonte.ativo and not lancadas:
            continue
        orc, real = _orcado_realizado(lancadas)
        pontos = []
        for m in meses:
            fm = por_fonte_mes.get((fonte.id, m))
            pontos.append(
                {
                    "competencia": m,
                    "orcado": None if fm is None else _q2n(fm.valor_orcado),
                    "realizado": None if fm is None else calc.q2(fm.valor_realizado),
                    "variacao": None if fm is None else _q2n(calc.variacao(fm.valor_orcado, fm.valor_realizado)),
                    "metrica_valor": None if fm is None else _q2n(fm.metrica_valor),
                    "custo_unitario": None
                    if fm is None
                    else _q4(calc.custo_unitario(fm.valor_realizado, fm.metrica_valor)),
                }
            )
        fontes_view.append(
            {
                "id": fonte.id,
                "nome": fonte.nome,
                "metrica_nome": fonte.metrica_nome,
                "orcado_periodo": _q2n(orc),
                "realizado_periodo": calc.q2(real if real is not None else ZERO),
                "variacao_periodo": _q2n(calc.variacao(orc, real)),
                "saving_iniciativas_mensal": calc.q2(
                    _soma([r.calculo.valor_mensal for i, r in em_saving if i.fonte_id == fonte.id])
                ),
                "serie": pontos,
            }
        )

    ini_view: list[dict[str, Any]] = [
        {
            "id": i.id,
            "titulo": i.titulo,
            "tipo": i.tipo,
            "modo_calculo": i.modo_calculo,
            "status": r.calculo.status,
            "valor_mensal": calc.q2(r.calculo.valor_mensal),
            "horas_mes": calc.q2(r.calculo.horas_mes),
            "saving_periodo": calc.q2(saving_periodo[i.id]),
            "saving_janela": calc.q2(r.calculo.saving_janela),
            "investimento_total": calc.q2(r.calculo.investimento_total),
            "roi_janela_pct": None if r.calculo.roi_janela_pct is None else calc.q1(r.calculo.roi_janela_pct),
            "payback_meses": r.calculo.payback_meses,
            "se_paga_na_janela": r.calculo.se_paga_na_janela,
            "mes_inicio": i.mes_inicio,
            "fim_janela": r.calculo.fim_janela,
        }
        for i, r in resumos
    ]
    ini_view.sort(key=lambda v: v["titulo"])
    ini_view.sort(key=lambda v: v["saving_periodo"], reverse=True)

    return {
        "de": de,
        "ate": ate,
        "referencia": ref,
        "janela_padrao": calc.JANELA_PADRAO,
        "horas_fte_mes": int(calc.HORAS_FTE_MES),
        "kpis": {
            "saving_realizado": calc.q2(saving_realizado),
            "saving_projetado": calc.q2(saving_projetado),
            "saving_mensal_em_curso": calc.q2(direto + horas_valor),
            "saving_direto_em_curso": calc.q2(direto),
            "saving_horas_em_curso": calc.q2(horas_valor),
            "horas_mes_liberadas": calc.q2(horas_liberadas),
            "fte_liberado": calc.q2(horas_liberadas / calc.HORAS_FTE_MES),
            "novo_normal_mensal": calc.q2(_soma([r.calculo.valor_mensal for r in novo_normal])),
            "investimento_total": calc.q2(invest_total),
            "saving_janela_total": calc.q2(saving_janela_total),
            "roi_pct": None if roi is None else calc.q1(roi),
            "iniciativas_por_status": contagem,
        },
        "serie": serie_view,
        "por_tipo": por_tipo,
        "fontes": fontes_view,
        "iniciativas": ini_view,
    }

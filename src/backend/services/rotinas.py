# ruff: noqa: E501  (textos descritivos das rotinas padrão)
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.backend.core.exceptions import ConflictError, NotFoundError
from src.backend.models.capacidade import Semana
from src.backend.models.rotinas import Rotina, RotinaExecucao
from src.backend.repositories import rotinas as repo
from src.backend.schemas.rotinas import ExecucaoUpdate, ResetSemana, RotinaCreate, RotinaUpdate
from src.backend.services.rotinas_agenda import (
    CONCLUIDA,
    PENDENTE,
    ExecucaoAgenda,
    Ocorrencia,
    RotinaAgenda,
    SemanaAgenda,
    expandir_semana,
    resumo_esforco,
)
from src.backend.tenancy.context import TenantContext

# Rotinas de exemplo do MVP: sem link, sem bloco e esforço 0. Chave de idempotência: (título, dia, período).
_G = "Engenharia de Dados"
_S = "Squad Engenharia"
ROTINAS_PADRAO: tuple[dict[str, Any], ...] = (
    {
        "titulo": "Reunião de Triagem + Limpeza de Topdesk.",
        "dia_semana": "Segunda",
        "periodo": "Manhã",
        "categoria": "RUN",
        "responsavel": _S,
        "descricao": "Reunião semanal de triagem de incidentes, alinhamento de prioridades e limpeza da fila N2 no Topdesk.",
        "tipo_agendamento": "SEMANAL",
    },
    {
        "titulo": "Foco em Projetos / Inovação (Jira).",
        "dia_semana": "Segunda",
        "periodo": "Tarde",
        "categoria": "BUILD",
        "responsavel": _G,
        "descricao": "Desenvolvimento focado nas histórias da sprint, esteiras ETL e arquitetura de dados no Jira.",
        "tipo_agendamento": "SEMANAL",
    },
    {
        "titulo": "Desenvolvimento (Libs) / Projetos.",
        "dia_semana": "Terça",
        "periodo": "Manhã",
        "categoria": "BUILD",
        "responsavel": _G,
        "descricao": "Evolução e manutenção das bibliotecas internas, utilitários comuns e repositórios core.",
        "tipo_agendamento": "SEMANAL",
    },
    {
        "titulo": "Foco total (Deep Work).",
        "dia_semana": "Terça",
        "periodo": "Tarde",
        "categoria": "BUILD",
        "responsavel": _G,
        "descricao": "Período protegido de imersão técnica sem reuniões para modelagem complexa e desenvolvimento crítico.",
        "tipo_agendamento": "SEMANAL",
    },
    {
        "titulo": "Redução de Toil (Automatizar bugs repetitivos).",
        "dia_semana": "Quarta",
        "periodo": "Manhã",
        "categoria": "RUN",
        "responsavel": _S,
        "descricao": "Engenharia de Confiabilidade (SRE): identificação de causas raízes e automação de scripts para eliminar toil operacional.",
        "tipo_agendamento": "SEMANAL",
    },
    {
        "titulo": "Foco em Projetos / Inovação (Jira).",
        "dia_semana": "Quarta",
        "periodo": "Tarde",
        "categoria": "BUILD",
        "responsavel": _G,
        "descricao": "Continuidade de entregáveis prioritários da sprint e revisões técnicas em pares (Code Review).",
        "tipo_agendamento": "SEMANAL",
    },
    {
        "titulo": "Desenvolvimento (Libs) / Projetos.",
        "dia_semana": "Quinta",
        "periodo": "Manhã",
        "categoria": "BUILD",
        "responsavel": _G,
        "descricao": "Implementação de novas funcionalidades, testes automatizados e esteiras CI/CD.",
        "tipo_agendamento": "SEMANAL",
    },
    {
        "titulo": "Foco total (Deep Work).",
        "dia_semana": "Quinta",
        "periodo": "Tarde",
        "categoria": "BUILD",
        "responsavel": _G,
        "descricao": "Sessão de Deep Work dedicada para otimização de consultas SQL, tuning de pipelines e escalabilidade.",
        "tipo_agendamento": "SEMANAL",
    },
    {
        "titulo": "Entregas da Sprint (Jira).",
        "dia_semana": "Sexta",
        "periodo": "Manhã",
        "categoria": "BUILD",
        "responsavel": _G,
        "descricao": "Testes integrados finais, validações com stakeholders e fechamento de itens comprometidos no Jira.",
        "tipo_agendamento": "SEMANAL",
    },
    {
        "titulo": "FinOps, Revisão de Nuvem e Fechamento.",
        "dia_semana": "Sexta",
        "periodo": "Tarde",
        "categoria": "RUN",
        "responsavel": "Tech Lead / Squad",
        "descricao": "Auditoria semanal de custos em nuvem (AWS/GCP/Azure), desligamento de recursos ociosos e alinhamento do ciclo.",
        "tipo_agendamento": "SEMANAL",
    },
    {
        "titulo": "Consolidação Mensal de Indicadores e Metas",
        "dia_semana": None,
        "periodo": "Manhã",
        "categoria": "RUN",
        "responsavel": _S,
        "descricao": "Extração e consolidação dos indicadores de capacidade, fechamento de volumetria e alinhamento com a diretoria.",
        "tipo_agendamento": "MENSAL_DIA_FIXO",
        "dia_mes": 1,
    },
    {
        "titulo": "Revisão de Metas e Alinhamento de Meio de Ciclo",
        "dia_semana": None,
        "periodo": "Tarde",
        "categoria": "BUILD",
        "responsavel": "Tech Lead / Squad",
        "descricao": "Reunião de meio de mês (dia 15) para checar o avanço dos projetos e replanejar eventuais desvios de capacidade.",
        "tipo_agendamento": "MENSAL_DIA_FIXO",
        "dia_mes": 15,
    },
    {
        "titulo": "Fechamento Cloud / FinOps e Apuração de Custos",
        "dia_semana": None,
        "periodo": "Tarde",
        "categoria": "RUN",
        "responsavel": "FinOps / DevOps",
        "descricao": "Auditoria completa de faturas cloud do mês (AWS/Azure), encerramento contábil e eliminação de recursos órfãos.",
        "tipo_agendamento": "MENSAL_ULTIMO_UTIL",
    },
)

SITUACOES_PENDENTES = ("VENCE_HOJE", "ATRASADA")


# --- helpers ----------------------------------------------------------------------------------------------------


def _persistir(db: Session, mensagem: str) -> None:
    """Flush dentro de savepoint: conflito vira 409 sem invalidar a transação externa."""
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError as exc:
        raise ConflictError(mensagem) from exc


def _rotina_ou_404(db: Session, ctx: TenantContext, rotina_id: UUID) -> Rotina:
    rotina = repo.obter_rotina(db, ctx.tenant_id, rotina_id)
    if rotina is None:
        raise NotFoundError("Rotina não encontrada")
    return rotina


def _semana_ou_404(db: Session, ctx: TenantContext, semana_id: UUID) -> Semana:
    semana = repo.obter_semana(db, ctx.tenant_id, semana_id)
    if semana is None:
        raise NotFoundError("Semana não encontrada")
    return semana


def _agenda_rotina(r: Rotina) -> RotinaAgenda:
    return RotinaAgenda(
        id=r.id,
        categoria=r.categoria,
        tipo_agendamento=r.tipo_agendamento,
        dia_semana=r.dia_semana,
        dia_mes=r.dia_mes,
        inicio_vigencia=r.inicio_vigencia,
        ativo=r.ativo,
        esforco_estimado_min=r.esforco_estimado_min,
    )


def _agenda_semana(s: Semana) -> SemanaAgenda:
    return SemanaAgenda(id=s.id, data_inicio=s.data_inicio, data_fim=s.data_fim, criada_em=s.created_at.date())


def _agenda_execucao(e: RotinaExecucao) -> ExecucaoAgenda:
    return ExecucaoAgenda(
        rotina_id=e.rotina_id,
        semana_id=e.semana_id,
        ocorrencia=e.ocorrencia,
        status=e.status,
        esforco_real_min=e.esforco_real_min,
    )


def _view_ocorrencia(oc: Ocorrencia, rotina: Rotina, semana: Semana, exe: RotinaExecucao | None) -> dict[str, Any]:
    return {
        "rotina_id": oc.rotina_id,
        "semana_id": oc.semana_id,
        "semana_identificacao": semana.identificacao,
        "ocorrencia": oc.ocorrencia,
        "data_prevista": oc.data_prevista,
        "status": oc.status,
        "situacao": oc.situacao,
        "titulo": rotina.titulo,
        "descricao": rotina.descricao,
        "categoria": rotina.categoria,
        "responsavel": rotina.responsavel,
        "link_recurso": rotina.link_recurso,
        "tipo_agendamento": rotina.tipo_agendamento,
        "dia_semana": rotina.dia_semana,
        "periodo": rotina.periodo,
        "dia_mes": rotina.dia_mes,
        "esforco_estimado_min": oc.esforco_estimado_min,
        "esforco_real_min": oc.esforco_real_min,
        "concluido_em": exe.concluido_em if exe is not None else None,
        "concluido_por": exe.concluido_por if exe is not None else None,
        "observacao": exe.observacao if exe is not None else None,
    }


def _ocorrencias_semana(
    rotinas: Sequence[Rotina], semana: Semana, execucoes: Iterable[RotinaExecucao], hoje: date
) -> list[tuple[Ocorrencia, Rotina, RotinaExecucao | None]]:
    """Expande uma semana e associa cada ocorrência à rotina e à execução de origem."""
    execs = list(execucoes)
    por_rotina = {r.id: r for r in rotinas}
    por_chave = {(e.rotina_id, e.ocorrencia): e for e in execs}
    ocs = expandir_semana(
        [_agenda_rotina(r) for r in rotinas], _agenda_semana(semana), [_agenda_execucao(e) for e in execs], hoje
    )
    return [(oc, por_rotina[oc.rotina_id], por_chave.get((oc.rotina_id, oc.ocorrencia))) for oc in ocs]


def _agrupar_execucoes(execs: Iterable[RotinaExecucao]) -> dict[UUID, list[RotinaExecucao]]:
    resultado: dict[UUID, list[RotinaExecucao]] = {}
    for e in execs:
        resultado.setdefault(e.semana_id, []).append(e)
    return resultado


def _regras_agendamento(dados: dict[str, Any]) -> None:
    """Valida e normaliza com o estado resultante (422)."""
    tipo = dados["tipo_agendamento"]
    if tipo == "SEMANAL" and not dados.get("dia_semana"):
        raise HTTPException(422, "dia_semana é obrigatório para rotinas semanais")
    if tipo == "MENSAL_DIA_FIXO" and dados.get("dia_mes") is None:
        raise HTTPException(422, "dia_mes é obrigatório para rotinas mensais em dia fixo")
    if tipo != "SEMANAL":
        dados["dia_semana"] = None
    if tipo != "MENSAL_DIA_FIXO":
        dados["dia_mes"] = None


# --- rotinas ----------------------------------------------------------------------------------------------------


def listar_rotinas(db: Session, ctx: TenantContext, ativo: bool | None = None) -> Sequence[Rotina]:
    return repo.listar_rotinas(db, ctx.tenant_id, ativo=ativo)


def obter_rotina(db: Session, ctx: TenantContext, rotina_id: UUID) -> Rotina:
    return _rotina_ou_404(db, ctx, rotina_id)


def criar_rotina(db: Session, ctx: TenantContext, dados: RotinaCreate) -> Rotina:
    campos = dados.model_dump()
    if campos["inicio_vigencia"] is None:
        campos["inicio_vigencia"] = date.today()
    _regras_agendamento(campos)
    rotina = Rotina(tenant_id=ctx.tenant_id, created_by=ctx.sub, **campos)
    db.add(rotina)
    _persistir(db, "Conflito ao criar rotina")
    db.refresh(rotina)
    return rotina


def atualizar_rotina(db: Session, ctx: TenantContext, rotina_id: UUID, dados: RotinaUpdate) -> Rotina:
    rotina = _rotina_ou_404(db, ctx, rotina_id)
    enviados = dados.model_dump(exclude_unset=True)
    nulaveis = ("descricao", "responsavel", "link_recurso", "dia_semana", "dia_mes")
    obrigatorios = (
        "titulo",
        "categoria",
        "tipo_agendamento",
        "periodo",
        "esforco_estimado_min",
        "ordem",
        "ativo",
        "inicio_vigencia",
    )
    estado = {nome: getattr(rotina, nome) for nome in (*nulaveis, *obrigatorios)}
    for nome in nulaveis:
        if nome in enviados:
            estado[nome] = enviados[nome]
    for nome in obrigatorios:
        if enviados.get(nome) is not None:
            estado[nome] = enviados[nome]
    _regras_agendamento(estado)
    for nome, valor in estado.items():
        setattr(rotina, nome, valor)
    _persistir(db, "Conflito ao atualizar rotina")
    db.refresh(rotina)
    return rotina


def remover_rotina(db: Session, ctx: TenantContext, rotina_id: UUID) -> None:
    db.delete(_rotina_ou_404(db, ctx, rotina_id))
    db.flush()


def criar_rotinas_padrao(db: Session, ctx: TenantContext) -> dict[str, int]:
    existentes = repo.listar_rotinas(db, ctx.tenant_id)
    chaves = {(r.titulo, r.dia_semana, r.periodo) for r in existentes}
    proxima_ordem = max((r.ordem for r in existentes), default=0)
    hoje = date.today()
    criadas = 0
    for padrao in ROTINAS_PADRAO:
        chave = (padrao["titulo"], padrao["dia_semana"], padrao["periodo"])
        if chave in chaves:
            continue
        criadas += 1
        db.add(
            Rotina(
                tenant_id=ctx.tenant_id,
                created_by=ctx.sub,
                esforco_estimado_min=0,
                ordem=proxima_ordem + criadas,
                ativo=True,
                inicio_vigencia=hoje,
                **padrao,
            )
        )
        chaves.add(chave)
    _persistir(db, "Conflito ao criar rotinas padrão")
    return {"created": criadas, "skipped": len(ROTINAS_PADRAO) - criadas}


# --- semana / execução ------------------------------------------------------------------------------------------


def ocorrencias_da_semana(
    db: Session, ctx: TenantContext, semana: Semana, hoje: date
) -> list[tuple[Ocorrencia, Rotina, RotinaExecucao | None]]:
    rotinas = repo.listar_rotinas(db, ctx.tenant_id)
    execucoes = repo.listar_execucoes(db, ctx.tenant_id, semana_id=semana.id)
    return _ocorrencias_semana(rotinas, semana, execucoes, hoje)


def visao_semana(
    db: Session,
    ctx: TenantContext,
    semana_id: UUID,
    hoje: date | None = None,
    categoria: str | None = None,
    status: str | None = None,
    tipo_agendamento: str | None = None,
) -> dict[str, Any]:
    hoje = hoje or date.today()
    semana = _semana_ou_404(db, ctx, semana_id)
    itens = ocorrencias_da_semana(db, ctx, semana, hoje)
    if categoria is not None:
        itens = [i for i in itens if i[0].categoria == categoria]
    if status is not None:
        itens = [i for i in itens if i[0].status == status]
    if tipo_agendamento is not None:
        itens = [i for i in itens if i[1].tipo_agendamento == tipo_agendamento]
    return {
        "semana_id": semana.id,
        "semana_identificacao": semana.identificacao,
        "hoje": hoje,
        "ocorrencias": [_view_ocorrencia(oc, r, semana, e) for oc, r, e in itens],
        "resumo": resumo_esforco(oc for oc, _r, _e in itens),
    }


def salvar_execucao(db: Session, ctx: TenantContext, rotina_id: UUID, dados: ExecucaoUpdate) -> dict[str, Any]:
    rotina = _rotina_ou_404(db, ctx, rotina_id)
    semana = _semana_ou_404(db, ctx, dados.semana_id)
    hoje = date.today()
    existente = repo.obter_execucao(db, ctx.tenant_id, rotina.id, semana.id, dados.ocorrencia)
    execs = [existente] if existente is not None else []
    validas = {oc.ocorrencia for oc, _r, _e in _ocorrencias_semana([rotina], semana, execs, hoje)}
    if dados.ocorrencia not in validas:
        raise HTTPException(422, "Ocorrência inválida para esta rotina nesta semana")
    exe = existente
    if exe is None:
        exe = RotinaExecucao(
            tenant_id=ctx.tenant_id,
            created_by=ctx.sub,
            rotina_id=rotina.id,
            semana_id=semana.id,
            ocorrencia=dados.ocorrencia,
        )
        db.add(exe)
    exe.status = dados.status
    if dados.status == CONCLUIDA:
        exe.concluido_em = datetime.now(UTC)
        exe.concluido_por = ctx.sub
        exe.esforco_real_min = dados.esforco_real_min
    else:
        exe.concluido_em = None
        exe.concluido_por = None
        exe.esforco_real_min = None
    if "observacao" in dados.model_fields_set:
        exe.observacao = dados.observacao
    _persistir(db, "Conflito ao salvar execução")
    db.refresh(exe)
    for oc, r, e in _ocorrencias_semana([rotina], semana, [exe], hoje):
        if oc.ocorrencia == dados.ocorrencia:
            return _view_ocorrencia(oc, r, semana, e)
    raise HTTPException(422, "Ocorrência inválida para esta rotina nesta semana")


def resetar_semana(db: Session, ctx: TenantContext, dados: ResetSemana) -> dict[str, int]:
    semana = _semana_ou_404(db, ctx, dados.semana_id)
    contagem = 0
    for exe in repo.listar_execucoes(db, ctx.tenant_id, semana_id=semana.id):
        if exe.status == CONCLUIDA:
            contagem += 1
        exe.status = PENDENTE
        exe.concluido_em = None
        exe.concluido_por = None
        exe.esforco_real_min = None
    db.flush()
    return {"reset_count": contagem}


def pendencias(db: Session, ctx: TenantContext, hoje: date | None = None) -> dict[str, Any]:
    hoje = hoje or date.today()
    rotinas = repo.listar_rotinas(db, ctx.tenant_id)
    por_semana = _agrupar_execucoes(repo.listar_execucoes(db, ctx.tenant_id))
    vence_hoje: list[tuple[Ocorrencia, dict[str, Any]]] = []
    atrasadas: list[tuple[Ocorrencia, dict[str, Any]]] = []
    for semana in repo.listar_semanas(db, ctx.tenant_id):
        if semana.data_inicio is None or semana.data_fim is None or semana.data_inicio > hoje:
            continue
        for oc, r, e in _ocorrencias_semana(rotinas, semana, por_semana.get(semana.id, []), hoje):
            if oc.status != PENDENTE or oc.situacao not in SITUACOES_PENDENTES:
                continue
            destino = vence_hoje if oc.situacao == "VENCE_HOJE" else atrasadas
            destino.append((oc, _view_ocorrencia(oc, r, semana, e)))
    vence_hoje.sort(key=lambda p: (p[1]["titulo"], p[1]["semana_identificacao"]))
    atrasadas.sort(key=lambda p: (p[0].data_prevista or hoje, p[1]["titulo"], p[1]["semana_identificacao"]))
    return {"hoje": hoje, "vence_hoje": [v for _o, v in vence_hoje], "atrasadas": [v for _o, v in atrasadas]}


# --- integração com o painel da Capacidade ----------------------------------------------------------------------


def resumo_para_painel(
    db: Session, ctx: TenantContext, semana: Semana | None, hoje: date | None = None
) -> dict[str, dict[str, int]]:
    """Resumo de esforço da semana informada ou, sem semana, da soma de todas as semanas do tenant."""
    hoje = hoje or date.today()
    rotinas = repo.listar_rotinas(db, ctx.tenant_id)
    if semana is not None:
        semanas: Sequence[Semana] = [semana]
        execs = repo.listar_execucoes(db, ctx.tenant_id, semana_id=semana.id)
    else:
        semanas = repo.listar_semanas(db, ctx.tenant_id)
        execs = repo.listar_execucoes(db, ctx.tenant_id)
    por_semana = _agrupar_execucoes(execs)
    ocorrencias: list[Ocorrencia] = []
    for s in semanas:
        ocorrencias.extend(oc for oc, _r, _e in _ocorrencias_semana(rotinas, s, por_semana.get(s.id, []), hoje))
    return resumo_esforco(ocorrencias)

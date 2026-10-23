"""Agenda de Rotinas: cálculo puro de ocorrências, datas previstas, situação e esforço.

Sem I/O, sem SQLAlchemy e sem FastAPI. Dias úteis são segunda a sexta e ignoram feriados.
"""

import calendar
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

DIAS_SEMANA: tuple[str, ...] = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")
DIAS_UTEIS: tuple[str, ...] = DIAS_SEMANA[:5]
OCORRENCIA_SEMANA = "SEMANA"
TIPOS_AGENDAMENTO: tuple[str, ...] = (
    "SEMANAL",
    "DIARIA",
    "QUINZENAL",
    "MENSAL_DIA_FIXO",
    "MENSAL_PRIMEIRO_UTIL",
    "MENSAL_ULTIMO_UTIL",
)
ALIASES_TIPO: dict[str, str] = {
    "MENSAL": "MENSAL_DIA_FIXO",
    "PRIMEIRO_UTIL": "MENSAL_PRIMEIRO_UTIL",
    "1_UTIL": "MENSAL_PRIMEIRO_UTIL",
    "ULTIMO_UTIL": "MENSAL_ULTIMO_UTIL",
    "MENSAL_ULTIMO_DIA": "MENSAL_ULTIMO_UTIL",
    "ULTIMO_DIA": "MENSAL_ULTIMO_UTIL",
}

CONCLUIDA = "CONCLUIDA"
PENDENTE = "PENDENTE"
CATEGORIAS = ("BUILD", "RUN")


def normalizar_tipo(valor: str) -> str:
    """Normaliza o tipo de agendamento (upper/strip + aliases); ValueError se inválido."""
    chave = (valor or "").strip().upper()
    chave = ALIASES_TIPO.get(chave, chave)
    if chave not in TIPOS_AGENDAMENTO:
        raise ValueError(f"tipo_agendamento inválido: {valor!r}")
    return chave


@dataclass(frozen=True)
class RotinaAgenda:
    id: UUID
    categoria: str
    tipo_agendamento: str
    dia_semana: str | None
    dia_mes: int | None
    inicio_vigencia: date
    ativo: bool
    esforco_estimado_min: int


@dataclass(frozen=True)
class SemanaAgenda:
    id: UUID
    data_inicio: date | None
    data_fim: date | None
    criada_em: date


@dataclass(frozen=True)
class ExecucaoAgenda:
    rotina_id: UUID
    semana_id: UUID
    ocorrencia: str
    status: str
    esforco_real_min: int | None


@dataclass(frozen=True)
class Ocorrencia:
    rotina_id: UUID
    semana_id: UUID
    ocorrencia: str
    data_prevista: date | None
    categoria: str
    status: str
    situacao: str
    esforco_estimado_min: int
    esforco_real_min: int | None


def primeiro_dia_util(ano: int, mes: int) -> date:
    d = date(ano, mes, 1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def ultimo_dia_util(ano: int, mes: int) -> date:
    d = date(ano, mes, calendar.monthrange(ano, mes)[1])
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _meses(inicio: date, fim: date) -> list[tuple[int, int]]:
    meses: list[tuple[int, int]] = []
    ano, mes = inicio.year, inicio.month
    while (ano, mes) <= (fim.year, fim.month):
        meses.append((ano, mes))
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    return meses


def vigente_na_semana(rotina: RotinaAgenda, semana: SemanaAgenda) -> bool:
    referencia = semana.data_fim or semana.data_inicio or semana.criada_em
    return rotina.inicio_vigencia <= referencia


def _primeira_no_intervalo(candidatas: Iterable[date], inicio: date, fim: date) -> list[tuple[str, date | None]]:
    for d in candidatas:
        if inicio <= d <= fim:
            return [(OCORRENCIA_SEMANA, d)]
    return []


def datas_previstas(rotina: RotinaAgenda, semana: SemanaAgenda) -> list[tuple[str, date | None]]:
    """Pares (ocorrencia, data). Lista vazia = a rotina não ocorre nesta semana."""
    tipo = rotina.tipo_agendamento
    inicio, fim = semana.data_inicio, semana.data_fim
    if inicio is None or fim is None:
        if tipo == "DIARIA":
            return [(dia, None) for dia in DIAS_UTEIS]
        return [(OCORRENCIA_SEMANA, None)]

    if tipo == "SEMANAL":
        if rotina.dia_semana is None:
            return []
        d = inicio
        while d <= fim:
            if DIAS_SEMANA[d.weekday()] == rotina.dia_semana:
                return [(OCORRENCIA_SEMANA, d)]
            d += timedelta(days=1)
        return []

    if tipo == "DIARIA":
        resultado: list[tuple[str, date | None]] = []
        encontrados: dict[str, date] = {}
        d = inicio
        while d <= fim:
            nome = DIAS_SEMANA[d.weekday()]
            if nome in DIAS_UTEIS and nome not in encontrados:
                encontrados[nome] = d
            d += timedelta(days=1)
        for dia in DIAS_UTEIS:
            if dia in encontrados:
                resultado.append((dia, encontrados[dia]))
        return resultado

    meses = _meses(inicio, fim)
    if tipo == "MENSAL_DIA_FIXO":
        alvo = rotina.dia_mes or 1
        return _primeira_no_intervalo(
            (date(a, m, min(alvo, calendar.monthrange(a, m)[1])) for a, m in meses), inicio, fim
        )
    if tipo == "MENSAL_PRIMEIRO_UTIL":
        return _primeira_no_intervalo((primeiro_dia_util(a, m) for a, m in meses), inicio, fim)
    if tipo == "MENSAL_ULTIMO_UTIL":
        return _primeira_no_intervalo((ultimo_dia_util(a, m) for a, m in meses), inicio, fim)
    if tipo == "QUINZENAL":
        return _primeira_no_intervalo((date(a, m, dia) for a, m in meses for dia in (1, 15)), inicio, fim)
    return []


def situacao(status: str, data_prevista: date | None, hoje: date) -> str:
    if status == CONCLUIDA:
        return "CONCLUIDA"
    if data_prevista is None:
        return "SEM_DATA"
    if data_prevista == hoje:
        return "VENCE_HOJE"
    if data_prevista < hoje:
        return "ATRASADA"
    return "PREVISTA"


def expandir_semana(
    rotinas: Iterable[RotinaAgenda],
    semana: SemanaAgenda,
    execucoes: Iterable[ExecucaoAgenda],
    hoje: date,
) -> list[Ocorrencia]:
    da_semana = {(e.rotina_id, e.ocorrencia): e for e in execucoes if e.semana_id == semana.id}
    com_execucao = {rotina_id for rotina_id, _ in da_semana}
    resultado: list[Ocorrencia] = []
    for rotina in rotinas:
        if not vigente_na_semana(rotina, semana):
            continue
        if not rotina.ativo and rotina.id not in com_execucao:
            continue
        for ocorrencia, data in datas_previstas(rotina, semana):
            execucao = da_semana.get((rotina.id, ocorrencia))
            status = execucao.status if execucao else PENDENTE
            resultado.append(
                Ocorrencia(
                    rotina_id=rotina.id,
                    semana_id=semana.id,
                    ocorrencia=ocorrencia,
                    data_prevista=data,
                    categoria=rotina.categoria,
                    status=status,
                    situacao=situacao(status, data, hoje),
                    esforco_estimado_min=rotina.esforco_estimado_min,
                    esforco_real_min=execucao.esforco_real_min if execucao else None,
                )
            )
    return resultado


def _vazio() -> dict[str, int]:
    return {"ocorrencias": 0, "concluidas": 0, "pendentes": 0, "minutos_previstos": 0, "minutos_executados": 0}


def resumo_esforco(ocorrencias: Iterable[Ocorrencia]) -> dict[str, dict[str, int]]:
    resumo = {"BUILD": _vazio(), "RUN": _vazio(), "TOTAL": _vazio()}
    for o in ocorrencias:
        concluida = o.status == CONCLUIDA
        executado = 0
        if concluida:
            executado = o.esforco_real_min if o.esforco_real_min is not None else o.esforco_estimado_min
        alvos = [resumo["TOTAL"]]
        if o.categoria in resumo:
            alvos.append(resumo[o.categoria])
        for r in alvos:
            r["ocorrencias"] += 1
            r["concluidas" if concluida else "pendentes"] += 1
            r["minutos_previstos"] += o.esforco_estimado_min
            r["minutos_executados"] += executado
    return resumo

"""Regras puras de FinOps (sem banco): janela de saving, status, ROI, payback e série mensal.

Dinheiro e horas usam Decimal; o arredondamento (2 casas, ROUND_HALF_UP) só acontece na saída.
Competência é sempre um `date` no dia 1.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

HORAS_FTE_MES = Decimal(168)
JANELA_PADRAO = 6
MULTIPLICADORES: dict[str, Decimal] = {
    "DIARIA_UTIL": Decimal(22),
    "DIARIA_CORRIDA": Decimal(30),
    "SEMANAL": Decimal("4.33"),
    "QUINZENAL": Decimal(2),
    "MENSAL": Decimal(1),
}
DIRETO_REAIS = "DIRETO_REAIS"
POR_TEMPO = "POR_TEMPO"
PLANEJADA, EM_SAVING, NOVO_NORMAL, ENCERRADA = "PLANEJADA", "EM_SAVING", "NOVO_NORMAL", "ENCERRADA"
STATUS = (PLANEJADA, EM_SAVING, NOVO_NORMAL, ENCERRADA)

_COMPETENCIA_RE = re.compile(r"^(\d{4})-(\d{2})$")
ZERO = Decimal(0)
CEM = Decimal(100)


# --- competências -------------------------------------------------------------------------------------------------


def parse_competencia(texto: str) -> date:
    """'YYYY-MM' -> date no dia 1. Levanta ValueError se inválida."""
    casou = _COMPETENCIA_RE.match(texto.strip()) if isinstance(texto, str) else None
    if not casou:
        raise ValueError("competência deve estar no formato YYYY-MM")
    ano, mes = int(casou.group(1)), int(casou.group(2))
    if not 1 <= mes <= 12 or ano < 1:
        raise ValueError("competência deve estar no formato YYYY-MM")
    return date(ano, mes, 1)


def fmt_competencia(valor: date) -> str:
    return f"{valor.year:04d}-{valor.month:02d}"


def primeiro_dia(valor: date) -> date:
    return valor.replace(day=1)


def mes_add(mes: date, n: int) -> date:
    indice = mes.year * 12 + (mes.month - 1) + n
    return date(indice // 12, indice % 12 + 1, 1)


def meses_entre(inicio: date, fim: date) -> int:
    """Diferença em meses (fim - inicio); negativa se fim < inicio."""
    return (fim.year - inicio.year) * 12 + (fim.month - inicio.month)


def intervalo_meses(de: date, ate: date) -> list[date]:
    return [mes_add(de, i) for i in range(meses_entre(de, ate) + 1)]


# --- arredondamento -----------------------------------------------------------------------------------------------


def q2(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def q1(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def q4(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


# --- entradas e saídas --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ParticipanteEntrada:
    custo_hora: Decimal
    qtd_pessoas: int
    horas_antes: Decimal
    horas_depois: Decimal


@dataclass(frozen=True)
class IniciativaEntrada:
    modo_calculo: str
    mes_inicio: date
    janela_meses: int = JANELA_PADRAO
    mes_encerramento: date | None = None
    valor_mensal: Decimal | None = None
    frequencia: str | None = None
    participantes: Sequence[ParticipanteEntrada] = ()
    investimento_reais: Decimal = ZERO
    investimento_horas: Decimal = ZERO
    investimento_custo_hora: Decimal = ZERO


@dataclass(frozen=True)
class ParticipanteCalculo:
    horas_mes: Decimal
    valor_mensal: Decimal


@dataclass(frozen=True)
class Calculo:
    """Resultado bruto (sem arredondar). Use `q2`/`q1` na saída."""

    valor_mensal: Decimal
    horas_mes: Decimal
    fte: Decimal
    perc_reducao: Decimal | None
    fim_janela: date
    meses_janela: int
    status: str
    meses_contados: int
    saving_acumulado: Decimal
    saving_janela: Decimal
    investimento_total: Decimal
    roi_janela_pct: Decimal | None
    payback_meses: int | None
    se_paga_na_janela: bool
    participantes: tuple[ParticipanteCalculo, ...]


# --- participantes e valor mensal ---------------------------------------------------------------------------------


def multiplicador(frequencia: str | None) -> Decimal:
    if frequencia is None or frequencia not in MULTIPLICADORES:
        raise ValueError("frequência inválida")
    return MULTIPLICADORES[frequencia]


def calcular_participante(p: ParticipanteEntrada, frequencia: str) -> ParticipanteCalculo:
    """delta = antes - depois pode ser negativo (ex.: executivo passa a revisar); sem clamp."""
    delta = p.horas_antes - p.horas_depois
    horas_mes = delta * p.qtd_pessoas * multiplicador(frequencia)
    return ParticipanteCalculo(horas_mes=horas_mes, valor_mensal=horas_mes * p.custo_hora)


def investimento_total(reais: Decimal, horas: Decimal, custo_hora: Decimal) -> Decimal:
    return reais + horas * custo_hora


# --- janela e status ----------------------------------------------------------------------------------------------


def fim_janela(mes_inicio: date, janela_meses: int) -> date:
    return mes_add(mes_inicio, janela_meses - 1)


def fim_efetivo(mes_inicio: date, janela_meses: int, mes_encerramento: date | None) -> date:
    fim = fim_janela(mes_inicio, janela_meses)
    if mes_encerramento is not None and mes_encerramento < fim:
        return mes_encerramento
    return fim


def meses_janela_efetivos(mes_inicio: date, janela_meses: int, mes_encerramento: date | None) -> int:
    return max(0, meses_entre(mes_inicio, fim_efetivo(mes_inicio, janela_meses, mes_encerramento)) + 1)


def meses_contados(mes_inicio: date, janela_meses: int, mes_encerramento: date | None, referencia: date) -> int:
    """Meses efetivos da janela que são <= referência."""
    if referencia < mes_inicio:
        return 0
    ultimo = min(referencia, fim_efetivo(mes_inicio, janela_meses, mes_encerramento))
    return max(0, meses_entre(mes_inicio, ultimo) + 1)


def status_em(mes_inicio: date, janela_meses: int, mes_encerramento: date | None, referencia: date) -> str:
    fim = fim_janela(mes_inicio, janela_meses)
    if referencia < mes_inicio:
        return PLANEJADA
    if mes_encerramento is not None and mes_encerramento < fim and referencia > mes_encerramento:
        return ENCERRADA
    if referencia <= fim:
        return EM_SAVING
    return NOVO_NORMAL


def saving_no_mes(
    valor_mensal: Decimal, mes_inicio: date, janela_meses: int, mes_encerramento: date | None, mes: date
) -> Decimal:
    fim = fim_efetivo(mes_inicio, janela_meses, mes_encerramento)
    return valor_mensal if mes_inicio <= mes <= fim else ZERO


# --- iniciativa ---------------------------------------------------------------------------------------------------


def calcular_iniciativa(entrada: IniciativaEntrada, referencia: date) -> Calculo:
    participantes: tuple[ParticipanteCalculo, ...] = ()
    perc: Decimal | None = None
    if entrada.modo_calculo == POR_TEMPO:
        freq = entrada.frequencia or ""
        participantes = tuple(calcular_participante(p, freq) for p in entrada.participantes)
        horas_mes = sum((p.horas_mes for p in participantes), ZERO)
        valor_mensal = sum((p.valor_mensal for p in participantes), ZERO)
        antes = sum((p.horas_antes * p.qtd_pessoas for p in entrada.participantes), ZERO)
        depois = sum((p.horas_depois * p.qtd_pessoas for p in entrada.participantes), ZERO)
        perc = (antes - depois) / antes * CEM if antes != 0 else None
    else:
        valor_mensal = entrada.valor_mensal or ZERO
        horas_mes = ZERO
    janela = meses_janela_efetivos(entrada.mes_inicio, entrada.janela_meses, entrada.mes_encerramento)
    contados = meses_contados(entrada.mes_inicio, entrada.janela_meses, entrada.mes_encerramento, referencia)
    saving_janela = valor_mensal * janela
    invest = investimento_total(entrada.investimento_reais, entrada.investimento_horas, entrada.investimento_custo_hora)
    roi = (saving_janela - invest) / invest * CEM if invest != 0 else None
    payback: int | None
    if invest == 0:
        payback = 0
    elif valor_mensal > 0:
        payback = int((invest / valor_mensal).to_integral_value(rounding=ROUND_CEILING))
    else:
        payback = None
    return Calculo(
        valor_mensal=valor_mensal,
        horas_mes=horas_mes,
        fte=horas_mes / HORAS_FTE_MES,
        perc_reducao=perc,
        fim_janela=fim_janela(entrada.mes_inicio, entrada.janela_meses),
        meses_janela=janela,
        status=status_em(entrada.mes_inicio, entrada.janela_meses, entrada.mes_encerramento, referencia),
        meses_contados=contados,
        saving_acumulado=valor_mensal * contados,
        saving_janela=saving_janela,
        investimento_total=invest,
        roi_janela_pct=roi,
        payback_meses=payback,
        se_paga_na_janela=payback is not None and payback <= janela,
        participantes=participantes,
    )


# --- agregações ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class IniciativaResumo:
    """Dados mínimos de uma iniciativa já calculada, para agregação mensal."""

    modo_calculo: str
    tipo: str
    mes_inicio: date
    janela_meses: int
    mes_encerramento: date | None
    calculo: Calculo


@dataclass(frozen=True)
class PontoSerie:
    competencia: date
    saving_direto: Decimal
    saving_horas: Decimal
    projetado: bool

    @property
    def saving_total(self) -> Decimal:
        return self.saving_direto + self.saving_horas


def serie_mensal(iniciativas: Iterable[IniciativaResumo], de: date, ate: date, referencia: date) -> list[PontoSerie]:
    itens = list(iniciativas)
    pontos = []
    for mes in intervalo_meses(de, ate):
        direto = horas = ZERO
        for it in itens:
            valor = saving_no_mes(it.calculo.valor_mensal, it.mes_inicio, it.janela_meses, it.mes_encerramento, mes)
            if it.modo_calculo == POR_TEMPO:
                horas += valor
            else:
                direto += valor
        pontos.append(PontoSerie(mes, direto, horas, mes > referencia))
    return pontos


def variacao(orcado: Decimal | None, realizado: Decimal | None) -> Decimal | None:
    """orçado - realizado; positivo = abaixo do orçado."""
    if orcado is None or realizado is None:
        return None
    return orcado - realizado


def custo_unitario(realizado: Decimal, metrica: Decimal | None) -> Decimal | None:
    if metrica is None or metrica == 0:
        return None
    return realizado / metrica

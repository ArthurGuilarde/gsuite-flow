"""Regras puras de Despesas & Contratos (sem banco): custo contratual/considerado, alertas e orçamento.

Dinheiro usa Decimal; competência é sempre um `date` no dia 1. Reaproveita os helpers de data e
arredondamento do FinOps.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from src.backend.services.finops_calculos import primeiro_dia, q1, q2

RECORRENTE_MENSAL = "RECORRENTE_MENSAL"
PONTUAL = "PONTUAL"
TIPOS_CUSTO = (RECORRENTE_MENSAL, PONTUAL)
EM_REVISAO, VALIDADO, DESPERDICIO, CANCELADO, RENEGOCIADO = (
    "EM_REVISAO",
    "VALIDADO",
    "DESPERDICIO",
    "CANCELADO",
    "RENEGOCIADO",
)
STATUS_AUDITORIA = (EM_REVISAO, VALIDADO, DESPERDICIO, CANCELADO, RENEGOCIADO)
ORIGEM_FATURA, ORIGEM_CONTRATO = "FATURA", "CONTRATO"
URGENTE, ATENCAO = "URGENTE", "ATENCAO"
DIAS_URGENTE = 30
DIAS_ATENCAO = 60
ZERO = Decimal(0)
CEM = Decimal(100)


@dataclass(frozen=True)
class DespesaEntrada:
    tipo_custo: str
    valor: Decimal
    status_auditoria: str
    valor_anterior: Decimal | None = None
    data_inicio: date | None = None
    mes_acao: date | None = None


@dataclass(frozen=True)
class CustoConsiderado:
    valor: Decimal
    origem: str
    competencia_fatura: date | None = None


def _cancelada_em(d: DespesaEntrada, mes: date) -> bool:
    if d.status_auditoria != CANCELADO:
        return False
    return d.mes_acao is None or primeiro_dia(d.mes_acao) <= mes


def _ativa_em(d: DespesaEntrada, mes: date) -> bool:
    """Recorrente, já iniciada e não cancelada no mês."""
    if d.tipo_custo != RECORRENTE_MENSAL or _cancelada_em(d, mes):
        return False
    return d.data_inicio is None or primeiro_dia(d.data_inicio) <= mes


def custo_contratual(d: DespesaEntrada, mes: date) -> Decimal:
    """Custo mensal previsto em contrato para o mês `mes` (dia 1)."""
    if not _ativa_em(d, mes):
        return ZERO
    if d.status_auditoria == RENEGOCIADO and d.mes_acao is not None and mes < primeiro_dia(d.mes_acao):
        return d.valor_anterior if d.valor_anterior is not None else d.valor
    return d.valor


def custo_considerado(
    d: DespesaEntrada,
    mes: date,
    faturas: Mapping[date, Decimal] | None = None,
    *,
    ultima_anterior: bool = False,
) -> CustoConsiderado:
    """Custo mensal considerado: realizado da fatura da fonte quando existe, senão o contratual.

    `faturas` mapeia competência -> valor_realizado da fonte ligada (None sem fonte). Só despesas
    recorrentes usam fatura. Com `ultima_anterior` (mês de referência), na falta de fatura do mês usa
    a última anterior, desde que a despesa esteja ativa no mês.
    """
    if d.tipo_custo != RECORRENTE_MENSAL:
        return CustoConsiderado(ZERO, ORIGEM_CONTRATO)
    if faturas:
        if mes in faturas:
            return CustoConsiderado(faturas[mes], ORIGEM_FATURA, mes)
        if ultima_anterior and _ativa_em(d, mes):
            anteriores = [c for c in faturas if c < mes]
            if anteriores:
                ultima = max(anteriores)
                return CustoConsiderado(faturas[ultima], ORIGEM_FATURA, ultima)
    return CustoConsiderado(custo_contratual(d, mes), ORIGEM_CONTRATO)


def pontual_no_mes(d: DespesaEntrada, mes: date) -> Decimal:
    """Valor de uma despesa pontual cuja data_inicio cai no mês (não cancelada)."""
    if d.tipo_custo != PONTUAL or d.status_auditoria == CANCELADO or d.data_inicio is None:
        return ZERO
    return d.valor if primeiro_dia(d.data_inicio) == mes else ZERO


def alerta_renovacao(status: str, data_renovacao: date | None, hoje: date) -> tuple[int, str] | None:
    """(dias, nível) se a renovação cai entre hoje e hoje+60 dias; None caso contrário."""
    if status == CANCELADO or data_renovacao is None:
        return None
    dias = (data_renovacao - hoje).days
    if dias < 0 or data_renovacao > hoje + timedelta(days=DIAS_ATENCAO):
        return None
    return dias, URGENTE if dias <= DIAS_URGENTE else ATENCAO


def auditoria_pct(statuses: Iterable[str]) -> Decimal:
    """Percentual (1 casa) de despesas já auditadas, isto é, com status diferente de EM_REVISAO."""
    lista = list(statuses)
    if not lista:
        return ZERO
    auditadas = sum(1 for s in lista if s != EM_REVISAO)
    return q1(Decimal(auditadas) / Decimal(len(lista)) * CEM)


def distribuir_anual(valor_anual: Decimal) -> list[Decimal]:
    """Divide o valor anual em 12 parcelas: 11 de round(valor/12, 2) e dezembro com o resto."""
    parcela = q2(valor_anual / 12)
    total = q2(valor_anual)
    return [parcela] * 11 + [total - parcela * 11]

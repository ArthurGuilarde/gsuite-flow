from datetime import date
from decimal import Decimal

from src.backend.services import despesas_calculos as dc

D = Decimal


def rec(valor="1000", status="VALIDADO", **extra):
    return dc.DespesaEntrada("RECORRENTE_MENSAL", D(valor), status, **extra)


def pont(valor="500", status="VALIDADO", **extra):
    return dc.DespesaEntrada("PONTUAL", D(valor), status, **extra)


def m(mes, ano=2026):
    return date(ano, mes, 1)


# --- custo contratual -----------------------------------------------------------------------------------------------


def test_contratual_recorrente_simples_e_pontual_zero():
    assert dc.custo_contratual(rec(), m(3)) == D(1000)
    assert dc.custo_contratual(pont(), m(3)) == D(0)


def test_contratual_cancelada_zera_a_partir_do_mes_da_acao():
    d = rec(status="CANCELADO", mes_acao=m(4))
    assert [dc.custo_contratual(d, m(i)) for i in (3, 4, 5)] == [D(1000), D(0), D(0)]
    # sem mes_acao a despesa cancelada nunca conta
    assert dc.custo_contratual(rec(status="CANCELADO"), m(1)) == D(0)


def test_contratual_renegociada_usa_valor_anterior_antes_da_acao():
    d = rec("700", status="RENEGOCIADO", valor_anterior=D(1000), mes_acao=m(4))
    assert [dc.custo_contratual(d, m(i)) for i in (3, 4, 5)] == [D(1000), D(700), D(700)]


def test_contratual_respeita_data_inicio_por_mes():
    d = rec(data_inicio=date(2026, 3, 20))
    assert [dc.custo_contratual(d, m(i)) for i in (2, 3, 4)] == [D(0), D(1000), D(1000)]
    renegociada = rec("700", status="RENEGOCIADO", valor_anterior=D(1000), mes_acao=m(5), data_inicio=m(3))
    assert dc.custo_contratual(renegociada, m(2)) == D(0)
    assert dc.custo_contratual(renegociada, m(3)) == D(1000)


# --- custo considerado ----------------------------------------------------------------------------------------------


def test_considerado_sem_fatura_usa_contrato():
    r = dc.custo_considerado(rec(), m(3))
    assert (r.valor, r.origem, r.competencia_fatura) == (D(1000), "CONTRATO", None)
    assert dc.custo_considerado(rec(), m(3), {}).origem == "CONTRATO"


def test_considerado_fatura_do_mes_substitui_contrato():
    r = dc.custo_considerado(rec(), m(3), {m(3): D("1234.56"), m(2): D(10)})
    assert (r.valor, r.origem, r.competencia_fatura) == (D("1234.56"), "FATURA", m(3))


def test_considerado_serie_historica_nao_usa_fatura_de_outro_mes():
    r = dc.custo_considerado(rec(), m(4), {m(3): D(900)})
    assert (r.valor, r.origem) == (D(1000), "CONTRATO")


def test_considerado_referencia_usa_ultima_fatura_anterior():
    faturas = {m(1): D(800), m(2): D(900), m(6): D(5000)}
    r = dc.custo_considerado(rec(), m(4), faturas, ultima_anterior=True)
    assert (r.valor, r.origem, r.competencia_fatura) == (D(900), "FATURA", m(2))
    # sem nenhuma fatura anterior volta ao contrato
    assert dc.custo_considerado(rec(), m(1), {m(2): D(1)}, ultima_anterior=True).origem == "CONTRATO"
    # fatura do próprio mês tem prioridade
    assert dc.custo_considerado(rec(), m(2), faturas, ultima_anterior=True).valor == D(900)


def test_considerado_nao_ressuscita_cancelada_nem_pre_inicio_pela_ultima_fatura():
    cancelada = rec(status="CANCELADO", mes_acao=m(3))
    r = dc.custo_considerado(cancelada, m(5), {m(2): D(900)}, ultima_anterior=True)
    assert (r.valor, r.origem) == (D(0), "CONTRATO")
    futura = rec(data_inicio=m(8))
    assert dc.custo_considerado(futura, m(5), {m(2): D(900)}, ultima_anterior=True).valor == D(0)


def test_considerado_pontual_ignora_fatura():
    assert dc.custo_considerado(pont(), m(3), {m(3): D(10)}).valor == D(0)


# --- pontual no mês -------------------------------------------------------------------------------------------------


def test_pontual_no_mes():
    d = pont("500", data_inicio=date(2026, 3, 31))
    assert dc.pontual_no_mes(d, m(3)) == D(500)
    assert dc.pontual_no_mes(d, m(4)) == D(0)
    assert dc.pontual_no_mes(pont(data_inicio=m(3), status="CANCELADO"), m(3)) == D(0)
    assert dc.pontual_no_mes(pont(), m(3)) == D(0)  # sem data_inicio
    assert dc.pontual_no_mes(rec(data_inicio=m(3)), m(3)) == D(0)


# --- alertas de renovação -------------------------------------------------------------------------------------------


def test_alerta_renovacao_faixas_30_e_60():
    hoje = date(2026, 1, 1)
    assert dc.alerta_renovacao("VALIDADO", date(2026, 1, 1), hoje) == (0, "URGENTE")
    assert dc.alerta_renovacao("VALIDADO", date(2026, 1, 31), hoje) == (30, "URGENTE")
    assert dc.alerta_renovacao("VALIDADO", date(2026, 2, 1), hoje) == (31, "ATENCAO")
    assert dc.alerta_renovacao("VALIDADO", date(2026, 3, 2), hoje) == (60, "ATENCAO")
    assert dc.alerta_renovacao("VALIDADO", date(2026, 3, 3), hoje) is None
    assert dc.alerta_renovacao("VALIDADO", date(2025, 12, 31), hoje) is None
    assert dc.alerta_renovacao("VALIDADO", None, hoje) is None
    assert dc.alerta_renovacao("CANCELADO", date(2026, 1, 10), hoje) is None
    assert dc.alerta_renovacao("RENEGOCIADO", date(2026, 1, 10), hoje) == (9, "URGENTE")


# --- auditoria ------------------------------------------------------------------------------------------------------


def test_auditoria_pct():
    assert dc.auditoria_pct([]) == D(0)
    assert dc.auditoria_pct(["EM_REVISAO"] * 3) == D("0.0")
    assert dc.auditoria_pct(["EM_REVISAO", "VALIDADO", "CANCELADO"]) == D("66.7")
    assert dc.auditoria_pct(["VALIDADO", "DESPERDICIO", "RENEGOCIADO"]) == D("100.0")
    assert dc.auditoria_pct(["EM_REVISAO", "VALIDADO", "VALIDADO", "VALIDADO"]) == D("75.0")


# --- orçamento anual ------------------------------------------------------------------------------------------------


def test_distribuir_anual_soma_exata():
    partes = dc.distribuir_anual(D(12000))
    assert partes == [D(1000)] * 12
    partes = dc.distribuir_anual(D(1000))
    assert len(partes) == 12 and partes[:11] == [D("83.33")] * 11 and partes[11] == D("83.37")
    for valor in ("0", "0.05", "1", "99999.99", "1234567.89"):
        partes = dc.distribuir_anual(D(valor))
        assert len(partes) == 12 and sum(partes) == D(valor) and all(p >= 0 for p in partes)

from datetime import date
from decimal import Decimal

import pytest

from src.backend.services import finops_calculos as c

D = Decimal
JAN = date(2026, 1, 1)


def m(ano, mes):
    return date(ano, mes, 1)


def direto(valor, inicio=JAN, janela=6, enc=None, **extra):
    return c.IniciativaEntrada(
        modo_calculo="DIRETO_REAIS",
        mes_inicio=inicio,
        janela_meses=janela,
        mes_encerramento=enc,
        valor_mensal=D(valor),
        **extra,
    )


def por_tempo(participantes, frequencia="DIARIA_UTIL", inicio=JAN, janela=6, **extra):
    return c.IniciativaEntrada(
        modo_calculo="POR_TEMPO",
        mes_inicio=inicio,
        janela_meses=janela,
        frequencia=frequencia,
        participantes=participantes,
        **extra,
    )


def p(custo, qtd, antes, depois):
    return c.ParticipanteEntrada(D(custo), qtd, D(antes), D(depois))


# --- competências -------------------------------------------------------------------------------------------------


def test_competencia_parse_fmt_e_mes_add():
    assert c.parse_competencia("2026-03") == m(2026, 3)
    assert c.parse_competencia(" 2026-12 ") == m(2026, 12)
    assert c.fmt_competencia(m(2026, 3)) == "2026-03"
    for ruim in ("2026-13", "2026-00", "26-01", "2026/01", "2026-1", "", "abc"):
        with pytest.raises(ValueError):
            c.parse_competencia(ruim)
    with pytest.raises(ValueError):
        c.parse_competencia(None)  # type: ignore[arg-type]
    assert c.mes_add(m(2026, 11), 3) == m(2027, 2)
    assert c.mes_add(m(2026, 1), -1) == m(2025, 12)
    assert c.mes_add(m(2026, 5), 0) == m(2026, 5)
    assert c.meses_entre(m(2026, 1), m(2027, 2)) == 13
    assert c.meses_entre(m(2026, 3), m(2026, 1)) == -2
    assert c.intervalo_meses(m(2026, 11), m(2027, 1)) == [m(2026, 11), m(2026, 12), m(2027, 1)]
    assert c.primeiro_dia(date(2026, 4, 17)) == m(2026, 4)


def test_arredondamento_half_up():
    assert c.q2(D("1.005")) == D("1.01")
    assert c.q2(D("2.675")) == D("2.68")
    assert c.q1(D("12.25")) == D("12.3")
    assert c.q4(D("0.12345")) == D("0.1235")


# --- participantes / valor mensal ---------------------------------------------------------------------------------


def test_exemplo_3h_de_2_analistas_mais_1h_de_1_executivo():
    """Antes: 3h x 2 analistas (R$80) ; depois: 0h. Executivo gasta 1h a mais (revisão), custo R$300."""
    entrada = por_tempo(
        [p(80, 2, 3, 0), p(300, 1, 0, 1)],
        frequencia="SEMANAL",
    )
    r = c.calcular_iniciativa(entrada, m(2026, 1))
    # analistas: 3 x 2 x 4.33 = 25.98h * 80 = 2078.40 ; executivo: -1 x 1 x 4.33 = -4.33h * 300 = -1299.00
    assert r.participantes[0].horas_mes == D("25.98")
    assert r.participantes[0].valor_mensal == D("2078.40")
    assert r.participantes[1].horas_mes == D("-4.33")
    assert r.participantes[1].valor_mensal == D("-1299.00")
    assert r.horas_mes == D("21.65")
    assert r.valor_mensal == D("779.40")
    assert c.q2(r.fte) == D("0.13")
    # antes = 3*2 + 0 = 6 ; depois = 0 + 1 = 1 ; (6-1)/6
    assert c.q2(r.perc_reducao) == D("83.33")


def test_exemplo_3h_de_2_analistas_e_1h_de_1_executivo_removidos():
    """Variante: 3h de 2 analistas + 1h de 1 executivo viram 0h (tudo automatizado), diaria util."""
    r = c.calcular_iniciativa(por_tempo([p(80, 2, 3, 0), p(300, 1, 1, 0)]), m(2026, 1))
    assert r.horas_mes == D(3 * 2 * 22 + 1 * 22)  # 154
    assert r.valor_mensal == D(3 * 2 * 22 * 80 + 1 * 22 * 300)  # 10560 + 6600
    assert r.participantes[1].valor_mensal == D(6600)
    assert r.perc_reducao == D(100)


def test_caso_mvp_5h_para_1_5h_diaria_util_uma_pessoa_r80():
    r = c.calcular_iniciativa(por_tempo([p(80, 1, 5, "1.5")]), m(2026, 1))
    assert r.horas_mes == D(77)
    assert c.q2(r.valor_mensal) == D("6160.00")
    assert c.q2(r.fte) == D("0.46")
    assert c.q2(r.perc_reducao) == D(70)


def test_multiplicadores_de_frequencia():
    esperado = {
        "DIARIA_UTIL": 22,
        "DIARIA_CORRIDA": 30,
        "SEMANAL": D("4.33"),
        "QUINZENAL": 2,
        "MENSAL": 1,
    }
    for freq, mult in esperado.items():
        r = c.calcular_iniciativa(por_tempo([p(10, 1, 2, 1)], frequencia=freq), m(2026, 1))
        assert r.horas_mes == D(mult), freq
    with pytest.raises(ValueError):
        c.multiplicador("ANUAL")
    with pytest.raises(ValueError):
        c.multiplicador(None)


def test_participante_com_delta_negativo_nao_sofre_clamp():
    r = c.calcular_iniciativa(por_tempo([p(300, 1, 0, 2)], frequencia="MENSAL"), m(2026, 1))
    assert r.horas_mes == D(-2)
    assert r.valor_mensal == D(-600)
    assert r.fte < 0
    assert r.perc_reducao is None  # soma de antes = 0
    # saving negativo: sem payback
    assert r.saving_janela == D(-3600)
    r2 = c.calcular_iniciativa(por_tempo([p(300, 1, 0, 2)], frequencia="MENSAL", investimento_reais=D(100)), m(2026, 1))
    assert r2.payback_meses is None and r2.se_paga_na_janela is False


def test_direto_reais_nao_tem_horas_nem_fte_nem_reducao():
    r = c.calcular_iniciativa(direto("1500.50"), m(2026, 1))
    assert (r.valor_mensal, r.horas_mes, r.fte, r.perc_reducao) == (D("1500.50"), 0, 0, None)
    assert r.participantes == ()
    assert c.calcular_iniciativa(direto("0"), m(2026, 1)).valor_mensal == 0


# --- janela e status ----------------------------------------------------------------------------------------------


def test_janela_padrao_seis_meses_e_status():
    e = direto("100", inicio=m(2026, 3))
    assert c.fim_janela(m(2026, 3), 6) == m(2026, 8)
    casos = [
        (m(2026, 2), c.PLANEJADA, 0),
        (m(2026, 3), c.EM_SAVING, 1),
        (m(2026, 8), c.EM_SAVING, 6),
        (m(2026, 9), c.NOVO_NORMAL, 6),
        (m(2030, 1), c.NOVO_NORMAL, 6),
    ]
    for ref, status, contados in casos:
        r = c.calcular_iniciativa(e, ref)
        assert (r.status, r.meses_contados) == (status, contados), ref
        assert r.saving_acumulado == D(100) * contados
        assert r.meses_janela == 6 and r.saving_janela == D(600)
        assert r.fim_janela == m(2026, 8)


def test_janela_atravessa_virada_de_ano_e_janela_de_um_mes():
    r = c.calcular_iniciativa(direto("10", inicio=m(2026, 11), janela=4), m(2027, 1))
    assert r.fim_janela == m(2027, 2) and r.status == c.EM_SAVING and r.meses_contados == 3
    um = direto("10", inicio=m(2026, 5), janela=1)
    assert c.calcular_iniciativa(um, m(2026, 5)).status == c.EM_SAVING
    assert c.calcular_iniciativa(um, m(2026, 6)).status == c.NOVO_NORMAL


def test_encerramento_antecipado_reduz_a_janela():
    e = direto("100", inicio=JAN, enc=m(2026, 3))
    assert c.meses_janela_efetivos(m(2026, 1), 6, m(2026, 3)) == 3
    r = c.calcular_iniciativa(e, m(2026, 3))
    assert r.status == c.EM_SAVING and r.meses_contados == 3 and r.meses_janela == 3
    assert r.saving_janela == D(300) and r.fim_janela == m(2026, 6)
    r = c.calcular_iniciativa(e, m(2026, 4))
    assert r.status == c.ENCERRADA and r.meses_contados == 3 and r.saving_acumulado == D(300)
    # encerrada continua encerrada depois do fim da janela original
    assert c.calcular_iniciativa(e, m(2027, 1)).status == c.ENCERRADA
    # encerra no mês de início: 1 mês de saving
    um = direto("100", inicio=JAN, enc=m(2026, 1))
    assert c.calcular_iniciativa(um, m(2026, 2)).meses_janela == 1


def test_encerramento_apos_fim_da_janela_e_ignorado():
    e = direto("100", inicio=JAN, enc=m(2026, 6))  # fim da janela = jun
    assert c.calcular_iniciativa(e, m(2026, 7)).status == c.NOVO_NORMAL
    e2 = direto("100", inicio=JAN, enc=m(2027, 6))
    r = c.calcular_iniciativa(e2, m(2026, 9))
    assert r.status == c.NOVO_NORMAL and r.meses_janela == 6


def test_saving_no_mes():
    args = (D(50), m(2026, 2), 3, None)
    assert [c.saving_no_mes(*args, mes=m(2026, n)) for n in range(1, 7)] == [0, 50, 50, 50, 0, 0]
    enc = (D(50), m(2026, 2), 3, m(2026, 3))
    assert [c.saving_no_mes(*enc, mes=m(2026, n)) for n in range(1, 6)] == [0, 50, 50, 0, 0]


# --- investimento, ROI, payback -----------------------------------------------------------------------------------


def test_investimento_roi_e_payback():
    e = direto("1000", investimento_reais=D(2000), investimento_horas=D(10), investimento_custo_hora=D(100))
    r = c.calcular_iniciativa(e, m(2026, 1))
    assert r.investimento_total == D(3000)
    assert r.saving_janela == D(6000)
    assert r.roi_janela_pct == D(100)
    assert r.payback_meses == 3 and r.se_paga_na_janela is True


def test_payback_arredonda_para_cima_e_pode_nao_pagar_na_janela():
    r = c.calcular_iniciativa(direto("1000", investimento_reais=D("7000.01")), m(2026, 1))
    assert r.payback_meses == 8 and r.se_paga_na_janela is False
    assert c.q1(r.roi_janela_pct) == D("-14.3")
    exato = c.calcular_iniciativa(direto("1000", investimento_reais=D(6000)), m(2026, 1))
    assert exato.payback_meses == 6 and exato.se_paga_na_janela is True and exato.roi_janela_pct == 0
    # janela menor por encerramento
    curto = c.calcular_iniciativa(direto("1000", enc=m(2026, 2), investimento_reais=D(3000)), m(2026, 1))
    assert curto.payback_meses == 3 and curto.se_paga_na_janela is False


def test_sem_investimento_roi_nulo_e_payback_zero():
    r = c.calcular_iniciativa(direto("100"), m(2026, 1))
    assert r.roi_janela_pct is None and r.payback_meses == 0 and r.se_paga_na_janela is True
    assert c.investimento_total(D(0), D(0), D(0)) == 0


def test_investimento_sem_saving_nunca_se_paga():
    r = c.calcular_iniciativa(direto("0", investimento_reais=D(500)), m(2026, 1))
    assert r.payback_meses is None and r.se_paga_na_janela is False
    assert r.roi_janela_pct == D(-100)


# --- série mensal -------------------------------------------------------------------------------------------------


def resumo(entrada, referencia=JAN, tipo="MELHORIA"):
    calculo = c.calcular_iniciativa(entrada, referencia)
    return c.IniciativaResumo(
        entrada.modo_calculo, tipo, entrada.mes_inicio, entrada.janela_meses, entrada.mes_encerramento, calculo
    )


def test_serie_mensal_separa_direto_e_horas_e_marca_projetado():
    a = resumo(direto("100", inicio=m(2026, 2), janela=2))
    b = resumo(por_tempo([p(10, 1, 2, 1)], frequencia="MENSAL", inicio=m(2026, 3), janela=2))  # 10/mês
    serie = c.serie_mensal([a, b], m(2026, 1), m(2026, 5), m(2026, 3))
    assert [x.competencia.month for x in serie] == [1, 2, 3, 4, 5]
    assert [x.saving_direto for x in serie] == [0, 100, 100, 0, 0]
    assert [x.saving_horas for x in serie] == [0, 0, 10, 10, 0]
    assert [x.saving_total for x in serie] == [0, 100, 110, 10, 0]
    assert [x.projetado for x in serie] == [False, False, False, True, True]


def test_serie_mensal_vazia_e_intervalo_unico():
    serie = c.serie_mensal([], m(2026, 1), m(2026, 1), m(2026, 1))
    assert len(serie) == 1 and serie[0].saving_total == 0 and serie[0].projetado is False


def test_variacao_e_custo_unitario():
    assert c.variacao(D(100), D(80)) == D(20)
    assert c.variacao(D(100), D(130)) == D(-30)
    assert c.variacao(None, D(1)) is None and c.variacao(D(1), None) is None
    assert c.custo_unitario(D(100), D(40)) == D("2.5")
    assert c.custo_unitario(D(100), D(0)) is None and c.custo_unitario(D(100), None) is None

from datetime import date
from uuid import uuid4

import pytest

from src.backend.services.rotinas_agenda import (
    DIAS_SEMANA,
    DIAS_UTEIS,
    ExecucaoAgenda,
    RotinaAgenda,
    SemanaAgenda,
    datas_previstas,
    expandir_semana,
    normalizar_tipo,
    primeiro_dia_util,
    resumo_esforco,
    situacao,
    ultimo_dia_util,
    vigente_na_semana,
)


def rotina(
    tipo="SEMANAL", dia_semana="Segunda", dia_mes=None, inicio=date(2026, 1, 1), ativo=True, categoria="RUN", esforco=30
):
    return RotinaAgenda(
        id=uuid4(),
        categoria=categoria,
        tipo_agendamento=tipo,
        dia_semana=dia_semana,
        dia_mes=dia_mes,
        inicio_vigencia=inicio,
        ativo=ativo,
        esforco_estimado_min=esforco,
    )


def semana(inicio, fim, criada=date(2026, 1, 1)):
    return SemanaAgenda(id=uuid4(), data_inicio=inicio, data_fim=fim, criada_em=criada)


# Segunda 2026-10-19 a Domingo 2026-10-25
S_OUT = semana(date(2026, 10, 19), date(2026, 10, 25))


def test_constantes_de_dias():
    assert DIAS_SEMANA[date(2026, 10, 19).weekday()] == "Segunda"
    assert DIAS_UTEIS == ("Segunda", "Terça", "Quarta", "Quinta", "Sexta")


def test_primeiro_e_ultimo_dia_util_com_fim_de_semana():
    assert primeiro_dia_util(2026, 2) == date(2026, 2, 2)  # 1/2 é domingo
    assert primeiro_dia_util(2026, 8) == date(2026, 8, 3)  # 1/8 é sábado
    assert primeiro_dia_util(2026, 10) == date(2026, 10, 1)
    assert ultimo_dia_util(2026, 10) == date(2026, 10, 30)  # 31/10 é sábado
    assert ultimo_dia_util(2026, 5) == date(2026, 5, 29)  # 31/5 é domingo
    assert ultimo_dia_util(2026, 8) == date(2026, 8, 31)


def test_semanal_no_dia_certo_e_fora_da_semana():
    assert datas_previstas(rotina(dia_semana="Quarta"), S_OUT) == [("SEMANA", date(2026, 10, 21))]
    assert datas_previstas(rotina(dia_semana="Domingo"), S_OUT) == [("SEMANA", date(2026, 10, 25))]
    curta = semana(date(2026, 10, 19), date(2026, 10, 21))
    assert datas_previstas(rotina(dia_semana="Sexta"), curta) == []


def test_diaria_cinco_ocorrencias_e_parcial():
    r = rotina(tipo="DIARIA", dia_semana=None)
    assert [(o, d.day) for o, d in datas_previstas(r, S_OUT)] == [
        ("Segunda", 19),
        ("Terça", 20),
        ("Quarta", 21),
        ("Quinta", 22),
        ("Sexta", 23),
    ]
    curta = semana(date(2026, 10, 21), date(2026, 10, 23))
    assert [o for o, _ in datas_previstas(r, curta)] == ["Quarta", "Quinta", "Sexta"]


def test_mensal_dia_fixo_dia_31_em_fevereiro():
    r = rotina(tipo="MENSAL_DIA_FIXO", dia_semana=None, dia_mes=31)
    final_fev = semana(date(2026, 2, 23), date(2026, 3, 1))
    assert datas_previstas(r, final_fev) == [("SEMANA", date(2026, 2, 28))]
    meio_fev = semana(date(2026, 2, 9), date(2026, 2, 15))
    assert datas_previstas(r, meio_fev) == []


def test_mensal_dia_fixo_semana_cruzando_meses():
    r = rotina(tipo="MENSAL_DIA_FIXO", dia_semana=None, dia_mes=1)
    cruza = semana(date(2026, 10, 26), date(2026, 11, 1))
    assert datas_previstas(r, cruza) == [("SEMANA", date(2026, 11, 1))]
    r31 = rotina(tipo="MENSAL_DIA_FIXO", dia_semana=None, dia_mes=31)
    cruza2 = semana(date(2026, 3, 30), date(2026, 4, 5))
    assert datas_previstas(r31, cruza2) == [("SEMANA", date(2026, 3, 31))]


def test_mensal_dia_fixo_semana_sem_o_dia():
    r = rotina(tipo="MENSAL_DIA_FIXO", dia_semana=None, dia_mes=5)
    assert datas_previstas(r, S_OUT) == []


def test_mensal_primeiro_e_ultimo_util():
    prim = rotina(tipo="MENSAL_PRIMEIRO_UTIL", dia_semana=None)
    ult = rotina(tipo="MENSAL_ULTIMO_UTIL", dia_semana=None)
    s_nov = semana(date(2026, 10, 26), date(2026, 11, 1))
    assert datas_previstas(ult, s_nov) == [("SEMANA", date(2026, 10, 30))]
    assert datas_previstas(prim, s_nov) == []  # 1/11 é domingo; o 1º útil é 2/11
    s_nov2 = semana(date(2026, 11, 2), date(2026, 11, 8))
    assert datas_previstas(prim, s_nov2) == [("SEMANA", date(2026, 11, 2))]
    assert datas_previstas(ult, S_OUT) == []


def test_quinzenal_dias_1_e_15():
    r = rotina(tipo="QUINZENAL", dia_semana=None)
    assert datas_previstas(r, semana(date(2026, 10, 12), date(2026, 10, 18))) == [("SEMANA", date(2026, 10, 15))]
    assert datas_previstas(r, semana(date(2026, 10, 26), date(2026, 11, 1))) == [("SEMANA", date(2026, 11, 1))]
    assert datas_previstas(r, S_OUT) == []


def test_semana_sem_datas_usa_fallback():
    sem = semana(None, None)
    assert datas_previstas(rotina(), sem) == [("SEMANA", None)]
    assert datas_previstas(rotina(tipo="MENSAL_DIA_FIXO", dia_mes=10), sem) == [("SEMANA", None)]
    assert [(o, d) for o, d in datas_previstas(rotina(tipo="DIARIA"), semana(date(2026, 10, 19), None))] == [
        (dia, None) for dia in DIAS_UTEIS
    ]


def test_vigencia():
    r = rotina(inicio=date(2026, 10, 26))
    assert vigente_na_semana(r, S_OUT) is False
    assert vigente_na_semana(r, semana(date(2026, 10, 26), date(2026, 11, 1))) is True
    # referência: data_fim; senão data_inicio; senão criada_em
    assert vigente_na_semana(r, semana(None, None, criada=date(2026, 10, 26))) is True
    assert vigente_na_semana(r, semana(None, None, criada=date(2026, 10, 25))) is False
    assert expandir_semana([r], S_OUT, [], date(2026, 10, 21)) == []


def test_rotina_inativa_so_com_execucao():
    r = rotina(ativo=False, dia_semana="Terça")
    assert expandir_semana([r], S_OUT, [], date(2026, 10, 21)) == []
    ex = ExecucaoAgenda(r.id, S_OUT.id, "SEMANA", "CONCLUIDA", 25)
    occ = expandir_semana([r], S_OUT, [ex], date(2026, 10, 21))
    assert len(occ) == 1 and occ[0].status == "CONCLUIDA" and occ[0].esforco_real_min == 25
    # execução de outra semana não conta
    outra = ExecucaoAgenda(r.id, uuid4(), "SEMANA", "CONCLUIDA", 25)
    assert expandir_semana([r], S_OUT, [outra], date(2026, 10, 21)) == []


def test_situacao():
    hoje = date(2026, 10, 21)
    assert situacao("CONCLUIDA", date(2026, 10, 1), hoje) == "CONCLUIDA"
    assert situacao("CONCLUIDA", None, hoje) == "CONCLUIDA"
    assert situacao("PENDENTE", None, hoje) == "SEM_DATA"
    assert situacao("PENDENTE", hoje, hoje) == "VENCE_HOJE"
    assert situacao("PENDENTE", date(2026, 10, 20), hoje) == "ATRASADA"
    assert situacao("PENDENTE", date(2026, 10, 22), hoje) == "PREVISTA"


def test_expandir_preserva_ordem_e_aplica_execucao_por_ocorrencia():
    a = rotina(tipo="DIARIA", dia_semana=None, esforco=10)
    b = rotina(dia_semana="Segunda", categoria="BUILD", esforco=60)
    ex = ExecucaoAgenda(a.id, S_OUT.id, "Terça", "CONCLUIDA", None)
    occ = expandir_semana([a, b], S_OUT, [ex], date(2026, 10, 20))
    assert [o.rotina_id for o in occ] == [a.id] * 5 + [b.id]
    por_dia = {o.ocorrencia: o for o in occ if o.rotina_id == a.id}
    assert por_dia["Segunda"].situacao == "ATRASADA"
    assert por_dia["Terça"].status == "CONCLUIDA" and por_dia["Terça"].situacao == "CONCLUIDA"
    assert por_dia["Quarta"].situacao == "PREVISTA"
    assert occ[-1].situacao == "ATRASADA" and occ[-1].categoria == "BUILD"


def test_resumo_esforco_real_ou_estimado():
    hoje = date(2026, 10, 21)
    a = rotina(esforco=30, categoria="RUN", dia_semana="Segunda")
    b = rotina(esforco=60, categoria="BUILD", dia_semana="Terça")
    c = rotina(esforco=45, categoria="RUN", dia_semana="Quarta")
    execs = [
        ExecucaoAgenda(a.id, S_OUT.id, "SEMANA", "CONCLUIDA", 50),  # real
        ExecucaoAgenda(b.id, S_OUT.id, "SEMANA", "CONCLUIDA", None),  # estimado
    ]
    r = resumo_esforco(expandir_semana([a, b, c], S_OUT, execs, hoje))
    assert r["RUN"] == {
        "ocorrencias": 2,
        "concluidas": 1,
        "pendentes": 1,
        "minutos_previstos": 75,
        "minutos_executados": 50,
    }
    assert r["BUILD"] == {
        "ocorrencias": 1,
        "concluidas": 1,
        "pendentes": 0,
        "minutos_previstos": 60,
        "minutos_executados": 60,
    }
    assert r["TOTAL"] == {
        "ocorrencias": 3,
        "concluidas": 2,
        "pendentes": 1,
        "minutos_previstos": 135,
        "minutos_executados": 110,
    }


def test_resumo_vazio():
    r = resumo_esforco([])
    assert set(r) == {"BUILD", "RUN", "TOTAL"}
    assert all(v["ocorrencias"] == 0 for v in r.values())


def test_normalizar_tipo():
    assert normalizar_tipo(" semanal ") == "SEMANAL"
    assert normalizar_tipo("mensal") == "MENSAL_DIA_FIXO"
    assert normalizar_tipo("1_util") == "MENSAL_PRIMEIRO_UTIL"
    assert normalizar_tipo("primeiro_util") == "MENSAL_PRIMEIRO_UTIL"
    for alias in ("ULTIMO_UTIL", "MENSAL_ULTIMO_DIA", "ultimo_dia"):
        assert normalizar_tipo(alias) == "MENSAL_ULTIMO_UTIL"
    with pytest.raises(ValueError):
        normalizar_tipo("ANUAL")
    with pytest.raises(ValueError):
        normalizar_tipo("")

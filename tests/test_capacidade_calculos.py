from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from src.backend.services.capacidade import (
    GRUPOS_PADRAO,
    META_BUILD_MIN,
    META_RUN_MAX,
    calcular_dashboard,
    contar_demandas_por_grupo,
)


def grupo(nome, categoria, ativo=True):
    return SimpleNamespace(id=uuid4(), nome=nome, categoria=categoria, icone="x", cor="#000000", ativo=ativo)


def lanc(g, status, quantidade):
    return SimpleNamespace(grupo_id=g.id, status=status, quantidade=quantidade)


def test_metas_e_grupos_padrao():
    assert (META_BUILD_MIN, META_RUN_MAX) == (0.70, 0.30)
    assert len(GRUPOS_PADRAO) == 6
    assert sum(1 for g in GRUPOS_PADRAO if g["categoria"] == "BUILD") == 1
    assert len({g["nome"] for g in GRUPOS_PADRAO}) == 6


def test_sem_dados_nao_divide_por_zero():
    r = calcular_dashboard([], [])
    assert r["total"] == 0
    assert r["periodo"] == "Todas as semanas"
    assert r["semana_id"] is None
    assert r["perc_build"] == r["perc_run"] == 0
    assert r["build_atingiu_meta"] is False
    assert r["run_atingiu_meta"] is True
    assert r["gap_build_pp"] == -70.0
    assert r["gap_run_pp"] == -30.0
    assert r["taxa_resolucao"] == 0
    assert r["groups"] == []


def test_grupo_sem_lancamentos_tem_zeros():
    r = calcular_dashboard([grupo("A", "BUILD")], [])
    assert r["groups"][0]["total"] == 0
    assert r["groups"][0]["taxa_resolucao"] == 0
    assert r["groups"][0]["pct_aberto"] == 0


def test_meta_exatamente_atingida():
    b, r_ = grupo("B", "BUILD"), grupo("R", "RUN")
    r = calcular_dashboard([b, r_], [lanc(b, "ABERTO", 7), lanc(r_, "ABERTO", 3)])
    assert r["perc_build"] == 0.7
    assert r["perc_run"] == 0.3
    assert r["build_atingiu_meta"] is True
    assert r["run_atingiu_meta"] is True
    assert r["gap_build_pp"] == 0.0
    assert r["gap_run_pp"] == 0.0


def test_meta_nao_atingida_e_gaps():
    b, r_ = grupo("B", "BUILD"), grupo("R", "RUN")
    r = calcular_dashboard([b, r_], [lanc(b, "ABERTO", 5), lanc(r_, "RESOLVIDO", 5)])
    assert r["perc_build"] == 0.5
    assert r["build_atingiu_meta"] is False
    assert r["run_atingiu_meta"] is False
    assert r["gap_build_pp"] == -20.0
    assert r["gap_run_pp"] == 20.0
    assert r["taxa_resolucao"] == 50.0


def test_resolvidos_e_abertos_por_categoria():
    b, r_ = grupo("B", "BUILD"), grupo("R", "RUN")
    itens = [lanc(b, "RESOLVIDO", 8), lanc(r_, "RESOLVIDO", 2), lanc(b, "ABERTO", 1), lanc(r_, "ABERTO", 9)]
    r = calcular_dashboard([b, r_], itens)
    assert (r["resolvidos_build"], r["resolvidos_run"]) == (8, 2)
    assert r["perc_build_resolvidos"] == 0.8
    assert r["resolvidos_build_atingiu_meta"] is True
    assert r["resolvidos_run_atingiu_meta"] is True
    assert r["gap_build_resolvidos_pp"] == 10.0
    assert r["gap_run_resolvidos_pp"] == -10.0
    assert (r["abertos_build"], r["abertos_run"]) == (1, 9)
    assert r["perc_run_abertos"] == 0.9
    assert r["total_abertos"] == 10
    assert r["total_resolvidos"] == 10


def test_grupos_inativos_sao_ignorados():
    b, ativo, inativo = grupo("B", "BUILD"), grupo("R", "RUN"), grupo("Z", "RUN", ativo=False)
    r = calcular_dashboard(
        [b, ativo, inativo], [lanc(b, "ABERTO", 7), lanc(ativo, "ABERTO", 3), lanc(inativo, "ABERTO", 90)]
    )
    assert r["total"] == 10
    assert r["qtd_run"] == 3
    assert [g["nome"] for g in r["groups"]] == ["B", "R"]


def test_percentuais_do_grupo_e_ordenacao():
    r1, b1, r0 = grupo("Zeta", "RUN"), grupo("Beta", "BUILD"), grupo("Alfa", "RUN")
    r = calcular_dashboard([r1, b1, r0], [lanc(r1, "ABERTO", 1), lanc(r1, "RESOLVIDO", 2)])
    assert [g["nome"] for g in r["groups"]] == ["Beta", "Alfa", "Zeta"]
    zeta = r["groups"][2]
    assert (zeta["abertos"], zeta["resolvidos"], zeta["total"]) == (1, 2, 3)
    assert zeta["taxa_resolucao"] == 66.7
    assert zeta["pct_aberto"] == 33.3
    assert zeta["pct_resolvido"] == 66.7


def test_semana_informada():
    semana = SimpleNamespace(id=uuid4(), identificacao="2026-S01")
    r = calcular_dashboard([], [], semana)
    assert r["semana_id"] == semana.id
    assert r["periodo"] == "2026-S01"


def resumo(ocorrencias, concluidas, previstos, executados):
    return {
        "ocorrencias": ocorrencias,
        "concluidas": concluidas,
        "pendentes": ocorrencias - concluidas,
        "minutos_previstos": previstos,
        "minutos_executados": executados,
    }


def test_rotinas_none_mantem_comportamento():
    b = grupo("B", "BUILD")
    r = calcular_dashboard([b], [lanc(b, "ABERTO", 4)], rotinas=None)
    assert r["rotinas"] == [] and r["total"] == 4


def test_rotinas_somam_pela_categoria():
    b, r_ = grupo("B", "BUILD"), grupo("R", "RUN")
    rotinas = {
        "BUILD": resumo(6, 2, 360, 150),
        "RUN": resumo(0, 0, 0, 0),
        "TOTAL": resumo(6, 2, 360, 150),
    }
    r = calcular_dashboard([b, r_], [lanc(b, "ABERTO", 1), lanc(r_, "ABERTO", 3)], rotinas=rotinas)
    assert r["rotinas"] == [
        {
            "categoria": "BUILD",
            "abertos": 4,
            "resolvidos": 2,
            "total": 6,
            "minutos_previstos": 360,
            "minutos_executados": 150,
        }
    ]
    assert (r["qtd_build"], r["qtd_run"], r["total"]) == (7, 3, 10)
    assert (r["abertos_build"], r["resolvidos_build"]) == (5, 2)
    assert r["total_abertos"] == 8 and r["total_resolvidos"] == 2
    assert r["perc_build"] == 0.7 and r["build_atingiu_meta"] is True
    assert [g["nome"] for g in r["groups"]] == ["B", "R"] and r["groups"][0]["total"] == 1


def test_rotinas_sem_grupos_e_com_run():
    rotinas = {"BUILD": resumo(0, 0, 0, 0), "RUN": resumo(3, 3, 90, 100), "TOTAL": resumo(3, 3, 90, 100)}
    r = calcular_dashboard([], [], rotinas=rotinas)
    assert [x["categoria"] for x in r["rotinas"]] == ["RUN"]
    assert (r["qtd_run"], r["resolvidos_run"], r["perc_run"], r["run_atingiu_meta"]) == (3, 3, 1.0, False)
    assert r["taxa_resolucao"] == 100.0


def test_demandas_somam_aos_abertos_e_resolvidos_do_grupo():
    b, r_, off = grupo("B", "BUILD"), grupo("R", "RUN"), grupo("Off", "RUN", ativo=False)
    demandas = {b.id: (2, 1), r_.id: (0, 3), off.id: (9, 9)}
    r = calcular_dashboard([b, r_, off], [lanc(b, "ABERTO", 1)], demandas=demandas)
    gb, gr = r["groups"]
    assert (gb["abertos"], gb["resolvidos"], gb["demandas_abertas"], gb["demandas_resolvidas"]) == (3, 1, 2, 1)
    assert (gr["abertos"], gr["resolvidos"], gr["demandas_abertas"], gr["demandas_resolvidas"]) == (0, 3, 0, 3)
    assert (r["abertos_build"], r["resolvidos_build"], r["abertos_run"], r["resolvidos_run"]) == (3, 1, 0, 3)
    assert (r["total_abertos"], r["total_resolvidos"], r["total"]) == (3, 4, 7)


def test_sem_demandas_os_campos_ficam_zerados():
    g = grupo("A", "BUILD")
    item = calcular_dashboard([g], [])["groups"][0]
    assert (item["demandas_abertas"], item["demandas_resolvidas"]) == (0, 0)


def dem(grupo_, status, criada, concluida=None):
    return (grupo_.id, status, criada, concluida)


def test_contar_demandas_sem_semana_soma_abertas_e_concluidas():
    g = grupo("A", "BUILD")
    agora = datetime(2026, 3, 4, 12, tzinfo=UTC)
    linhas = [dem(g, "ABERTA", agora), dem(g, "ABERTA", agora), dem(g, "CONCLUIDA", agora, agora)]
    assert contar_demandas_por_grupo(linhas) == {g.id: (2, 1)}
    assert contar_demandas_por_grupo([]) == {}


def test_contar_demandas_por_periodo_da_semana():
    g = grupo("A", "BUILD")
    semana = SimpleNamespace(data_inicio=date(2026, 3, 2), data_fim=date(2026, 3, 8))
    dentro = datetime(2026, 3, 4, 12, tzinfo=UTC)
    fora = datetime(2026, 2, 10, 12, tzinfo=UTC)
    linhas = [
        dem(g, "ABERTA", dentro),
        dem(g, "ABERTA", fora),
        dem(g, "CONCLUIDA", fora, dentro),  # conta pela conclusão
        dem(g, "CONCLUIDA", dentro, fora),  # aberta dentro, concluída fora: não conta
        dem(g, "CONCLUIDA", dentro.replace(tzinfo=None), dentro.replace(tzinfo=None)),  # SQLite: naive = UTC
    ]
    assert contar_demandas_por_grupo(linhas, semana) == {g.id: (1, 2)}


def test_contar_demandas_semana_sem_datas_nao_conta_nada():
    g = grupo("A", "BUILD")
    agora = datetime(2026, 3, 4, 12, tzinfo=UTC)
    linhas = [dem(g, "ABERTA", agora), dem(g, "CONCLUIDA", agora, agora)]
    for semana in (
        SimpleNamespace(data_inicio=None, data_fim=None),
        SimpleNamespace(data_inicio=date(2026, 3, 2), data_fim=None),
    ):
        assert contar_demandas_por_grupo(linhas, semana) == {}

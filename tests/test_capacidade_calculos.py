from types import SimpleNamespace
from uuid import uuid4

from src.backend.services.capacidade import GRUPOS_PADRAO, META_BUILD_MIN, META_RUN_MAX, calcular_dashboard


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

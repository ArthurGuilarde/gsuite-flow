from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.backend.api import deps
from src.backend.core import sessions
from src.backend.core.config import settings
from src.backend.integrations.guilarde.contracts import Authorization, Principal
from src.backend.models import Base

TENANT_A, TENANT_B = uuid4(), uuid4()
P = "/api/v1/finops"


@pytest.fixture
def grants():
    return {TENANT_A: {"access", "read", "write"}, TENANT_B: {"access", "read", "write"}}


@pytest.fixture
def client(monkeypatch, tmp_path, grants):
    engine = create_engine(f"sqlite:///{tmp_path / 'fin.sqlite3'}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    monkeypatch.setattr(deps, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "AUTH_MODE", "oidc")
    monkeypatch.setattr(sessions, "load_session", lambda _sid: {"access_token": "test", "csrf": "csrf"})
    monkeypatch.setattr(deps, "validate_access_token", lambda _token: Principal(sub="user-a"))

    async def authorize(_token, tenant_id, permission):
        perms = grants.get(tenant_id, set())
        return Authorization(
            sub="user-a",
            tenant_id=tenant_id,
            app_id=settings.APP_ID,
            allowed=permission in perms and "access" in perms,
            permissions=perms,
        )

    monkeypatch.setattr(deps.core_client, "authorize", authorize)
    from tests.support.tenant_example import create_test_app

    test_client = TestClient(create_test_app())
    test_client.cookies.set(settings.SESSION_COOKIE, "a" * 43)
    yield test_client
    engine.dispose()


def h(tenant, write=False):
    headers = {"X-Tenant-ID": str(tenant)}
    if write:
        headers.update({"X-CSRF-Token": "csrf", "Origin": settings.PUBLIC_URL})
    return headers


def get(c, path, tenant=TENANT_A):
    return c.get(P + path, headers=h(tenant))


def send(c, method, path, body=None, tenant=TENANT_A):
    return c.request(method, P + path, json=body, headers=h(tenant, True))


def nova_fonte(c, nome="Fabric", tenant=TENANT_A, **extra):
    r = send(c, "POST", "/fontes", {"nome": nome, **extra}, tenant)
    assert r.status_code == 201, r.text
    return r.json()


def nova_fatura(c, fonte, competencia="2026-01", realizado=1000, tenant=TENANT_A, **extra):
    corpo = {"fonte_id": fonte["id"], "competencia": competencia, "valor_realizado": realizado, **extra}
    r = send(c, "POST", "/faturas", corpo, tenant)
    assert r.status_code == 201, r.text
    return r.json()


def corpo_direto(titulo="Renegociar contrato", valor=1000, **extra):
    corpo = {
        "titulo": titulo,
        "tipo": "OTIMIZACAO_CUSTO",
        "modo_calculo": "DIRETO_REAIS",
        "valor_mensal": valor,
        "mes_inicio": "2026-01",
    }
    corpo.update(extra)
    return corpo


def corpo_tempo(titulo="Automação de relatório", **extra):
    corpo = {
        "titulo": titulo,
        "tipo": "AUTOMACAO",
        "modo_calculo": "POR_TEMPO",
        "frequencia": "DIARIA_UTIL",
        "mes_inicio": "2026-01",
        "participantes": [
            {"perfil_nome": "Analista", "custo_hora": 80, "qtd_pessoas": 1, "horas_antes": 5, "horas_depois": 1.5}
        ],
    }
    corpo.update(extra)
    return corpo


def criar_iniciativa(c, corpo, tenant=TENANT_A):
    r = send(c, "POST", "/iniciativas", corpo, tenant)
    assert r.status_code == 201, r.text
    return r.json()


# --- perfis ---------------------------------------------------------------------------------------------------------


def test_perfis_crud_e_conflito(client):
    a = send(client, "POST", "/perfis", {"nome": "Analista", "custo_hora": 80})
    assert a.status_code == 201
    corpo = a.json()
    assert corpo["custo_hora"] == 80.0 and corpo["ativo"] is True and corpo["created_at"]
    assert "tenant_id" not in corpo
    send(client, "POST", "/perfis", {"nome": "Executivo", "custo_hora": 300.5})
    assert send(client, "POST", "/perfis", {"nome": "Analista", "custo_hora": 1}).status_code == 409
    assert [p["nome"] for p in get(client, "/perfis").json()] == ["Analista", "Executivo"]
    outro = get(client, "/perfis", TENANT_B).json()
    assert outro == []
    # tenant B pode usar o mesmo nome
    assert send(client, "POST", "/perfis", {"nome": "Analista", "custo_hora": 1}, TENANT_B).status_code == 201
    p = send(client, "PATCH", f"/perfis/{corpo['id']}", {"custo_hora": 95.25, "ativo": False})
    assert p.status_code == 200 and p.json()["custo_hora"] == 95.25 and p.json()["ativo"] is False
    assert send(client, "PATCH", f"/perfis/{corpo['id']}", {"nome": "Executivo"}).status_code == 409
    assert send(client, "PATCH", f"/perfis/{corpo['id']}", {"nome": None}).status_code == 422
    assert send(client, "DELETE", f"/perfis/{corpo['id']}").status_code == 204
    assert send(client, "DELETE", f"/perfis/{corpo['id']}").status_code == 404
    assert send(client, "PATCH", f"/perfis/{uuid4()}", {"ativo": True}).status_code == 404


def test_perfis_validacao(client):
    for ruim in (
        {"nome": "", "custo_hora": 1},
        {"nome": "x", "custo_hora": -1},
        {"nome": "x"},
        {"nome": "x" * 81, "custo_hora": 1},
        {"nome": "x", "custo_hora": 1, "tenant_id": str(TENANT_B)},
        {"nome": "x", "custo_hora": 1.234},
    ):
        assert send(client, "POST", "/perfis", ruim).status_code == 422, ruim


def test_perfil_removido_nao_altera_snapshot_do_participante(client):
    perfil = send(client, "POST", "/perfis", {"nome": "Analista", "custo_hora": 80}).json()
    ini = criar_iniciativa(client, corpo_tempo())
    send(client, "PATCH", f"/perfis/{perfil['id']}", {"custo_hora": 999})
    send(client, "DELETE", f"/perfis/{perfil['id']}")
    lido = get(client, f"/iniciativas/{ini['id']}").json()
    assert lido["participantes"][0]["custo_hora"] == 80.0
    assert lido["calculo"]["valor_mensal"] == 6160.0


# --- fontes e faturas -----------------------------------------------------------------------------------------------


def test_fontes_crud(client):
    f = nova_fonte(client, "Fabric", descricao="Capacidade F64", metrica_nome="Usuários ativos")
    assert f["metrica_nome"] == "Usuários ativos" and f["ativo"] is True
    assert send(client, "POST", "/fontes", {"nome": "Fabric"}).status_code == 409
    assert nova_fonte(client, "AWS")["metrica_nome"] is None
    assert [x["nome"] for x in get(client, "/fontes").json()] == ["AWS", "Fabric"]
    p = send(client, "PATCH", f"/fontes/{f['id']}", {"metrica_nome": None, "ativo": False, "descricao": "novo"})
    assert p.status_code == 200 and p.json()["metrica_nome"] is None and p.json()["ativo"] is False
    assert p.json()["descricao"] == "novo"
    assert send(client, "PATCH", f"/fontes/{f['id']}", {"nome": "AWS"}).status_code == 409
    assert send(client, "PATCH", f"/fontes/{uuid4()}", {"ativo": True}).status_code == 404
    assert send(client, "DELETE", f"/fontes/{uuid4()}").status_code == 404
    assert send(client, "DELETE", f"/fontes/{f['id']}").status_code == 204
    assert [x["nome"] for x in get(client, "/fontes").json()] == ["AWS"]


def test_faturas_crud_variacao_e_custo_unitario(client):
    f = nova_fonte(client, "Fabric", metrica_nome="Usuários ativos")
    a = nova_fatura(client, f, "2026-01", 900, valor_orcado=1000, metrica_valor=300, observacao="ok")
    assert a["competencia"] == "2026-01" and a["fonte_nome"] == "Fabric"
    assert a["variacao"] == 100.0 and a["custo_unitario"] == 3.0
    estourou = nova_fatura(client, f, "2026-02", 1200.5, valor_orcado=1000)
    assert estourou["variacao"] == -200.5 and estourou["custo_unitario"] is None
    sem_orcado = nova_fatura(client, f, "2026-03", 500, metrica_valor=0)
    assert sem_orcado["variacao"] is None and sem_orcado["custo_unitario"] is None
    terco = nova_fatura(client, f, "2026-04", 100, metrica_valor=3)
    assert terco["custo_unitario"] == 33.3333
    assert [x["competencia"] for x in get(client, "/faturas").json()] == ["2026-04", "2026-03", "2026-02", "2026-01"]
    filtro = get(client, "/faturas?de=2026-02&ate=2026-03").json()
    assert [x["competencia"] for x in filtro] == ["2026-03", "2026-02"]
    assert len(get(client, f"/faturas?fonte_id={f['id']}").json()) == 4
    assert get(client, f"/faturas?fonte_id={uuid4()}").json() == []
    p = send(client, "PATCH", f"/faturas/{a['id']}", {"valor_realizado": 950, "valor_orcado": None, "observacao": None})
    assert p.status_code == 200 and p.json()["valor_orcado"] is None and p.json()["variacao"] is None
    assert p.json()["valor_realizado"] == 950.0 and p.json()["observacao"] is None
    assert p.json()["metrica_valor"] == 300.0
    assert send(client, "PATCH", f"/faturas/{a['id']}", {"competencia": "2026-02"}).status_code == 409
    assert send(client, "PATCH", f"/faturas/{a['id']}", {"valor_realizado": None}).status_code == 422
    assert send(client, "PATCH", f"/faturas/{a['id']}", {"fonte_id": f["id"]}).status_code == 422
    assert send(client, "PATCH", f"/faturas/{uuid4()}", {"observacao": "x"}).status_code == 404
    assert send(client, "DELETE", f"/faturas/{a['id']}").status_code == 204
    assert send(client, "DELETE", f"/faturas/{a['id']}").status_code == 404


def test_faturas_conflito_validacao_e_filtros_invalidos(client):
    f = nova_fonte(client)
    nova_fatura(client, f, "2026-01")
    dup = {"fonte_id": f["id"], "competencia": "2026-01", "valor_realizado": 1}
    assert send(client, "POST", "/faturas", dup).status_code == 409
    # a transação continua utilizável após o conflito
    assert send(client, "POST", "/faturas", {**dup, "competencia": "2026-02"}).status_code == 201
    for ruim in (
        {**dup, "competencia": "2026-13"},
        {**dup, "competencia": "01/2026"},
        {**dup, "competencia": "2026-1-1"},
        {**dup, "valor_realizado": -1},
        {**dup, "valor_orcado": -1},
        {**dup, "metrica_valor": -1},
        {"fonte_id": f["id"], "competencia": "2026-05"},
        {**dup, "tenant_id": str(TENANT_B)},
    ):
        assert send(client, "POST", "/faturas", ruim).status_code == 422, ruim
    assert get(client, "/faturas?de=2026-99").status_code == 422
    assert get(client, "/faturas?ate=abc").status_code == 422
    assert send(client, "POST", "/faturas", {**dup, "fonte_id": str(uuid4())}).status_code == 404


def test_delete_fonte_apaga_faturas_e_bloqueia_com_iniciativa(client):
    livre = nova_fonte(client, "Livre")
    nova_fatura(client, livre, "2026-01")
    nova_fatura(client, livre, "2026-02")
    ocupada = nova_fonte(client, "Ocupada")
    nova_fatura(client, ocupada, "2026-01")
    ini = criar_iniciativa(client, corpo_direto(fonte_id=ocupada["id"]))
    assert ini["fonte_nome"] == "Ocupada"
    r = send(client, "DELETE", f"/fontes/{ocupada['id']}")
    assert r.status_code == 409 and "detail" in r.json()
    assert len(get(client, f"/faturas?fonte_id={ocupada['id']}").json()) == 1
    assert send(client, "DELETE", f"/fontes/{livre['id']}").status_code == 204
    assert get(client, "/faturas").json() != [] and len(get(client, "/faturas").json()) == 1
    # desvinculando a iniciativa a fonte pode ser excluída
    send(client, "PUT", f"/iniciativas/{ini['id']}", corpo_direto(fonte_id=None))
    assert send(client, "DELETE", f"/fontes/{ocupada['id']}").status_code == 204
    assert get(client, "/faturas").json() == []


# --- iniciativas ----------------------------------------------------------------------------------------------------


def test_iniciativa_direta_crud(client):
    ini = criar_iniciativa(
        client, corpo_direto(descricao="Contrato anual", tipo="otimizacao_custo", frequencia="MENSAL")
    )
    assert ini["tipo"] == "OTIMIZACAO_CUSTO" and ini["modo_calculo"] == "DIRETO_REAIS"
    assert ini["valor_mensal"] == 1000.0 and ini["frequencia"] is None and ini["participantes"] == []
    assert ini["janela_meses"] == 6 and ini["mes_inicio"] == "2026-01" and ini["mes_encerramento"] is None
    assert ini["investimento_reais"] == 0.0 and ini["fonte_id"] is None and ini["fonte_nome"] is None
    assert ini["created_at"] and ini["updated_at"]
    calc = ini["calculo"]
    assert calc["horas_mes"] == 0.0 and calc["fte"] == 0.0 and calc["perc_reducao"] is None
    assert calc["fim_janela"] == "2026-06" and calc["saving_janela"] == 6000.0
    assert calc["roi_janela_pct"] is None and calc["payback_meses"] == 0 and calc["se_paga_na_janela"] is True
    lido = get(client, f"/iniciativas/{ini['id']}?referencia=2026-03").json()
    assert lido["calculo"]["status"] == "EM_SAVING" and lido["calculo"]["meses_contados"] == 3
    assert lido["calculo"]["saving_acumulado"] == 3000.0
    lido = get(client, f"/iniciativas/{ini['id']}?referencia=2026-07").json()
    assert lido["calculo"]["status"] == "NOVO_NORMAL" and lido["calculo"]["saving_acumulado"] == 6000.0
    assert get(client, f"/iniciativas/{ini['id']}?referencia=2025-12").json()["calculo"]["status"] == "PLANEJADA"
    assert send(client, "DELETE", f"/iniciativas/{ini['id']}").status_code == 204
    assert send(client, "DELETE", f"/iniciativas/{ini['id']}").status_code == 404
    assert get(client, f"/iniciativas/{ini['id']}").status_code == 404
    assert send(client, "PUT", f"/iniciativas/{ini['id']}", corpo_direto()).status_code == 404


def test_iniciativa_por_tempo_calcula_mvp_e_participantes(client):
    ini = criar_iniciativa(client, corpo_tempo(valor_mensal=999, janela_meses=12))
    assert ini["valor_mensal"] is None and ini["frequencia"] == "DIARIA_UTIL" and ini["janela_meses"] == 12
    part = ini["participantes"][0]
    assert part["id"] and part["perfil_nome"] == "Analista" and part["horas_mes"] == 77.0
    assert part["valor_mensal"] == 6160.0
    calc = ini["calculo"]
    assert calc["valor_mensal"] == 6160.0 and calc["horas_mes"] == 77.0 and calc["fte"] == 0.46
    assert calc["perc_reducao"] == 70.0 and calc["saving_janela"] == 6160.0 * 12


def test_iniciativa_com_dois_perfis_e_delta_negativo(client):
    corpo = corpo_tempo(
        frequencia="mensal",
        participantes=[
            {"perfil_nome": "Analista", "custo_hora": 80, "qtd_pessoas": 2, "horas_antes": 3, "horas_depois": 0},
            {"perfil_nome": "Executivo", "custo_hora": 300, "qtd_pessoas": 1, "horas_antes": 0, "horas_depois": 1},
        ],
    )
    ini = criar_iniciativa(client, corpo)
    assert [p["horas_mes"] for p in ini["participantes"]] == [6.0, -1.0]
    assert [p["valor_mensal"] for p in ini["participantes"]] == [480.0, -300.0]
    assert ini["calculo"]["valor_mensal"] == 180.0 and ini["calculo"]["horas_mes"] == 5.0
    assert ini["calculo"]["perc_reducao"] == 83.33


def test_put_substitui_participantes_e_campos(client):
    fonte = nova_fonte(client)
    ini = criar_iniciativa(client, corpo_tempo())
    antigo = ini["participantes"][0]["id"]
    novo = corpo_tempo(
        titulo="Novo título",
        frequencia="SEMANAL",
        fonte_id=fonte["id"],
        janela_meses=3,
        mes_encerramento="2026-02",
        investimento_reais=1000,
        investimento_horas=10,
        investimento_custo_hora=50,
        participantes=[
            {"perfil_nome": "A", "custo_hora": 100, "qtd_pessoas": 2, "horas_antes": 2, "horas_depois": 1},
            {"perfil_nome": "B", "custo_hora": 10, "qtd_pessoas": 1, "horas_antes": 1, "horas_depois": 0},
        ],
    )
    r = send(client, "PUT", f"/iniciativas/{ini['id']}", novo)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["id"] == ini["id"] and corpo["titulo"] == "Novo título" and corpo["fonte_nome"] == fonte["nome"]
    assert [p["perfil_nome"] for p in corpo["participantes"]] == ["A", "B"]
    assert antigo not in [p["id"] for p in corpo["participantes"]]
    assert corpo["calculo"]["investimento_total"] == 1500.0 and corpo["calculo"]["meses_janela"] == 2
    assert corpo["mes_encerramento"] == "2026-02"
    lido = get(client, f"/iniciativas/{ini['id']}").json()
    assert len(lido["participantes"]) == 2
    # troca de modo: de POR_TEMPO para DIRETO_REAIS limpa participantes e frequência
    r = send(client, "PUT", f"/iniciativas/{ini['id']}", corpo_direto(valor=250))
    assert r.status_code == 200
    assert r.json()["participantes"] == [] and r.json()["frequencia"] is None and r.json()["valor_mensal"] == 250.0
    assert r.json()["mes_encerramento"] is None and r.json()["fonte_id"] is None
    assert len(get(client, "/iniciativas").json()) == 1


def test_iniciativas_listagem_filtros_e_ordem(client):
    criar_iniciativa(client, corpo_direto("B", mes_inicio="2026-01"))
    criar_iniciativa(client, corpo_direto("A", mes_inicio="2026-01"))
    criar_iniciativa(client, corpo_direto("C", mes_inicio="2026-04", tipo="MELHORIA"))
    criar_iniciativa(client, corpo_tempo("D", mes_inicio="2025-01"))
    assert [i["titulo"] for i in get(client, "/iniciativas?referencia=2026-05").json()] == ["C", "A", "B", "D"]
    assert [i["titulo"] for i in get(client, "/iniciativas?tipo=melhoria").json()] == ["C"]
    assert [i["titulo"] for i in get(client, "/iniciativas?tipo=AUTOMACAO").json()] == ["D"]
    por_status = {
        s: [i["titulo"] for i in get(client, f"/iniciativas?status={s}&referencia=2026-05").json()]
        for s in ("PLANEJADA", "EM_SAVING", "NOVO_NORMAL", "ENCERRADA")
    }
    assert por_status == {"PLANEJADA": [], "EM_SAVING": ["C", "A", "B"], "NOVO_NORMAL": ["D"], "ENCERRADA": []}
    assert [i["titulo"] for i in get(client, "/iniciativas?status=planejada&referencia=2026-02").json()] == ["C"]
    assert get(client, "/iniciativas?tipo=x").status_code == 422
    assert get(client, "/iniciativas?status=x").status_code == 422
    assert get(client, "/iniciativas?referencia=2026-13").status_code == 422
    assert get(client, f"/iniciativas/{uuid4()}").status_code == 404
    assert get(client, f"/iniciativas/{uuid4()}?referencia=nope").status_code == 422
    # default de referência é o mês atual: iniciativa de 2026-01 com janela de 6 meses já não está em saving
    # em qualquer data posterior a 2026-06; o campo status sempre existe
    assert all("status" in i["calculo"] for i in get(client, "/iniciativas").json())


def test_iniciativa_validacoes_422(client):
    base = corpo_direto()
    tempo = corpo_tempo()
    um = tempo["participantes"][0]
    casos = [
        {k: v for k, v in base.items() if k != "valor_mensal"},
        {**base, "valor_mensal": -1},
        {**base, "participantes": [um]},
        {**tempo, "frequencia": None},
        {**tempo, "participantes": []},
        {**tempo, "participantes": [um] * 21},
        {**base, "janela_meses": 0},
        {**base, "janela_meses": 61},
        {**base, "mes_encerramento": "2025-12"},
        {**base, "mes_inicio": "2026-1"},
        {**base, "tipo": "OUTRO"},
        {**base, "modo_calculo": "OUTRO"},
        {**tempo, "frequencia": "ANUAL"},
        {**base, "titulo": ""},
        {**base, "titulo": "x" * 161},
        {**base, "investimento_reais": -1},
        {**base, "investimento_horas": -1},
        {**base, "investimento_custo_hora": -1},
        {**base, "tenant_id": str(TENANT_B)},
        {**tempo, "participantes": [{**um, "qtd_pessoas": 0}]},
        {**tempo, "participantes": [{**um, "horas_antes": -1}]},
        {**tempo, "participantes": [{**um, "horas_depois": -1}]},
        {**tempo, "participantes": [{**um, "custo_hora": -1}]},
        {**tempo, "participantes": [{**um, "perfil_nome": ""}]},
        {**tempo, "participantes": [{**um, "extra": 1}]},
    ]
    for ruim in casos:
        assert send(client, "POST", "/iniciativas", ruim).status_code == 422, ruim
    assert get(client, "/iniciativas").json() == []
    # exatamente 20 participantes é aceito
    assert send(client, "POST", "/iniciativas", {**tempo, "participantes": [um] * 20}).status_code == 201
    # encerramento igual ao início também
    assert send(client, "POST", "/iniciativas", {**base, "mes_encerramento": "2026-01"}).status_code == 201
    assert send(client, "PUT", f"/iniciativas/{uuid4()}", {**base, "janela_meses": 0}).status_code == 422


# --- simulação ------------------------------------------------------------------------------------------------------


def test_simular_nao_grava_e_ignora_fonte(client):
    corpo = corpo_tempo(fonte_id=str(uuid4()), investimento_reais=5000)
    r = send(client, "POST", "/simular?referencia=2026-02", corpo)
    assert r.status_code == 200, r.text
    corpo_r = r.json()
    assert corpo_r["participantes"] == [{"horas_mes": 77.0, "valor_mensal": 6160.0}]
    calc = corpo_r["calculo"]
    assert calc["valor_mensal"] == 6160.0 and calc["fte"] == 0.46 and calc["status"] == "EM_SAVING"
    assert calc["fim_janela"] == "2026-06" and calc["saving_janela"] == 36960.0
    assert calc["payback_meses"] == 1 and calc["roi_janela_pct"] == 639.2 and calc["se_paga_na_janela"] is True
    assert get(client, "/iniciativas").json() == []
    assert send(client, "POST", "/simular", {**corpo, "participantes": []}).status_code == 422
    assert send(client, "POST", "/simular?referencia=zzz", corpo).status_code == 422
    direto = send(client, "POST", "/simular", corpo_direto(valor=10)).json()
    assert direto["participantes"] == [] and direto["calculo"]["valor_mensal"] == 10.0


def test_simular_exige_apenas_leitura(client, grants):
    grants[TENANT_A] = {"access", "read"}
    r = send(client, "POST", "/simular?referencia=2026-02", corpo_direto())
    assert r.status_code == 200


# --- dashboard ------------------------------------------------------------------------------------------------------


def montar_cenario(client):
    fabric = nova_fonte(client, "Fabric", metrica_nome="Usuários ativos")
    aws = nova_fonte(client, "AWS")
    nova_fonte(client, "Inativa")
    send(client, "PATCH", f"/fontes/{get(client, '/fontes').json()[2]['id']}", {"ativo": False})
    nova_fatura(client, fabric, "2026-01", 900, valor_orcado=1000, metrica_valor=300)
    nova_fatura(client, fabric, "2026-02", 1100, valor_orcado=1000, metrica_valor=0)
    nova_fatura(client, aws, "2026-02", 400)
    direto = criar_iniciativa(
        client,
        corpo_direto("Contrato", 1000, mes_inicio="2026-01", fonte_id=fabric["id"], investimento_reais=2000),
    )
    horas = criar_iniciativa(client, corpo_tempo("Automação", mes_inicio="2026-03", janela_meses=2))
    antiga = criar_iniciativa(client, corpo_direto("Antiga", 500, mes_inicio="2025-01", tipo="MELHORIA"))
    encerrada = criar_iniciativa(
        client, corpo_direto("Encerrada", 100, mes_inicio="2026-01", mes_encerramento="2026-02", tipo="MELHORIA")
    )
    return fabric, aws, direto, horas, antiga, encerrada


def test_dashboard_kpis_serie_e_fontes(client):
    fabric, aws, direto, horas, antiga, encerrada = montar_cenario(client)
    r = get(client, "/dashboard?de=2026-01&ate=2026-06&referencia=2026-04")
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["de"], d["ate"], d["referencia"]) == ("2026-01", "2026-06", "2026-04")
    assert d["janela_padrao"] == 6 and d["horas_fte_mes"] == 168
    # série
    serie = d["serie"]
    assert [s["competencia"] for s in serie] == [f"2026-0{n}" for n in range(1, 7)]
    assert [s["saving_direto"] for s in serie] == [1100.0, 1100.0, 1000.0, 1000.0, 1000.0, 1000.0]
    assert [s["saving_horas"] for s in serie] == [0.0, 0.0, 6160.0, 6160.0, 0.0, 0.0]
    assert [s["saving_total"] for s in serie] == [1100.0, 1100.0, 7160.0, 7160.0, 1000.0, 1000.0]
    assert [s["projetado"] for s in serie] == [False, False, False, False, True, True]
    assert (serie[0]["orcado"], serie[0]["realizado"], serie[0]["variacao"]) == (1000.0, 900.0, 100.0)
    assert (serie[1]["orcado"], serie[1]["realizado"], serie[1]["variacao"]) == (1000.0, 1500.0, -500.0)
    assert (serie[2]["orcado"], serie[2]["realizado"], serie[2]["variacao"]) == (None, None, None)
    # kpis
    k = d["kpis"]
    assert k["saving_realizado"] == 1100 + 1100 + 7160 + 7160
    assert k["saving_projetado"] == 2000.0
    # em curso em 2026-04: Contrato (jan..jun) e Automação (mar..abr)
    assert k["saving_direto_em_curso"] == 1000.0 and k["saving_horas_em_curso"] == 6160.0
    assert k["saving_mensal_em_curso"] == 7160.0
    assert k["horas_mes_liberadas"] == 77.0 and k["fte_liberado"] == 0.46
    assert k["novo_normal_mensal"] == 500.0  # Antiga; encerrada não conta
    assert k["investimento_total"] == 2000.0
    assert k["saving_janela_total"] == 6000 + 12320 + 3000 + 200
    assert k["roi_pct"] == round((k["saving_janela_total"] - 2000) / 2000 * 100, 1)
    assert k["iniciativas_por_status"] == {"PLANEJADA": 0, "EM_SAVING": 2, "NOVO_NORMAL": 1, "ENCERRADA": 1}
    # por tipo
    tipos = {t["tipo"]: t for t in d["por_tipo"]}
    assert list(tipos) == ["MELHORIA", "AUTOMACAO", "OTIMIZACAO_CUSTO"]
    assert tipos["OTIMIZACAO_CUSTO"]["quantidade"] == 1 and tipos["OTIMIZACAO_CUSTO"]["saving_periodo"] == 6000.0
    assert tipos["AUTOMACAO"]["saving_periodo"] == 12320.0
    assert tipos["MELHORIA"]["quantidade"] == 2 and tipos["MELHORIA"]["saving_periodo"] == 200.0
    # fontes (a inativa sem faturas não aparece)
    fontes = {f["nome"]: f for f in d["fontes"]}
    assert set(fontes) == {"Fabric", "AWS"}
    fb = fontes["Fabric"]
    assert fb["orcado_periodo"] == 2000.0 and fb["realizado_periodo"] == 2000.0 and fb["variacao_periodo"] == 0.0
    assert fb["saving_iniciativas_mensal"] == 1000.0 and fb["metrica_nome"] == "Usuários ativos"
    assert len(fb["serie"]) == 6
    assert (fb["serie"][0]["custo_unitario"], fb["serie"][1]["custo_unitario"]) == (3.0, None)
    assert fb["serie"][2]["realizado"] is None
    assert fontes["AWS"]["orcado_periodo"] is None and fontes["AWS"]["realizado_periodo"] == 400.0
    assert fontes["AWS"]["variacao_periodo"] is None and fontes["AWS"]["saving_iniciativas_mensal"] == 0.0
    # iniciativas: saving_periodo DESC, título
    assert [i["titulo"] for i in d["iniciativas"]] == ["Automação", "Contrato", "Encerrada", "Antiga"]
    auto = d["iniciativas"][0]
    assert auto["status"] == "EM_SAVING" and auto["saving_periodo"] == 12320.0 and auto["horas_mes"] == 77.0
    assert auto["fim_janela"] == "2026-04" and auto["mes_inicio"] == "2026-03"
    assert auto["payback_meses"] == 0 and auto["se_paga_na_janela"] is True
    contrato = d["iniciativas"][1]
    assert contrato["investimento_total"] == 2000.0 and contrato["payback_meses"] == 2
    assert contrato["roi_janela_pct"] == 200.0


def test_dashboard_fatura_nao_soma_saving_e_defaults(client):
    fonte = nova_fonte(client)
    nova_fatura(client, fonte, "2026-01", 100, valor_orcado=5000)
    d = get(client, "/dashboard?referencia=2026-05").json()
    assert (d["de"], d["ate"], d["referencia"]) == ("2026-01", "2026-12", "2026-05")
    assert len(d["serie"]) == 12 and d["kpis"]["saving_realizado"] == 0.0 and d["kpis"]["saving_projetado"] == 0.0
    assert d["serie"][0]["variacao"] == 4900.0
    assert d["kpis"]["roi_pct"] is None and d["kpis"]["iniciativas_por_status"]["EM_SAVING"] == 0
    assert [t["quantidade"] for t in d["por_tipo"]] == [0, 0, 0] and d["iniciativas"] == []
    sem_nada = get(client, "/dashboard", TENANT_B)
    assert sem_nada.status_code == 200 and sem_nada.json()["fontes"] == []
    # somente "de": ate = dezembro do mesmo ano
    assert get(client, "/dashboard?de=2025-06&referencia=2026-05").json()["ate"] == "2025-12"


def test_dashboard_validacoes(client):
    assert get(client, "/dashboard?de=2026-05&ate=2026-04").status_code == 422
    assert get(client, "/dashboard?de=2026-01&ate=2028-12").status_code == 200  # 36 meses
    assert get(client, "/dashboard?de=2026-01&ate=2029-01").status_code == 422  # 37 meses
    assert get(client, "/dashboard?de=x").status_code == 422
    assert get(client, "/dashboard?referencia=2026").status_code == 422


# --- isolamento e permissões ----------------------------------------------------------------------------------------


def test_isolamento_entre_tenants(client):
    fonte = nova_fonte(client, "Fabric")
    fatura = nova_fatura(client, fonte)
    perfil = send(client, "POST", "/perfis", {"nome": "Analista", "custo_hora": 80}).json()
    ini = criar_iniciativa(client, corpo_direto(fonte_id=fonte["id"]))
    for listagem in ("/perfis", "/fontes", "/faturas", "/iniciativas"):
        assert get(client, listagem, TENANT_B).json() == []
    assert get(client, f"/iniciativas/{ini['id']}", TENANT_B).status_code == 404
    assert send(client, "PUT", f"/iniciativas/{ini['id']}", corpo_direto("X"), TENANT_B).status_code == 404
    assert send(client, "DELETE", f"/iniciativas/{ini['id']}", tenant=TENANT_B).status_code == 404
    assert send(client, "PATCH", f"/fontes/{fonte['id']}", {"nome": "X"}, TENANT_B).status_code == 404
    assert send(client, "DELETE", f"/fontes/{fonte['id']}", tenant=TENANT_B).status_code == 404
    assert send(client, "PATCH", f"/faturas/{fatura['id']}", {"valor_realizado": 1}, TENANT_B).status_code == 404
    assert send(client, "DELETE", f"/faturas/{fatura['id']}", tenant=TENANT_B).status_code == 404
    assert send(client, "PATCH", f"/perfis/{perfil['id']}", {"ativo": False}, TENANT_B).status_code == 404
    assert send(client, "DELETE", f"/perfis/{perfil['id']}", tenant=TENANT_B).status_code == 404
    # B não vincula fonte de A, nem lança fatura nela
    assert send(client, "POST", "/iniciativas", corpo_direto(fonte_id=fonte["id"]), TENANT_B).status_code == 404
    corpo = {"fonte_id": fonte["id"], "competencia": "2026-05", "valor_realizado": 1}
    assert send(client, "POST", "/faturas", corpo, TENANT_B).status_code == 404
    mine = criar_iniciativa(client, corpo_direto("Minha B"), TENANT_B)
    assert (
        send(client, "PUT", f"/iniciativas/{mine['id']}", corpo_direto(fonte_id=fonte["id"]), TENANT_B).status_code
        == 404
    )
    d = get(client, "/dashboard?de=2026-01&ate=2026-12", TENANT_B).json()
    assert [i["titulo"] for i in d["iniciativas"]] == ["Minha B"] and d["fontes"] == []
    # tudo de A permanece intacto
    assert get(client, f"/iniciativas/{ini['id']}").status_code == 200
    assert len(get(client, "/faturas").json()) == 1 and len(get(client, "/perfis").json()) == 1
    # B pode usar os mesmos nomes
    assert send(client, "POST", "/fontes", {"nome": "Fabric"}, TENANT_B).status_code == 201


def test_leitor_nao_escreve_mas_le(client, grants):
    fonte = nova_fonte(client)
    fatura = nova_fatura(client, fonte)
    perfil = send(client, "POST", "/perfis", {"nome": "Analista", "custo_hora": 80}).json()
    ini = criar_iniciativa(client, corpo_direto())
    grants[TENANT_A] = {"access", "read"}
    escritas = [
        ("POST", "/perfis", {"nome": "X", "custo_hora": 1}),
        ("PATCH", f"/perfis/{perfil['id']}", {"ativo": False}),
        ("DELETE", f"/perfis/{perfil['id']}", None),
        ("POST", "/fontes", {"nome": "X"}),
        ("PATCH", f"/fontes/{fonte['id']}", {"nome": "Y"}),
        ("DELETE", f"/fontes/{fonte['id']}", None),
        ("POST", "/faturas", {"fonte_id": fonte["id"], "competencia": "2026-09", "valor_realizado": 1}),
        ("PATCH", f"/faturas/{fatura['id']}", {"valor_realizado": 2}),
        ("DELETE", f"/faturas/{fatura['id']}", None),
        ("POST", "/iniciativas", corpo_direto("Z")),
        ("PUT", f"/iniciativas/{ini['id']}", corpo_direto("Z")),
        ("DELETE", f"/iniciativas/{ini['id']}", None),
    ]
    for metodo, caminho, corpo in escritas:
        r = send(client, metodo, caminho, corpo)
        assert r.status_code == 403, (metodo, caminho, r.text)
    for caminho in ("/perfis", "/fontes", "/faturas", "/iniciativas", f"/iniciativas/{ini['id']}", "/dashboard"):
        assert get(client, caminho).status_code == 200, caminho
    grants[TENANT_A] = set()
    assert get(client, "/dashboard").status_code == 403
    assert send(client, "POST", "/simular", corpo_direto()).status_code == 403


def test_escrita_exige_csrf(client):
    r = client.post(P + "/perfis", json={"nome": "x", "custo_hora": 1}, headers={"X-Tenant-ID": str(TENANT_A)})
    assert r.status_code == 403


# --- vínculo com despesas (Fase 4) ------------------------------------------------------------------------------------


def nova_despesa(c, nome="Licença", tenant=TENANT_A, **extra):
    corpo = {"nome": nome, "categoria": "SaaS & Ferramentas", "tipo_custo": "RECORRENTE_MENSAL", "valor": 1000}
    corpo.update(extra)
    r = c.post("/api/v1/despesas", json=corpo, headers=h(tenant, True))
    assert r.status_code == 201, r.text
    return r.json()


def test_iniciativa_sem_despesa_tem_campos_de_vinculo_vazios(client):
    ini = criar_iniciativa(client, corpo_direto())
    assert ini["despesa_id"] is None and ini["despesa_nome"] is None and ini["conversao_despesa"] is False
    assert send(client, "POST", "/iniciativas", corpo_direto(conversao_despesa=True)).status_code == 422


def test_iniciativa_manual_com_despesa_id(client):
    despesa = nova_despesa(client)
    ini = criar_iniciativa(client, corpo_direto(despesa_id=despesa["id"]))
    assert ini["despesa_id"] == despesa["id"] and ini["despesa_nome"] == "Licença"
    assert ini["conversao_despesa"] is False
    listada = get(client, "/iniciativas?referencia=2026-02").json()[0]
    assert listada["despesa_nome"] == "Licença"
    # despesa inexistente ou de outro tenant -> 404 (criação e edição)
    assert send(client, "POST", "/iniciativas", corpo_direto(despesa_id=str(uuid4()))).status_code == 404
    assert send(client, "POST", "/iniciativas", corpo_direto(despesa_id=despesa["id"]), TENANT_B).status_code == 404
    assert send(client, "PUT", f"/iniciativas/{ini['id']}", corpo_direto(despesa_id=str(uuid4()))).status_code == 404
    # simulação ignora despesa_id
    assert send(client, "POST", "/simular", corpo_direto(despesa_id=str(uuid4()))).status_code == 200
    # a iniciativa manual pode ser removida normalmente
    assert send(client, "DELETE", f"/iniciativas/{ini['id']}").status_code == 204


def test_fonte_com_despesa_nao_pode_ser_excluida(client):
    fonte = nova_fonte(client, "Fabric")
    despesa = nova_despesa(client, fonte_id=fonte["id"])
    r = send(client, "DELETE", f"/fontes/{fonte['id']}")
    assert r.status_code == 409 and "detail" in r.json()
    client.delete(f"/api/v1/despesas/{despesa['id']}", headers=h(TENANT_A, True))
    assert send(client, "DELETE", f"/fontes/{fonte['id']}").status_code == 204


def test_iniciativa_de_conversao_nao_pode_ser_excluida(client):
    despesa = nova_despesa(client)
    r = client.post(f"/api/v1/despesas/{despesa['id']}/cancelar", json={"mes": "2026-02"}, headers=h(TENANT_A, True))
    assert r.status_code == 200, r.text
    ini = r.json()["iniciativa"]
    lida = get(client, f"/iniciativas/{ini['id']}").json()
    assert lida["conversao_despesa"] is True and lida["despesa_nome"] == "Licença"
    excluir = send(client, "DELETE", f"/iniciativas/{ini['id']}")
    assert excluir.status_code == 409 and "detail" in excluir.json()
    # despesa_id não pode ser trocado nem removido no PUT
    assert send(client, "PUT", f"/iniciativas/{ini['id']}", corpo_direto(valor=1000)).status_code == 422
    outra = nova_despesa(client, "Outra")
    assert send(client, "PUT", f"/iniciativas/{ini['id']}", corpo_direto(despesa_id=outra["id"])).status_code == 422
    ok = send(client, "PUT", f"/iniciativas/{ini['id']}", corpo_direto(despesa_id=despesa["id"], janela_meses=3))
    assert ok.status_code == 200 and ok.json()["janela_meses"] == 3 and ok.json()["conversao_despesa"] is True
    # aparece no dashboard do FinOps como saving
    dash = get(client, "/dashboard?de=2026-01&ate=2026-06&referencia=2026-03").json()
    assert dash["kpis"]["saving_direto_em_curso"] == 1000.0

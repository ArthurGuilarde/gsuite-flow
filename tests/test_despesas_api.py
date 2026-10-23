from datetime import date, timedelta
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
P = "/api/v1/despesas"
F = "/api/v1/finops"
REF = "referencia=2026-05&hoje=2026-05-10"


@pytest.fixture
def grants():
    return {TENANT_A: {"access", "read", "write"}, TENANT_B: {"access", "read", "write"}}


@pytest.fixture
def client(monkeypatch, tmp_path, grants):
    engine = create_engine(f"sqlite:///{tmp_path / 'desp.sqlite3'}", connect_args={"check_same_thread": False})

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


def get(c, path, tenant=TENANT_A, base=P):
    return c.get(base + path, headers=h(tenant))


def send(c, method, path, body=None, tenant=TENANT_A, base=P):
    return c.request(method, base + path, json=body, headers=h(tenant, True))


def nova(c, nome="Licença X", tenant=TENANT_A, **extra):
    corpo = {"nome": nome, "categoria": "SaaS & Ferramentas", "tipo_custo": "RECORRENTE_MENSAL", "valor": 1000}
    corpo.update(extra)
    r = send(c, "POST", "", corpo, tenant)
    assert r.status_code == 201, r.text
    return r.json()


def nova_fonte(c, nome="Fabric", tenant=TENANT_A):
    r = send(c, "POST", "/fontes", {"nome": nome}, tenant, base=F)
    assert r.status_code == 201, r.text
    return r.json()


def nova_fatura(c, fonte, competencia, realizado, tenant=TENANT_A):
    corpo = {"fonte_id": fonte["id"], "competencia": competencia, "valor_realizado": realizado}
    r = send(c, "POST", "/faturas", corpo, tenant, base=F)
    assert r.status_code == 201, r.text
    return r.json()


def iniciativas_finops(c, tenant=TENANT_A):
    return get(c, "/iniciativas?referencia=2026-05", tenant, base=F).json()


# --- CRUD -----------------------------------------------------------------------------------------------------------


def test_despesa_crud_e_defaults(client):
    d = nova(client, fornecedor="Acme", responsavel="Ana", observacoes="obs", data_renovacao="2026-06-01")
    assert d["status_auditoria"] == "EM_REVISAO" and d["valor"] == 1000.0 and d["valor_anterior"] is None
    assert d["origem_custo"] == "CONTRATO" and d["custo_mensal_considerado"] == 1000.0
    assert d["custo_anual"] == 12000.0 and d["competencia_fatura"] is None and d["mes_acao"] is None
    assert d["iniciativas"] == [] and d["fonte_id"] is None and d["fonte_nome"] is None
    assert d["created_at"] and d["updated_at"] and "tenant_id" not in d
    pontual = nova(client, "Treinamento", tipo_custo="pontual", valor=300, data_inicio="2026-05-02", categoria="Outros")
    assert pontual["tipo_custo"] == "PONTUAL" and pontual["custo_anual"] == 300.0
    assert pontual["custo_mensal_considerado"] == 0.0
    lista = get(client, f"?{REF}").json()
    assert [x["nome"] for x in lista] == ["Licença X", "Treinamento"]
    assert lista[0]["dias_para_renovacao"] == 22
    assert [x["nome"] for x in get(client, "?status=em_revisao").json()] == ["Licença X", "Treinamento"]
    assert [x["nome"] for x in get(client, "?categoria=Outros").json()] == ["Treinamento"]
    assert get(client, "?status=VALIDADO").json() == []
    p = send(
        client,
        "PATCH",
        f"/{d['id']}",
        {"valor": 1500, "status_auditoria": "validado", "fornecedor": None, "responsavel": "Bia"},
    )
    assert p.status_code == 200, p.text
    corpo = p.json()
    assert corpo["valor"] == 1500.0 and corpo["status_auditoria"] == "VALIDADO" and corpo["fornecedor"] is None
    assert corpo["responsavel"] == "Bia" and corpo["nome"] == "Licença X"
    lido = get(client, f"/{d['id']}?{REF}")
    assert lido.status_code == 200 and lido.json()["dias_para_renovacao"] == 22
    assert send(client, "DELETE", f"/{d['id']}").status_code == 204
    assert send(client, "DELETE", f"/{d['id']}").status_code == 404
    assert get(client, f"/{d['id']}").status_code == 404
    assert send(client, "PATCH", f"/{uuid4()}", {"valor": 1}).status_code == 404


def test_despesa_validacoes_422(client):
    base = {"nome": "X", "categoria": "Outros", "tipo_custo": "PONTUAL", "valor": 1}
    ruins = [
        {**base, "nome": ""},
        {**base, "nome": "  "},
        {**base, "nome": "x" * 161},
        {**base, "categoria": ""},
        {**base, "categoria": "x" * 61},
        {**base, "tipo_custo": "ANUAL"},
        {**base, "valor": -1},
        {**base, "valor": 1.234},
        {**base, "status_auditoria": "CANCELADO"},
        {**base, "status_auditoria": "RENEGOCIADO"},
        {**base, "status_auditoria": "OUTRO"},
        {**base, "data_inicio": "2026-13-01"},
        {**base, "tenant_id": str(TENANT_B)},
        {k: v for k, v in base.items() if k != "valor"},
    ]
    for ruim in ruins:
        assert send(client, "POST", "", ruim).status_code == 422, ruim
    d = nova(client)
    for ruim in (
        {"status_auditoria": "CANCELADO"},
        {"status_auditoria": "RENEGOCIADO"},
        {"nome": None},
        {"valor": None},
    ):
        assert send(client, "PATCH", f"/{d['id']}", ruim).status_code == 422, ruim
    assert get(client, "?status=x").status_code == 422
    assert get(client, "?referencia=2026-13").status_code == 422
    assert get(client, "?hoje=10/05/2026").status_code == 422
    assert get(client, f"/{d['id']}?referencia=zzz").status_code == 422
    assert get(client, "/dashboard?hoje=x").status_code == 422
    assert send(client, "POST", "/x/cancelar", {}).status_code == 422


# --- custo considerado e fatura -------------------------------------------------------------------------------------


def test_custo_considerado_vem_da_fatura(client):
    fonte = nova_fonte(client)
    d = nova(client, valor=1000, fonte_id=fonte["id"])
    assert d["fonte_nome"] == "Fabric" and d["origem_custo"] == "CONTRATO"
    nova_fatura(client, fonte, "2026-03", 1400)
    # sem fatura em 2026-05: usa a última anterior
    v = get(client, f"/{d['id']}?{REF}").json()
    assert v["origem_custo"] == "FATURA" and v["custo_mensal_considerado"] == 1400.0
    assert v["competencia_fatura"] == "2026-03" and v["custo_anual"] == 16800.0
    nova_fatura(client, fonte, "2026-05", 1700)
    v = get(client, f"/{d['id']}?{REF}").json()
    assert v["custo_mensal_considerado"] == 1700.0 and v["competencia_fatura"] == "2026-05"
    # mês anterior à primeira fatura: contrato
    v = get(client, f"/{d['id']}?referencia=2026-01&hoje=2026-01-01").json()
    assert v["origem_custo"] == "CONTRATO" and v["custo_mensal_considerado"] == 1000.0


def test_fonte_de_outro_tenant_e_conflito_de_exclusao(client):
    fonte_a = nova_fonte(client, "Fabric")
    fonte_b = nova_fonte(client, "Outra", TENANT_B)
    corpo = {"nome": "X", "categoria": "Outros", "tipo_custo": "PONTUAL", "valor": 1, "fonte_id": fonte_a["id"]}
    assert send(client, "POST", "", corpo, TENANT_B).status_code == 404
    d = nova(client, fonte_id=fonte_a["id"])
    assert send(client, "PATCH", f"/{d['id']}", {"fonte_id": fonte_b["id"]}).status_code == 404
    assert send(client, "PATCH", f"/{d['id']}", {"fonte_id": str(uuid4())}).status_code == 404
    # fonte com despesa: 409; desvinculando, pode excluir
    assert send(client, "DELETE", f"/fontes/{fonte_a['id']}", base=F).status_code == 409
    assert send(client, "PATCH", f"/{d['id']}", {"fonte_id": None}).json()["fonte_id"] is None
    assert send(client, "DELETE", f"/fontes/{fonte_a['id']}", base=F).status_code == 204


# --- cancelar -------------------------------------------------------------------------------------------------------


def test_cancelar_cria_iniciativa_e_reverter_apaga(client):
    fonte = nova_fonte(client)
    d = nova(client, "Contrato Cloud", valor=2000, fonte_id=fonte["id"])
    r = send(client, "POST", f"/{d['id']}/cancelar", {"mes": "2026-05", "janela_meses": 4, "observacao": "Sem uso"})
    assert r.status_code == 200, r.text
    corpo = r.json()
    desp, ini = corpo["despesa"], corpo["iniciativa"]
    assert desp["status_auditoria"] == "CANCELADO" and desp["mes_acao"] == "2026-05"
    assert ini["titulo"] == "Cancelamento: Contrato Cloud" and ini["descricao"] == "Sem uso"
    assert ini["tipo"] == "OTIMIZACAO_CUSTO" and ini["modo_calculo"] == "DIRETO_REAIS"
    assert ini["valor_mensal"] == 2000.0 and ini["mes_inicio"] == "2026-05" and ini["janela_meses"] == 4
    assert ini["fonte_id"] == fonte["id"] and ini["fonte_nome"] == "Fabric"
    assert ini["despesa_id"] == d["id"] and ini["despesa_nome"] == "Contrato Cloud"
    assert ini["conversao_despesa"] is True
    assert [i["id"] for i in desp["iniciativas"]] == [ini["id"]] and desp["iniciativas"][0]["conversao_despesa"] is True
    # aparece no FinOps com o vínculo
    lista = iniciativas_finops(client)
    assert [i["id"] for i in lista] == [ini["id"]] and lista[0]["despesa_nome"] == "Contrato Cloud"
    # a despesa cancelada custa zero a partir do mês da ação; antes ainda custava
    assert get(client, f"/{d['id']}?referencia=2026-05&hoje=2026-05-10").json()["custo_mensal_considerado"] == 0.0
    # regras: já cancelada, patch, delete, exclusão da iniciativa de conversão
    assert send(client, "POST", f"/{d['id']}/cancelar", {}).status_code == 409
    assert send(client, "POST", f"/{d['id']}/renegociar", {"novo_valor": 1}).status_code == 409
    assert send(client, "PATCH", f"/{d['id']}", {"status_auditoria": "VALIDADO"}).status_code == 409
    assert send(client, "PATCH", f"/{d['id']}", {"valor": 5}).status_code == 409
    assert send(client, "PATCH", f"/{d['id']}", {"tipo_custo": "PONTUAL"}).status_code == 409
    assert send(client, "PATCH", f"/{d['id']}", {"valor": 2000, "responsavel": "Zé"}).status_code == 200
    assert send(client, "DELETE", f"/{d['id']}").status_code == 409
    assert send(client, "DELETE", f"/iniciativas/{ini['id']}", base=F).status_code == 409
    # PUT da iniciativa de conversão: janela editável, despesa_id fixo
    corpo_put = {
        "titulo": "Cancelamento: Contrato Cloud",
        "tipo": "OTIMIZACAO_CUSTO",
        "modo_calculo": "DIRETO_REAIS",
        "valor_mensal": 2000,
        "mes_inicio": "2026-05",
        "janela_meses": 12,
        "despesa_id": d["id"],
    }
    ok = send(client, "PUT", f"/iniciativas/{ini['id']}", corpo_put, base=F)
    assert ok.status_code == 200 and ok.json()["janela_meses"] == 12 and ok.json()["conversao_despesa"] is True
    assert (
        send(client, "PUT", f"/iniciativas/{ini['id']}", {**corpo_put, "despesa_id": None}, base=F).status_code == 422
    )
    outra = nova(client, "Outra")
    assert (
        send(client, "PUT", f"/iniciativas/{ini['id']}", {**corpo_put, "despesa_id": outra["id"]}, base=F).status_code
        == 422
    )
    # reverter
    rev = send(client, "POST", f"/{d['id']}/reverter", {"novo_status": "desperdicio"})
    assert rev.status_code == 200, rev.text
    v = rev.json()
    assert v["status_auditoria"] == "DESPERDICIO" and v["mes_acao"] is None and v["valor_anterior"] is None
    assert v["valor"] == 2000.0 and v["iniciativas"] == []
    assert iniciativas_finops(client) == []
    assert send(client, "POST", f"/{d['id']}/reverter", {}).status_code == 409
    assert send(client, "DELETE", f"/{d['id']}").status_code == 204


def test_cancelar_defaults_pontual_e_valor_zero(client):
    d = nova(client)
    r = send(client, "POST", f"/{d['id']}/cancelar", None).json()
    hoje = date.today()
    assert r["despesa"]["mes_acao"] == f"{hoje.year:04d}-{hoje.month:02d}"
    assert r["iniciativa"]["janela_meses"] == 6 and r["iniciativa"]["descricao"] is None
    pontual = nova(client, "Pontual", tipo_custo="PONTUAL", valor=500)
    r = send(client, "POST", f"/{pontual['id']}/cancelar", {"mes": "2026-02"}).json()
    assert r["despesa"]["status_auditoria"] == "CANCELADO" and r["iniciativa"] is None
    zero = nova(client, "Zerada", valor=0)
    assert send(client, "POST", f"/{zero['id']}/cancelar", {}).json()["iniciativa"] is None
    assert len(iniciativas_finops(client)) == 1
    # reverter sem iniciativa
    assert send(client, "POST", f"/{pontual['id']}/reverter", None).json()["status_auditoria"] == "EM_REVISAO"
    for ruim in ({"janela_meses": 0}, {"janela_meses": 61}, {"mes": "2026-13"}, {"extra": 1}):
        assert send(client, "POST", f"/{pontual['id']}/cancelar", ruim).status_code == 422, ruim
    assert send(client, "POST", f"/{pontual['id']}/reverter", {"novo_status": "CANCELADO"}).status_code == 422
    assert send(client, "POST", f"/{uuid4()}/cancelar", {}).status_code == 404
    assert send(client, "POST", f"/{uuid4()}/reverter", {}).status_code == 404


# --- renegociar -----------------------------------------------------------------------------------------------------


def test_renegociar_e_reverter_restaura_valor(client):
    d = nova(client, "Telefonia", valor=1000, data_inicio="2026-01-01")
    r = send(client, "POST", f"/{d['id']}/renegociar", {"novo_valor": 700, "mes": "2026-05"})
    assert r.status_code == 200, r.text
    desp, ini = r.json()["despesa"], r.json()["iniciativa"]
    assert desp["status_auditoria"] == "RENEGOCIADO" and desp["valor"] == 700.0 and desp["valor_anterior"] == 1000.0
    assert desp["mes_acao"] == "2026-05"
    assert ini["titulo"] == "Renegociação: Telefonia" and ini["valor_mensal"] == 300.0
    assert ini["janela_meses"] == 6 and ini["conversao_despesa"] is True
    # antes da ação o custo era o anterior; depois, o novo
    assert get(client, f"/{d['id']}?referencia=2026-04").json()["custo_mensal_considerado"] == 1000.0
    assert get(client, f"/{d['id']}?referencia=2026-05").json()["custo_mensal_considerado"] == 700.0
    assert send(client, "PATCH", f"/{d['id']}", {"valor": 600}).status_code == 409
    assert send(client, "POST", f"/{d['id']}/cancelar", {}).status_code == 409
    rev = send(client, "POST", f"/{d['id']}/reverter", {"novo_status": "VALIDADO"}).json()
    assert rev["valor"] == 1000.0 and rev["valor_anterior"] is None and rev["status_auditoria"] == "VALIDADO"
    assert iniciativas_finops(client) == []


def test_renegociar_validacoes(client):
    d = nova(client, valor=1000)
    assert send(client, "POST", f"/{d['id']}/renegociar", {"novo_valor": 1000}).status_code == 422
    assert send(client, "POST", f"/{d['id']}/renegociar", {"novo_valor": 1200}).status_code == 422
    assert send(client, "POST", f"/{d['id']}/renegociar", {"novo_valor": -1}).status_code == 422
    assert send(client, "POST", f"/{d['id']}/renegociar", {}).status_code == 422
    assert send(client, "POST", f"/{d['id']}/renegociar", {"novo_valor": 1, "janela_meses": 0}).status_code == 422
    pontual = nova(client, "P", tipo_custo="PONTUAL", valor=500)
    assert send(client, "POST", f"/{pontual['id']}/renegociar", {"novo_valor": 1}).status_code == 422
    assert send(client, "POST", f"/{uuid4()}/renegociar", {"novo_valor": 1}).status_code == 404
    # renegociar para zero é permitido; economia = valor atual
    r = send(client, "POST", f"/{d['id']}/renegociar", {"novo_valor": 0, "mes": "2026-05", "janela_meses": 3}).json()
    assert r["iniciativa"]["valor_mensal"] == 1000.0 and r["iniciativa"]["janela_meses"] == 3
    assert iniciativas_finops(client)[0]["despesa_id"] == d["id"]


# --- vínculo manual de iniciativa -----------------------------------------------------------------------------------


def corpo_ini(**extra):
    corpo = {
        "titulo": "Otimizar licença",
        "tipo": "OTIMIZACAO_CUSTO",
        "modo_calculo": "DIRETO_REAIS",
        "valor_mensal": 100,
        "mes_inicio": "2026-01",
    }
    corpo.update(extra)
    return corpo


def test_iniciativa_manual_vinculada_bloqueia_exclusao_da_despesa(client):
    d = nova(client)
    r = send(client, "POST", "/iniciativas", corpo_ini(despesa_id=d["id"]), base=F)
    assert r.status_code == 201, r.text
    ini = r.json()
    assert ini["despesa_id"] == d["id"] and ini["despesa_nome"] == "Licença X" and ini["conversao_despesa"] is False
    v = get(client, f"/{d['id']}?{REF}").json()
    assert [(i["id"], i["conversao_despesa"]) for i in v["iniciativas"]] == [(ini["id"], False)]
    assert v["iniciativas"][0]["status"] == "EM_SAVING" and v["iniciativas"][0]["valor_mensal"] == 100.0
    assert send(client, "DELETE", f"/{d['id']}").status_code == 409
    # a iniciativa manual pode ser desvinculada e excluída; despesa liberada
    assert send(client, "PUT", f"/iniciativas/{ini['id']}", corpo_ini(), base=F).json()["despesa_id"] is None
    assert send(client, "DELETE", f"/{d['id']}").status_code == 204
    # simular ignora despesa_id (mesmo inexistente)
    assert send(client, "POST", "/simular", corpo_ini(despesa_id=str(uuid4())), base=F).status_code == 200
    assert send(client, "POST", "/iniciativas", corpo_ini(despesa_id=str(uuid4())), base=F).status_code == 404


def test_reverter_nao_apaga_iniciativa_manual(client):
    d = nova(client)
    manual = send(client, "POST", "/iniciativas", corpo_ini(despesa_id=d["id"]), base=F).json()
    send(client, "POST", f"/{d['id']}/cancelar", {"mes": "2026-05"})
    assert len(iniciativas_finops(client)) == 2
    v = send(client, "POST", f"/{d['id']}/reverter", {}).json()
    assert [i["id"] for i in v["iniciativas"]] == [manual["id"]]
    assert [i["id"] for i in iniciativas_finops(client)] == [manual["id"]]


# --- orçamento ------------------------------------------------------------------------------------------------------


def test_orcamento_upsert_listagem_e_exclusao(client):
    r = send(client, "PUT", "/orcamentos/2026-03", {"valor": 5000, "observacao": "Q1"})
    assert r.status_code == 200, r.text
    assert r.json()["competencia"] == "2026-03" and r.json()["valor"] == 5000.0 and r.json()["observacao"] == "Q1"
    outro = send(client, "PUT", "/orcamentos/2026-03", {"valor": 6000}).json()
    assert outro["id"] == r.json()["id"] and outro["valor"] == 6000.0 and outro["observacao"] is None
    send(client, "PUT", "/orcamentos/2026-01", {"valor": 1})
    send(client, "PUT", "/orcamentos/2027-01", {"valor": 2})
    assert [o["competencia"] for o in get(client, "/orcamentos?ano=2026").json()] == ["2026-01", "2026-03"]
    assert [o["competencia"] for o in get(client, "/orcamentos?ano=2027").json()] == ["2027-01"]
    assert get(client, "/orcamentos?ano=2026", TENANT_B).json() == []
    assert isinstance(get(client, "/orcamentos").json(), list)
    for ruim in ("2026-13", "2026", "abc"):
        assert send(client, "PUT", f"/orcamentos/{ruim}", {"valor": 1}).status_code == 422, ruim
    assert send(client, "PUT", "/orcamentos/2026-05", {"valor": -1}).status_code == 422
    assert send(client, "PUT", "/orcamentos/2026-05", {}).status_code == 422
    assert get(client, "/orcamentos?ano=0").status_code == 422
    assert send(client, "DELETE", "/orcamentos/2026-03").status_code == 204
    assert send(client, "DELETE", "/orcamentos/2026-03").status_code == 404
    assert send(client, "DELETE", "/orcamentos/2026-13").status_code == 422


def test_orcamento_anual_divide_por_12_e_respeita_sobrescrever(client):
    send(client, "PUT", "/orcamentos/2026-02", {"valor": 7})
    r = send(client, "POST", "/orcamentos/anual", {"ano": 2026, "valor_anual": 1000})
    assert r.status_code == 200 and r.json() == {"criados": 11, "atualizados": 0, "ignorados": 1}
    lista = get(client, "/orcamentos?ano=2026").json()
    assert len(lista) == 12 and lista[1]["valor"] == 7.0
    assert lista[0]["valor"] == 83.33 and lista[11]["valor"] == 83.37
    r = send(client, "POST", "/orcamentos/anual", {"ano": 2026, "valor_anual": 1200, "sobrescrever": True})
    assert r.json() == {"criados": 0, "atualizados": 12, "ignorados": 0}
    lista = get(client, "/orcamentos?ano=2026").json()
    assert [o["valor"] for o in lista] == [100.0] * 12
    for ruim in ({"ano": 2026, "valor_anual": -1}, {"ano": 1, "valor_anual": 1}, {"valor_anual": 1}):
        assert send(client, "POST", "/orcamentos/anual", ruim).status_code == 422, ruim


# --- dashboard ------------------------------------------------------------------------------------------------------


def test_dashboard_vazio(client):
    d = get(client, f"/dashboard?{REF}").json()
    assert (d["referencia"], d["hoje"], d["ano"]) == ("2026-05", "2026-05-10", 2026)
    k = d["kpis"]
    assert k["run_rate_mensal"] == 0.0 and k["auditoria_pct"] == 0.0 and k["total_despesas"] == 0
    assert k["orcado_mes"] is None and k["variacao_orcamento"] is None
    assert k["por_status"] == {"EM_REVISAO": 0, "VALIDADO": 0, "DESPERDICIO": 0, "CANCELADO": 0, "RENEGOCIADO": 0}
    assert d["alertas_renovacao"] == [] and d["por_categoria"] == []
    assert [s["status"] for s in d["por_status"]] == [
        "EM_REVISAO",
        "VALIDADO",
        "DESPERDICIO",
        "CANCELADO",
        "RENEGOCIADO",
    ]
    assert len(d["serie"]) == 12 and d["serie"][0]["competencia"] == "2026-01" and d["serie"][0]["orcado"] is None
    assert get(client, "/dashboard").status_code == 200


def montar_cenario(client):
    fonte = nova_fonte(client)
    nova_fatura(client, fonte, "2026-04", 1500)
    nova(
        client,
        "Cloud",
        categoria="Infra",
        valor=1000,
        fonte_id=fonte["id"],
        status_auditoria="VALIDADO",
        data_inicio="2026-01-01",
        data_renovacao="2026-05-20",
    )
    nova(client, "Ferramenta", categoria="SaaS", valor=400, status_auditoria="DESPERDICIO", data_renovacao="2026-06-30")
    ren = nova(client, "Telefonia", categoria="Infra", valor=1000)
    cancel = nova(client, "Antiga", categoria="SaaS", valor=300, data_renovacao="2026-05-12")
    nova(client, "Curso", categoria="Pessoas", tipo_custo="PONTUAL", valor=900, data_inicio="2026-03-10")
    nova(client, "Futuro", categoria="Pessoas", tipo_custo="PONTUAL", valor=100, data_inicio="2026-05-15")
    send(client, "POST", f"/{ren['id']}/renegociar", {"novo_valor": 800, "mes": "2026-03", "janela_meses": 12})
    send(client, "POST", f"/{cancel['id']}/cancelar", {"mes": "2026-04", "janela_meses": 12})
    send(client, "PUT", "/orcamentos/2026-05", {"valor": 3000})
    send(client, "PUT", "/orcamentos/2026-03", {"valor": 3000})


def test_dashboard_kpis_alertas_e_serie(client):
    montar_cenario(client)
    d = get(client, f"/dashboard?{REF}").json()
    k = d["kpis"]
    # Cloud: última fatura (1500); Ferramenta 400; Telefonia 800 (renegociada em 2026-03); Antiga cancelada
    assert k["run_rate_mensal"] == 2700.0 and k["run_rate_anual"] == 32400.0
    assert k["pontuais_ano"] == 1000.0 and k["desperdicio_mensal"] == 400.0
    # saving em 2026-05: Telefonia (200, janela 12 desde mar) e Antiga (300, desde abr)
    assert k["saving_capturado_mensal"] == 500.0 and k["novo_normal_mensal"] == 0.0
    assert k["orcado_mes"] == 3000.0 and k["variacao_orcamento"] == 3000 - (2700 + 100)
    assert k["total_despesas"] == 6 and k["auditoria_pct"] == 66.7  # 4 de 6 já fora de EM_REVISAO
    assert k["por_status"] == {"EM_REVISAO": 2, "VALIDADO": 1, "DESPERDICIO": 1, "CANCELADO": 1, "RENEGOCIADO": 1}
    # alertas: hoje 2026-05-10 -> Cloud (10 dias, URGENTE), Ferramenta (51 dias, ATENCAO); Antiga cancelada ignorada
    alertas = d["alertas_renovacao"]
    assert [(a["nome"], a["dias"], a["nivel"]) for a in alertas] == [
        ("Cloud", 10, "URGENTE"),
        ("Ferramenta", 51, "ATENCAO"),
    ]
    assert alertas[0]["custo_mensal"] == 1500.0 and alertas[0]["status_auditoria"] == "VALIDADO"
    # categorias: sem canceladas; custo DESC
    cats = {c["categoria"]: c for c in d["por_categoria"]}
    assert [c["categoria"] for c in d["por_categoria"]] == ["Infra", "SaaS", "Pessoas"]
    assert cats["Infra"]["quantidade"] == 2 and cats["Infra"]["custo_mensal"] == 2300.0
    assert cats["SaaS"]["quantidade"] == 1 and cats["SaaS"]["custo_mensal"] == 400.0
    assert cats["Pessoas"]["quantidade"] == 2 and cats["Pessoas"]["custo_mensal"] == 0.0
    por_status = {s["status"]: s for s in d["por_status"]}
    assert por_status["CANCELADO"]["quantidade"] == 1 and por_status["CANCELADO"]["custo_mensal"] == 0.0
    assert por_status["RENEGOCIADO"]["custo_mensal"] == 800.0
    # série mensal (só fatura do próprio mês ou contrato)
    serie = {s["competencia"]: s for s in d["serie"]}
    assert len(serie) == 12
    # janeiro: Cloud(1000, início jan) + Ferramenta 400 + Telefonia 1000 + Antiga 300
    assert serie["2026-01"]["recorrente"] == 2700.0 and serie["2026-01"]["pontual"] == 0.0
    # março: Telefonia já 800; pontual Curso 900
    assert serie["2026-03"]["recorrente"] == 2500.0 and serie["2026-03"]["pontual"] == 900.0
    assert serie["2026-03"]["total"] == 3400.0 and serie["2026-03"]["orcado"] == 3000.0
    assert serie["2026-03"]["variacao"] == -400.0
    # abril: Cloud fatura 1500; Antiga cancelada em abril
    assert serie["2026-04"]["recorrente"] == 1500 + 400 + 800
    # maio: Cloud volta ao contrato (sem fatura em maio); pontual Futuro
    assert serie["2026-05"]["recorrente"] == 1000 + 400 + 800 and serie["2026-05"]["pontual"] == 100.0
    assert serie["2026-05"]["variacao"] == 3000 - 2200 - 100
    assert serie["2026-02"]["orcado"] is None and serie["2026-02"]["variacao"] is None


def test_dashboard_orcamento_so_aparece_com_cadastro(client):
    nova(client, valor=100)
    d = get(client, f"/dashboard?{REF}").json()
    assert d["kpis"]["orcado_mes"] is None and d["kpis"]["run_rate_mensal"] == 100.0
    assert all(s["orcado"] is None for s in d["serie"])
    # alerta fora da janela de 60 dias não aparece; 60 dias exatos aparece
    base = date(2026, 5, 10)
    nova(client, "Em 60", data_renovacao=(base + timedelta(days=60)).isoformat())
    nova(client, "Em 61", data_renovacao=(base + timedelta(days=61)).isoformat())
    nova(client, "Ontem", data_renovacao=(base - timedelta(days=1)).isoformat())
    nomes = [a["nome"] for a in get(client, f"/dashboard?{REF}").json()["alertas_renovacao"]]
    assert nomes == ["Em 60"]


# --- isolamento e permissões ----------------------------------------------------------------------------------------


def test_isolamento_entre_tenants(client):
    d = nova(client)
    orc = send(client, "PUT", "/orcamentos/2026-01", {"valor": 10}).json()
    assert get(client, "", TENANT_B).json() == []
    assert get(client, f"/{d['id']}", TENANT_B).status_code == 404
    assert send(client, "PATCH", f"/{d['id']}", {"valor": 1}, TENANT_B).status_code == 404
    assert send(client, "DELETE", f"/{d['id']}", tenant=TENANT_B).status_code == 404
    assert send(client, "POST", f"/{d['id']}/cancelar", {}, TENANT_B).status_code == 404
    assert send(client, "POST", f"/{d['id']}/renegociar", {"novo_valor": 1}, TENANT_B).status_code == 404
    assert send(client, "POST", f"/{d['id']}/reverter", {}, TENANT_B).status_code == 404
    assert get(client, "/orcamentos?ano=2026", TENANT_B).json() == []
    assert send(client, "DELETE", "/orcamentos/2026-01", tenant=TENANT_B).status_code == 404
    assert get(client, f"/dashboard?{REF}", TENANT_B).json()["kpis"]["total_despesas"] == 0
    # B não vincula iniciativa à despesa de A
    corpo = {
        "titulo": "X",
        "tipo": "MELHORIA",
        "modo_calculo": "DIRETO_REAIS",
        "valor_mensal": 1,
        "mes_inicio": "2026-01",
        "despesa_id": d["id"],
    }
    assert send(client, "POST", "/iniciativas", corpo, TENANT_B, base=F).status_code == 404
    mine = send(client, "POST", "/iniciativas", {**corpo, "despesa_id": None}, TENANT_B, base=F).json()
    assert send(client, "PUT", f"/iniciativas/{mine['id']}", corpo, TENANT_B, base=F).status_code == 404
    # tudo de A intacto; B pode ter o mesmo orçamento/nome
    assert get(client, f"/{d['id']}").status_code == 200
    assert get(client, "/orcamentos?ano=2026").json()[0]["id"] == orc["id"]
    assert send(client, "PUT", "/orcamentos/2026-01", {"valor": 99}, TENANT_B).status_code == 200
    assert get(client, "/orcamentos?ano=2026").json()[0]["valor"] == 10.0
    nova(client, "Licença X", tenant=TENANT_B)


def test_leitor_nao_escreve_mas_le(client, grants):
    d = nova(client)
    grants[TENANT_A] = {"access", "read"}
    corpo = {"nome": "Z", "categoria": "Outros", "tipo_custo": "PONTUAL", "valor": 1}
    escritas = [
        ("POST", "", corpo),
        ("PATCH", f"/{d['id']}", {"valor": 2}),
        ("DELETE", f"/{d['id']}", None),
        ("POST", f"/{d['id']}/cancelar", {}),
        ("POST", f"/{d['id']}/renegociar", {"novo_valor": 1}),
        ("POST", f"/{d['id']}/reverter", {}),
        ("PUT", "/orcamentos/2026-01", {"valor": 1}),
        ("DELETE", "/orcamentos/2026-01", None),
        ("POST", "/orcamentos/anual", {"ano": 2026, "valor_anual": 1}),
    ]
    for metodo, caminho, body in escritas:
        r = send(client, metodo, caminho, body)
        assert r.status_code == 403, (metodo, caminho, r.text)
    for caminho in ("", f"/{d['id']}", "/orcamentos", "/dashboard"):
        assert get(client, caminho).status_code == 200, caminho
    grants[TENANT_A] = set()
    assert get(client, "/dashboard").status_code == 403
    assert get(client, "").status_code == 403


def test_escrita_exige_csrf(client):
    corpo = {"nome": "Z", "categoria": "Outros", "tipo_custo": "PONTUAL", "valor": 1}
    r = client.post(P, json=corpo, headers={"X-Tenant-ID": str(TENANT_A)})
    assert r.status_code == 403

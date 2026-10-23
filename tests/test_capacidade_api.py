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
P = "/api/v1"


@pytest.fixture
def grants():
    return {TENANT_A: {"access", "read", "write"}, TENANT_B: {"access", "read", "write"}}


@pytest.fixture
def client(monkeypatch, tmp_path, grants):
    engine = create_engine(f"sqlite:///{tmp_path / 'cap.sqlite3'}", connect_args={"check_same_thread": False})

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


def novo_grupo(c, nome="G1", categoria="BUILD", tenant=TENANT_A, **extra):
    r = send(c, "POST", "/grupos", {"nome": nome, "categoria": categoria, **extra}, tenant)
    assert r.status_code == 201, r.text
    return r.json()


def nova_semana(c, ident="S1", tenant=TENANT_A, **extra):
    r = send(c, "POST", "/semanas", {"identificacao": ident, **extra}, tenant)
    assert r.status_code == 201, r.text
    return r.json()


def test_grupos_crud(client):
    g = novo_grupo(client, "Projetos", "build")
    assert g["categoria"] == "BUILD" and g["icone"] == "📋" and g["cor"] == "#64748B" and g["ativo"] is True
    assert [x["id"] for x in get(client, "/grupos").json()] == [g["id"]]
    r = send(client, "PATCH", f"/grupos/{g['id']}", {"cor": "#00AE9D", "ativo": False, "categoria": "run"})
    assert r.status_code == 200
    assert (r.json()["cor"], r.json()["ativo"], r.json()["categoria"]) == ("#00AE9D", False, "RUN")
    assert send(client, "DELETE", f"/grupos/{g['id']}").status_code == 204
    assert get(client, "/grupos").json() == []
    assert send(client, "DELETE", f"/grupos/{g['id']}").status_code == 404


def test_grupos_conflito_e_validacao(client):
    novo_grupo(client, "A")
    outro = novo_grupo(client, "B")
    assert send(client, "POST", "/grupos", {"nome": "A", "categoria": "RUN"}).status_code == 409
    assert send(client, "PATCH", f"/grupos/{outro['id']}", {"nome": "A"}).status_code == 409
    assert send(client, "PATCH", f"/grupos/{outro['id']}", {"nome": "B"}).status_code == 200
    for body in (
        {"nome": "X", "categoria": "OUTRO"},
        {"nome": "X", "categoria": "RUN", "cor": "azul"},
        {"nome": "X", "categoria": "RUN", "cor": "#12345"},
        {"nome": "", "categoria": "RUN"},
        {"nome": "X", "categoria": "RUN", "tenant_id": str(TENANT_B)},
        {"nome": "X", "categoria": "RUN", "icone": "x" * 17},
    ):
        assert send(client, "POST", "/grupos", body).status_code == 422, body


def test_grupos_padrao_idempotente(client):
    novo_grupo(client, "Rotinas (N0)", "RUN")
    r = send(client, "POST", "/grupos/padrao")
    assert r.status_code == 200 and r.json() == {"created": 5, "skipped": 1}
    assert send(client, "POST", "/grupos/padrao").json() == {"created": 0, "skipped": 6}
    assert len(get(client, "/grupos").json()) == 6


def test_semanas_crud_e_validacoes(client):
    s = nova_semana(client, "S1", data_inicio="2026-01-05", data_fim="2026-01-11")
    assert s["data_inicio"] == "2026-01-05"
    assert send(client, "POST", "/semanas", {"identificacao": "S1"}).status_code == 409
    assert (
        send(
            client, "POST", "/semanas", {"identificacao": "S2", "data_inicio": "2026-02-02", "data_fim": "2026-02-01"}
        ).status_code
        == 422
    )
    s2 = nova_semana(client, "S2")
    assert send(client, "PATCH", f"/semanas/{s2['id']}", {"identificacao": "S1"}).status_code == 409
    assert (
        send(
            client, "PATCH", f"/semanas/{s2['id']}", {"data_inicio": "2026-02-02", "data_fim": "2026-02-01"}
        ).status_code
        == 422
    )
    ok = send(client, "PATCH", f"/semanas/{s['id']}", {"identificacao": "S1b"})
    assert ok.status_code == 200 and ok.json()["identificacao"] == "S1b"
    # Só um lado no corpo: confere com o valor salvo.
    assert send(client, "PATCH", f"/semanas/{s['id']}", {"data_fim": "2026-01-01"}).status_code == 422
    assert send(client, "PATCH", f"/semanas/{s['id']}", {"data_inicio": "2026-01-12"}).status_code == 422
    limpa = send(client, "PATCH", f"/semanas/{s['id']}", {"data_fim": None})
    assert limpa.status_code == 200 and limpa.json()["data_fim"] is None
    assert len(get(client, "/semanas").json()) == 2
    assert send(client, "DELETE", f"/semanas/{s['id']}").status_code == 204
    assert send(client, "DELETE", f"/semanas/{s['id']}").status_code == 404


def test_lancamentos_crud_e_cascata(client):
    g, s = novo_grupo(client), nova_semana(client)
    r = send(
        client, "POST", "/lancamentos", {"grupo_id": g["id"], "semana_id": s["id"], "quantidade": 4, "status": "aberto"}
    )
    assert r.status_code == 201, r.text
    lanc = r.json()
    assert lanc["status"] == "ABERTO" and lanc["grupo_nome"] == "G1" and lanc["semana_identificacao"] == "S1"
    assert lanc["observacao"] is None and lanc["updated_at"]
    p = send(
        client, "PATCH", f"/lancamentos/{lanc['id']}", {"quantidade": 9, "status": "resolvido", "observacao": "ok"}
    )
    assert p.status_code == 200
    assert (p.json()["quantidade"], p.json()["status"], p.json()["observacao"]) == (9, "RESOLVIDO", "ok")
    assert len(get(client, f"/lancamentos?grupo_id={g['id']}&semana_id={s['id']}").json()) == 1
    assert get(client, f"/lancamentos?semana_id={uuid4()}").json() == []
    for body in (
        {"grupo_id": g["id"], "semana_id": s["id"], "quantidade": -1},
        {"grupo_id": g["id"], "semana_id": s["id"], "status": "X"},
        {"grupo_id": g["id"], "semana_id": s["id"], "tenant_id": str(TENANT_A)},
    ):
        assert send(client, "POST", "/lancamentos", body).status_code == 422
    assert send(client, "POST", "/lancamentos", {"grupo_id": str(uuid4()), "semana_id": s["id"]}).status_code == 404
    # Cascata ao remover o grupo e ao remover a semana.
    assert send(client, "DELETE", f"/grupos/{g['id']}").status_code == 204
    assert get(client, "/lancamentos").json() == []
    g2 = novo_grupo(client, "G2")
    send(client, "POST", "/lancamentos", {"grupo_id": g2["id"], "semana_id": s["id"]})
    assert len(get(client, "/lancamentos").json()) == 1
    assert send(client, "DELETE", f"/semanas/{s['id']}").status_code == 204
    assert get(client, "/lancamentos").json() == []
    assert send(client, "DELETE", f"/lancamentos/{lanc['id']}").status_code == 404


def test_inicializar_idempotente(client):
    g1, g2, s = novo_grupo(client, "G1"), novo_grupo(client, "G2", "RUN"), nova_semana(client)
    r = send(
        client, "POST", "/lancamentos/inicializar", {"semana_id": s["id"], "grupo_ids": [g1["id"]], "default_qtd": 2}
    )
    assert r.status_code == 200 and r.json() == {"created": 2, "skipped": 0, "total_grupos": 1}
    r = send(client, "POST", "/lancamentos/inicializar", {"semana_id": s["id"]})
    assert r.json() == {"created": 2, "skipped": 2, "total_grupos": 2}
    assert send(client, "POST", "/lancamentos/inicializar", {"semana_id": s["id"]}).json() == {
        "created": 0,
        "skipped": 4,
        "total_grupos": 2,
    }
    itens = get(client, f"/lancamentos?grupo_id={g1['id']}").json()
    assert sorted((i["status"], i["quantidade"]) for i in itens) == [("ABERTO", 2), ("RESOLVIDO", 2)]
    assert send(client, "POST", "/lancamentos/inicializar", {"semana_id": str(uuid4())}).status_code == 404
    assert (
        send(
            client, "POST", "/lancamentos/inicializar", {"semana_id": s["id"], "grupo_ids": [str(uuid4())]}
        ).status_code
        == 404
    )
    assert g2["id"]


def test_par_cria_e_atualiza(client):
    g, s = novo_grupo(client), nova_semana(client)
    corpo = {"grupo_id": g["id"], "semana_id": s["id"], "qtd_aberto": 3, "qtd_resolvido": 5, "obs_aberto": "a"}
    r = send(client, "PUT", "/lancamentos/par", corpo)
    assert r.status_code == 200
    assert [(i["status"], i["quantidade"]) for i in r.json()] == [("ABERTO", 3), ("RESOLVIDO", 5)]
    ids = [i["id"] for i in r.json()]
    corpo.update(qtd_aberto=1, qtd_resolvido=0)
    r2 = send(client, "PUT", "/lancamentos/par", corpo)
    assert [i["id"] for i in r2.json()] == ids
    assert [i["quantidade"] for i in r2.json()] == [1, 0]
    assert len(get(client, "/lancamentos").json()) == 2
    assert send(client, "PUT", "/lancamentos/par", {**corpo, "qtd_aberto": -1}).status_code == 422
    assert send(client, "PUT", "/lancamentos/par", {**corpo, "grupo_id": str(uuid4())}).status_code == 404


def test_dashboard(client):
    b, r_ = novo_grupo(client, "B", "BUILD"), novo_grupo(client, "R", "RUN")
    off = novo_grupo(client, "Off", "RUN")
    send(client, "PATCH", f"/grupos/{off['id']}", {"ativo": False})
    s1, s2 = nova_semana(client, "S1"), nova_semana(client, "S2")
    for g, s, qa, qr in ((b, s1, 7, 0), (r_, s1, 3, 0), (off, s1, 50, 50), (b, s2, 1, 1)):
        send(
            client,
            "PUT",
            "/lancamentos/par",
            {"grupo_id": g["id"], "semana_id": s["id"], "qtd_aberto": qa, "qtd_resolvido": qr},
        )
    todas = get(client, "/dashboard").json()
    assert todas["periodo"] == "Todas as semanas" and todas["semana_id"] is None
    assert todas["total"] == 12 and [g["nome"] for g in todas["groups"]] == ["B", "R"]
    uma = get(client, f"/dashboard?semana_id={s1['id']}").json()
    assert uma["periodo"] == "S1" and uma["total"] == 10
    assert uma["perc_build"] == 0.7 and uma["build_atingiu_meta"] and uma["run_atingiu_meta"]
    assert get(client, f"/dashboard?semana_id={uuid4()}").status_code == 404


def test_dashboard_inclui_rotinas(client):
    b = novo_grupo(client, "B", "BUILD")
    s1 = nova_semana(client, "S1", data_inicio="2026-01-05", data_fim="2026-01-11")
    s2 = nova_semana(client, "S2", data_inicio="2026-01-12", data_fim="2026-01-18")
    send(
        client,
        "PUT",
        "/lancamentos/par",
        {"grupo_id": b["id"], "semana_id": s1["id"], "qtd_aberto": 1, "qtd_resolvido": 0},
    )
    base = {"inicio_vigencia": "2026-01-01", "tipo_agendamento": "SEMANAL", "dia_semana": "Segunda"}
    r = send(client, "POST", "/rotinas", {**base, "titulo": "Build", "categoria": "BUILD", "esforco_estimado_min": 60})
    build = r.json()
    send(client, "POST", "/rotinas", {**base, "titulo": "Run", "categoria": "RUN", "esforco_estimado_min": 30})
    conclusao = {"semana_id": s1["id"], "ocorrencia": "SEMANA", "status": "CONCLUIDA", "esforco_real_min": 45}
    assert send(client, "PUT", f"/rotinas/{build['id']}/execucao", conclusao).status_code == 200
    uma = get(client, f"/dashboard?semana_id={s1['id']}").json()
    assert {x["categoria"]: x for x in uma["rotinas"]} == {
        "BUILD": {
            "categoria": "BUILD",
            "abertos": 0,
            "resolvidos": 1,
            "total": 1,
            "minutos_previstos": 60,
            "minutos_executados": 45,
        },
        "RUN": {
            "categoria": "RUN",
            "abertos": 1,
            "resolvidos": 0,
            "total": 1,
            "minutos_previstos": 30,
            "minutos_executados": 0,
        },
    }
    assert (uma["qtd_build"], uma["qtd_run"], uma["total"]) == (2, 1, 3)
    assert (uma["resolvidos_build"], uma["abertos_build"], uma["abertos_run"]) == (1, 1, 1)
    # Sem semana_id: soma de todas as semanas (duas ocorrências por rotina).
    todas = get(client, "/dashboard").json()
    assert {x["categoria"]: x["total"] for x in todas["rotinas"]} == {"BUILD": 2, "RUN": 2}
    assert todas["qtd_build"] == 3 and todas["qtd_run"] == 2
    vazia = get(client, f"/dashboard?semana_id={s2['id']}").json()
    assert vazia["total"] == 2 and {x["categoria"]: x["abertos"] for x in vazia["rotinas"]} == {"BUILD": 1, "RUN": 1}
    # Outro tenant não enxerga as rotinas de A.
    assert get(client, "/dashboard", TENANT_B).json()["rotinas"] == []


def test_isolamento_entre_tenants(client):
    g, s = novo_grupo(client), nova_semana(client)
    lanc = send(client, "POST", "/lancamentos", {"grupo_id": g["id"], "semana_id": s["id"], "quantidade": 5}).json()
    for path in (f"/grupos/{g['id']}", f"/semanas/{s['id']}", f"/lancamentos/{lanc['id']}"):
        assert send(client, "PATCH", path, {}, TENANT_B).status_code == 404
        assert send(client, "DELETE", path, None, TENANT_B).status_code == 404
    gb, sb = novo_grupo(client, "GB", tenant=TENANT_B), nova_semana(client, "SB", tenant=TENANT_B)
    cruzado = (
        {"grupo_id": g["id"], "semana_id": sb["id"]},
        {"grupo_id": gb["id"], "semana_id": s["id"]},
        {"grupo_id": g["id"], "semana_id": s["id"]},
    )
    for body in cruzado:
        assert send(client, "POST", "/lancamentos", body, TENANT_B).status_code == 404
    assert (
        send(
            client, "PUT", "/lancamentos/par", {**cruzado[0], "qtd_aberto": 1, "qtd_resolvido": 1}, TENANT_B
        ).status_code
        == 404
    )
    assert send(client, "POST", "/lancamentos/inicializar", {"semana_id": s["id"]}, TENANT_B).status_code == 404
    assert (
        send(
            client, "POST", "/lancamentos/inicializar", {"semana_id": sb["id"], "grupo_ids": [g["id"]]}, TENANT_B
        ).status_code
        == 404
    )
    assert [x["id"] for x in get(client, "/grupos", TENANT_B).json()] == [gb["id"]]
    assert [x["id"] for x in get(client, "/semanas", TENANT_B).json()] == [sb["id"]]
    assert get(client, "/lancamentos", TENANT_B).json() == []
    assert get(client, f"/dashboard?semana_id={s['id']}", TENANT_B).status_code == 404
    dash = get(client, "/dashboard", TENANT_B).json()
    assert dash["total"] == 0 and [x["id"] for x in dash["groups"]] == [gb["id"]]
    # Nada mudou em A; mesmo nome é permitido em outro tenant.
    assert get(client, "/dashboard").json()["total"] == 5
    assert novo_grupo(client, "GB", tenant=TENANT_A)["nome"] == "GB"
    assert len(get(client, "/lancamentos").json()) == 1


def test_leitor_nao_escreve(client, grants):
    g, s = novo_grupo(client), nova_semana(client)
    grants[TENANT_A] = {"access", "read"}
    assert get(client, "/grupos").status_code == 200
    assert get(client, "/dashboard").status_code == 200
    escritas = (
        ("POST", "/grupos", {"nome": "X", "categoria": "RUN"}),
        ("POST", "/grupos/padrao", None),
        ("PATCH", f"/grupos/{g['id']}", {"nome": "Y"}),
        ("DELETE", f"/grupos/{g['id']}", None),
        ("POST", "/semanas", {"identificacao": "X"}),
        ("PATCH", f"/semanas/{s['id']}", {"identificacao": "Y"}),
        ("DELETE", f"/semanas/{s['id']}", None),
        ("POST", "/lancamentos", {"grupo_id": g["id"], "semana_id": s["id"]}),
        ("POST", "/lancamentos/inicializar", {"semana_id": s["id"]}),
        ("PUT", "/lancamentos/par", {"grupo_id": g["id"], "semana_id": s["id"], "qtd_aberto": 1, "qtd_resolvido": 1}),
        ("PATCH", f"/lancamentos/{uuid4()}", {"quantidade": 1}),
        ("DELETE", f"/lancamentos/{uuid4()}", None),
    )
    for metodo, caminho, corpo in escritas:
        assert send(client, metodo, caminho, corpo).status_code == 403, (metodo, caminho)
    assert len(get(client, "/grupos").json()) == 1


def test_escrita_exige_csrf_e_origin(client):
    corpo = {"nome": "X", "categoria": "RUN"}
    sem_csrf = client.post(
        P + "/grupos", json=corpo, headers={"X-Tenant-ID": str(TENANT_A), "Origin": settings.PUBLIC_URL}
    )
    assert sem_csrf.status_code == 403
    sem_origin = client.post(P + "/grupos", json=corpo, headers={"X-Tenant-ID": str(TENANT_A), "X-CSRF-Token": "csrf"})
    assert sem_origin.status_code == 403

from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from src.backend.api import deps
from src.backend.core import sessions
from src.backend.core.config import settings
from src.backend.integrations.guilarde.contracts import Authorization, Principal
from src.backend.models import Base

TENANT_A, TENANT_B = uuid4(), uuid4()
P = "/api/v1/demandas"
R = "/api/v1"


@pytest.fixture
def grants():
    return {TENANT_A: {"access", "read", "write"}, TENANT_B: {"access", "read", "write"}}


@pytest.fixture
def who():
    return {"sub": "user-a"}


@pytest.fixture
def client(monkeypatch, tmp_path, grants, who):
    engine = create_engine(f"sqlite:///{tmp_path / 'dem.sqlite3'}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    monkeypatch.setattr(deps, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "AUTH_MODE", "oidc")
    monkeypatch.setattr(sessions, "load_session", lambda _sid: {"access_token": "test", "csrf": "csrf"})
    monkeypatch.setattr(deps, "validate_access_token", lambda _token: Principal(sub=who["sub"]))

    async def authorize(_token, tenant_id, permission):
        perms = grants.get(tenant_id, set())
        return Authorization(
            sub=who["sub"],
            tenant_id=tenant_id,
            app_id=settings.APP_ID,
            allowed=permission in perms and "access" in perms,
            permissions=perms,
        )

    monkeypatch.setattr(deps.core_client, "authorize", authorize)
    from tests.support.tenant_example import create_test_app

    test_client = TestClient(create_test_app())
    test_client.cookies.set(settings.SESSION_COOKIE, "a" * 43)
    test_client.engine = engine  # type: ignore[attr-defined]
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


def cget(c, path, tenant=TENANT_A):
    return c.get(R + path, headers=h(tenant))


def csend(c, method, path, body=None, tenant=TENANT_A):
    return c.request(method, R + path, json=body, headers=h(tenant, True))


def grupo(c, nome="Suporte", categoria="RUN", tenant=TENANT_A, **extra):
    r = csend(c, "POST", "/grupos", {"nome": nome, "categoria": categoria, **extra}, tenant)
    assert r.status_code == 201, r.text
    return r.json()


def demanda(c, titulo="Preciso de acesso", tenant=TENANT_A, **extra):
    r = send(c, "POST", "", {"titulo": titulo, **extra}, tenant)
    assert r.status_code == 201, r.text
    return r.json()


def triagem(c, tenant=TENANT_A):
    return next(g for g in cget(c, "/grupos", tenant).json() if g["sistema"])


def somente_leitura(grants):
    grants[TENANT_A] = {"access", "read"}


def classificar(c, d, g, **extra):
    r = send(c, "POST", f"/{d['id']}/classificar", {"grupo_id": g["id"], **extra})
    assert r.status_code == 200, r.text
    return r.json()


def sql(c, comando, **params):
    with c.engine.begin() as conn:
        conn.execute(text(comando), params)


# --- Triagem (grupo de sistema) ----------------------------------------------------------------------------------


def test_triagem_criada_uma_vez_e_visivel_em_grupos(client):
    grupos = cget(client, "/grupos").json()
    assert len(grupos) == 1
    t = grupos[0]
    assert (t["nome"], t["categoria"], t["sistema"], t["ativo"], t["icone"], t["cor"]) == (
        "Triagem",
        "RUN",
        True,
        True,
        "📥",
        "#64748B",
    )
    assert cget(client, "/grupos").json()[0]["id"] == t["id"]
    demanda(client)
    assert get(client, "").status_code == 200
    assert cget(client, "/dashboard").status_code == 200
    assert [g["id"] for g in cget(client, "/grupos").json()] == [t["id"]]
    outra = cget(client, "/grupos", TENANT_B).json()
    assert len(outra) == 1 and outra[0]["id"] != t["id"]


def test_triagem_criada_por_qualquer_funcao_do_servico(client):
    assert get(client, "").status_code == 200
    assert [g["nome"] for g in cget(client, "/grupos").json()] == ["Triagem"]
    assert cget(client, "/dashboard", TENANT_B).status_code == 200
    assert [g["sistema"] for g in cget(client, "/grupos", TENANT_B).json()] == [True]


def test_grupo_comum_nao_e_sistema(client):
    g = grupo(client, "Alfa")
    assert g["sistema"] is False
    assert [x["nome"] for x in cget(client, "/grupos").json()] == ["Alfa", "Triagem"]


def test_triagem_protegida(client):
    t = triagem(client)
    assert csend(client, "DELETE", f"/grupos/{t['id']}").status_code == 409
    for corpo in ({"nome": "Outro"}, {"categoria": "BUILD"}, {"ativo": False}):
        assert csend(client, "PATCH", f"/grupos/{t['id']}", corpo).status_code == 409, corpo
    r = csend(client, "PATCH", f"/grupos/{t['id']}", {"icone": "🎯", "cor": "#00AE9D"})
    assert r.status_code == 200
    assert (r.json()["icone"], r.json()["cor"], r.json()["nome"], r.json()["sistema"]) == (
        "🎯",
        "#00AE9D",
        "Triagem",
        True,
    )
    # valores iguais aos atuais não contam como mudança
    corpo = {"nome": "Triagem", "categoria": "RUN", "ativo": True}
    assert csend(client, "PATCH", f"/grupos/{t['id']}", corpo).status_code == 200
    assert triagem(client)["id"] == t["id"]


def test_triagem_adota_grupo_existente_com_mesmo_nome(client):
    antigo = grupo(client, "Triagem", "BUILD")
    csend(client, "PATCH", f"/grupos/{antigo['id']}", {"ativo": False})
    grupos = cget(client, "/grupos").json()
    assert len(grupos) == 1
    t = grupos[0]
    assert t["id"] == antigo["id"]
    assert (t["sistema"], t["categoria"], t["ativo"]) == (True, "RUN", True)


def test_grupo_com_demandas_nao_exclui(client):
    g = grupo(client, "Suporte")
    d = demanda(client)
    classificar(client, d, g)
    assert csend(client, "DELETE", f"/grupos/{g['id']}").status_code == 409
    assert send(client, "POST", f"/{d['id']}/cancelar").status_code == 200
    assert csend(client, "DELETE", f"/grupos/{g['id']}").status_code == 409
    vazio = grupo(client, "Vazio")
    assert csend(client, "DELETE", f"/grupos/{vazio['id']}").status_code == 204


# --- abrir demanda e visibilidade --------------------------------------------------------------------------------


def test_abrir_demanda_vai_para_triagem(client):
    d = demanda(client, "  Novo acesso  ", descricao="Detalhes", prioridade="alta")
    t = triagem(client)
    assert (d["titulo"], d["descricao"], d["prioridade"], d["status"]) == ("Novo acesso", "Detalhes", "ALTA", "ABERTA")
    assert (d["grupo_id"], d["grupo_nome"], d["solicitante_sub"]) == (t["id"], "Triagem", "user-a")
    assert d["created_at"] and d["updated_at"]
    for campo in ("classificado_por", "classificado_em", "concluido_por", "concluido_em", "cancelado_em"):
        assert d[campo] is None, campo
    assert demanda(client, "Padrão")["prioridade"] == "MEDIA"
    assert get(client, f"/{d['id']}").json() == d


def test_abrir_demanda_validacao(client):
    assert send(client, "POST", "", {"titulo": "   "}).status_code == 422
    assert send(client, "POST", "", {"titulo": "x" * 201}).status_code == 422
    assert send(client, "POST", "", {"titulo": "ok", "descricao": "x" * 10_001}).status_code == 422
    assert send(client, "POST", "", {"titulo": "ok", "prioridade": "URGENTE"}).status_code == 422
    assert send(client, "POST", "", {"titulo": "ok", "solicitante_sub": "outro"}).status_code == 422
    assert send(client, "POST", "", {"titulo": "ok", "grupo_id": str(uuid4())}).status_code == 422
    assert send(client, "POST", "", {"titulo": "ok", "descricao": "x" * 10_000}).status_code == 201


def test_solicitante_somente_leitura_abre_e_ve_apenas_as_proprias(client, grants, who):
    outra = demanda(client, "Da equipe")
    somente_leitura(grants)
    who["sub"] = "user-b"
    propria = demanda(client, "Do solicitante")
    assert propria["solicitante_sub"] == "user-b"
    assert [d["id"] for d in get(client, "").json()] == [propria["id"]]
    assert [d["id"] for d in get(client, "?minhas=false").json()] == [propria["id"]]
    assert get(client, f"/{propria['id']}").status_code == 200
    assert get(client, f"/{outra['id']}").status_code == 404
    for acao in ("cancelar", "concluir", "reabrir"):
        assert send(client, "POST", f"/{propria['id']}/{acao}").status_code == 403, acao
    assert send(client, "POST", f"/{propria['id']}/classificar", {"grupo_id": str(uuid4())}).status_code == 403


def test_equipe_com_write_ve_todas_e_filtra_minhas(client, who):
    a = demanda(client, "Da A")
    who["sub"] = "user-b"
    b = demanda(client, "Da B")
    assert {d["id"] for d in get(client, "").json()} == {a["id"], b["id"]}
    assert [d["id"] for d in get(client, "?minhas=true").json()] == [b["id"]]
    assert get(client, f"/{a['id']}").status_code == 200


def test_filtros_status_e_grupo(client):
    g = grupo(client, "Suporte")
    d1, d2, d3, d4 = (demanda(client, str(i)) for i in range(4))
    classificar(client, d1, g)
    send(client, "POST", f"/{d2['id']}/cancelar")
    send(client, "POST", f"/{d3['id']}/concluir")
    assert {d["id"] for d in get(client, "?status=ABERTA").json()} == {d1["id"], d4["id"]}
    assert [d["id"] for d in get(client, "?status=cancelada").json()] == [d2["id"]]
    assert [d["id"] for d in get(client, "?status=CONCLUIDA").json()] == [d3["id"]]
    assert [d["id"] for d in get(client, f"?grupo_id={g['id']}").json()] == [d1["id"]]
    assert get(client, f"?grupo_id={uuid4()}").json() == []
    assert get(client, "?grupo_id=nao-e-uuid").status_code == 422


def test_ordenacao_por_prioridade_e_depois_criacao(client):
    baixa = demanda(client, "baixa", prioridade="BAIXA")
    alta1 = demanda(client, "alta1", prioridade="ALTA")
    media = demanda(client, "media", prioridade="MEDIA")
    alta2 = demanda(client, "alta2", prioridade="ALTA")
    sql(client, "UPDATE demandas SET created_at='2030-01-02 00:00:00' WHERE id=:id", id=alta1["id"].replace("-", ""))
    sql(client, "UPDATE demandas SET created_at='2030-01-01 00:00:00' WHERE id=:id", id=alta2["id"].replace("-", ""))
    ids = [d["id"] for d in get(client, "").json()]
    assert ids == [alta2["id"], alta1["id"], media["id"], baixa["id"]]


# --- classificar -------------------------------------------------------------------------------------------------


def test_classificar_e_reclassificar_mantem_status(client, who):
    g1, g2 = grupo(client, "Suporte"), grupo(client, "Infra", "BUILD")
    d = demanda(client, prioridade="BAIXA")
    v = classificar(client, d, g1, prioridade="alta")
    assert (v["status"], v["grupo_id"], v["grupo_nome"], v["prioridade"]) == ("ABERTA", g1["id"], "Suporte", "ALTA")
    assert v["classificado_por"] == "user-a" and v["classificado_em"]
    who["sub"] = "user-c"
    v = classificar(client, d, g2)
    assert (v["grupo_nome"], v["prioridade"], v["classificado_por"]) == ("Infra", "ALTA", "user-c")
    assert v["status"] == "ABERTA"
    assert v["solicitante_sub"] == "user-a"
    assert get(client, f"/{d['id']}").json()["grupo_id"] == g2["id"]


def test_classificar_destino_invalido(client):
    d = demanda(client)
    t = triagem(client)
    inativo = grupo(client, "Inativo")
    csend(client, "PATCH", f"/grupos/{inativo['id']}", {"ativo": False})
    assert send(client, "POST", f"/{d['id']}/classificar", {"grupo_id": t["id"]}).status_code == 422
    assert send(client, "POST", f"/{d['id']}/classificar", {"grupo_id": inativo["id"]}).status_code == 422
    assert send(client, "POST", f"/{d['id']}/classificar", {"grupo_id": str(uuid4())}).status_code == 404
    assert send(client, "POST", f"/{d['id']}/classificar", {}).status_code == 422
    outro = grupo(client, "Do B", tenant=TENANT_B)
    assert send(client, "POST", f"/{d['id']}/classificar", {"grupo_id": outro["id"]}).status_code == 404
    atual = get(client, f"/{d['id']}").json()
    assert (atual["status"], atual["grupo_id"]) == ("ABERTA", t["id"])
    assert send(client, "POST", f"/{uuid4()}/classificar", {"grupo_id": inativo["id"]}).status_code == 404


def test_classificar_so_aberta(client):
    g = grupo(client, "Suporte")
    cancelada, concluida = demanda(client, "c"), demanda(client, "d")
    send(client, "POST", f"/{cancelada['id']}/cancelar")
    send(client, "POST", f"/{concluida['id']}/concluir")
    for d in (cancelada, concluida):
        assert send(client, "POST", f"/{d['id']}/classificar", {"grupo_id": g["id"]}).status_code == 409


# --- concluir / reabrir / cancelar -------------------------------------------------------------------------------


def test_concluir_na_propria_triagem_e_reabrir(client, who):
    t = triagem(client)
    d = demanda(client)
    who["sub"] = "user-c"
    r = send(client, "POST", f"/{d['id']}/concluir")
    assert r.status_code == 200, r.text
    v = r.json()
    assert (v["status"], v["concluido_por"], v["grupo_id"]) == ("CONCLUIDA", "user-c", t["id"])
    assert v["concluido_em"]
    assert send(client, "POST", f"/{d['id']}/concluir").status_code == 409
    assert send(client, "POST", f"/{d['id']}/cancelar").status_code == 409
    r = send(client, "POST", f"/{d['id']}/reabrir")
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["concluido_por"], r.json()["concluido_em"]) == ("ABERTA", None, None)
    assert send(client, "POST", f"/{d['id']}/reabrir").status_code == 409
    assert send(client, "POST", f"/{d['id']}/concluir").status_code == 200


def test_cancelar(client):
    g = grupo(client, "Suporte")
    d = demanda(client)
    r = send(client, "POST", f"/{d['id']}/cancelar")
    assert r.status_code == 200
    assert r.json()["status"] == "CANCELADA" and r.json()["cancelado_em"]
    for acao in ("cancelar", "concluir", "reabrir"):
        assert send(client, "POST", f"/{d['id']}/{acao}").status_code == 409, acao
    assert send(client, "POST", f"/{d['id']}/classificar", {"grupo_id": g["id"]}).status_code == 409
    assert send(client, "POST", f"/{uuid4()}/cancelar").status_code == 404


def test_reabrir_so_concluida(client):
    d = demanda(client)
    assert send(client, "POST", f"/{d['id']}/reabrir").status_code == 409
    assert send(client, "POST", f"/{uuid4()}/reabrir").status_code == 404


def test_cancelar_e_concluir_classificada_mantem_grupo(client):
    g = grupo(client, "Suporte")
    a, b = demanda(client, "a"), demanda(client, "b")
    classificar(client, a, g)
    classificar(client, b, g)
    r = send(client, "POST", f"/{a['id']}/cancelar")
    assert (r.json()["status"], r.json()["grupo_nome"]) == ("CANCELADA", "Suporte")
    r = send(client, "POST", f"/{b['id']}/concluir")
    assert (r.json()["status"], r.json()["grupo_nome"]) == ("CONCLUIDA", "Suporte")


# --- painel ------------------------------------------------------------------------------------------------------


def grupo_do_painel(painel, nome):
    return next(g for g in painel["groups"] if g["nome"] == nome)


def semana(c, ident, inicio=None, fim=None):
    corpo = {"identificacao": ident}
    if inicio is not None:
        corpo.update(data_inicio=inicio.isoformat(), data_fim=fim.isoformat())
    r = csend(c, "POST", "/semanas", corpo)
    assert r.status_code == 201, r.text
    return r.json()


def test_painel_conta_demandas_por_status_sem_semana(client):
    build = grupo(client, "Projetos", "BUILD")
    run = grupo(client, "Suporte", "RUN")
    d1, d2, d3, d4, d5 = (demanda(client, str(i)) for i in range(5))
    classificar(client, d1, build)
    classificar(client, d2, build)
    classificar(client, d3, run)
    send(client, "POST", f"/{d2['id']}/concluir")
    send(client, "POST", f"/{d3['id']}/cancelar")
    send(client, "POST", f"/{d4['id']}/concluir")  # concluída na Triagem
    p = cget(client, "/dashboard").json()
    proj = grupo_do_painel(p, "Projetos")
    assert (proj["abertos"], proj["resolvidos"], proj["demandas_abertas"], proj["demandas_resolvidas"]) == (1, 1, 1, 1)
    sup = grupo_do_painel(p, "Suporte")
    assert (sup["abertos"], sup["resolvidos"], sup["demandas_abertas"], sup["demandas_resolvidas"]) == (0, 0, 0, 0)
    tri = grupo_do_painel(p, "Triagem")
    assert (tri["abertos"], tri["resolvidos"], tri["demandas_abertas"], tri["demandas_resolvidas"]) == (1, 1, 1, 1)
    assert (p["abertos_build"], p["resolvidos_build"], p["abertos_run"], p["resolvidos_run"]) == (1, 1, 1, 1)
    assert (p["total_abertos"], p["total_resolvidos"], p["total"]) == (2, 2, 4)
    assert d5["id"]


def test_painel_soma_lancamentos_e_demandas(client):
    g = grupo(client, "Projetos", "BUILD")
    s = semana(client, "S1")
    lanc = {"grupo_id": g["id"], "semana_id": s["id"], "quantidade": 3, "status": "ABERTO"}
    csend(client, "POST", "/lancamentos", lanc)
    classificar(client, demanda(client), g)
    proj = grupo_do_painel(cget(client, "/dashboard").json(), "Projetos")
    assert (proj["abertos"], proj["demandas_abertas"]) == (4, 1)


def test_painel_semana_filtra_por_abertura_e_conclusao(client):
    g = grupo(client, "Projetos", "BUILD")
    hoje = date.today()
    atual = semana(client, "Atual", hoje - timedelta(days=1), hoje + timedelta(days=1))
    antiga = semana(client, "Antiga", date(2000, 1, 3), date(2000, 1, 9))
    sem_datas = semana(client, "Sem datas")
    aberta_antiga, aberta_nova, concl_antiga_aberta_hoje, concl_hoje_aberta_antiga = (
        demanda(client, str(i)) for i in range(4)
    )
    for d in (aberta_antiga, aberta_nova, concl_antiga_aberta_hoje, concl_hoje_aberta_antiga):
        classificar(client, d, g)
    send(client, "POST", f"/{concl_antiga_aberta_hoje['id']}/concluir")
    send(client, "POST", f"/{concl_hoje_aberta_antiga['id']}/concluir")
    antigo = "2000-01-05 12:00:00"
    sql(client, "UPDATE demandas SET created_at=:t WHERE id=:id", t=antigo, id=aberta_antiga["id"].replace("-", ""))
    sql(
        client,
        "UPDATE demandas SET created_at=:t WHERE id=:id",
        t=antigo,
        id=concl_hoje_aberta_antiga["id"].replace("-", ""),
    )
    sql(
        client,
        "UPDATE demandas SET concluido_em=:t WHERE id=:id",
        t=antigo,
        id=concl_antiga_aberta_hoje["id"].replace("-", ""),
    )

    def contagem(sem):
        painel = cget(client, f"/dashboard?semana_id={sem['id']}").json()
        item = grupo_do_painel(painel, "Projetos")
        return item["demandas_abertas"], item["demandas_resolvidas"]

    # ABERTA conta pela abertura; CONCLUIDA pela conclusão.
    assert contagem(atual) == (1, 1)  # aberta_nova ; concluída hoje
    assert contagem(antiga) == (1, 1)  # aberta_antiga ; concluída em 2000
    assert contagem(sem_datas) == (0, 0)
    p = cget(client, f"/dashboard?semana_id={sem_datas['id']}").json()
    assert p["total"] == 0
    todas = grupo_do_painel(cget(client, "/dashboard").json(), "Projetos")
    assert (todas["demandas_abertas"], todas["demandas_resolvidas"]) == (2, 2)


def test_painel_ignora_grupo_inativo(client):
    g = grupo(client, "Projetos", "BUILD")
    classificar(client, demanda(client), g)
    csend(client, "PATCH", f"/grupos/{g['id']}", {"ativo": False})
    p = cget(client, "/dashboard").json()
    assert [x["nome"] for x in p["groups"]] == ["Triagem"]
    assert p["total"] == 0


# --- isolamento e permissões -------------------------------------------------------------------------------------


def test_isolamento_entre_tenants(client):
    g = grupo(client, "Suporte")
    d = demanda(client)
    assert get(client, "", TENANT_B).json() == []
    assert get(client, f"/{d['id']}", TENANT_B).status_code == 404
    assert send(client, "POST", f"/{d['id']}/cancelar", tenant=TENANT_B).status_code == 404
    assert send(client, "POST", f"/{d['id']}/concluir", tenant=TENANT_B).status_code == 404
    assert send(client, "POST", f"/{d['id']}/classificar", {"grupo_id": g["id"]}, TENANT_B).status_code == 404
    assert get(client, f"/{d['id']}").status_code == 200
    painel_b = cget(client, "/dashboard", TENANT_B).json()
    assert painel_b["total"] == 0


def test_sem_acesso_ao_tenant_e_negado(client, grants):
    grants.pop(TENANT_B)
    assert get(client, "", TENANT_B).status_code == 403
    assert send(client, "POST", "", {"titulo": "x"}, TENANT_B).status_code == 403


def test_rotas_de_filas_nao_existem(client):
    assert get(client, "/filas").status_code in (404, 422)
    assert send(client, "POST", "/filas", {"nome": "x"}).status_code in (404, 405)


def test_mutacao_sem_csrf_e_negada(client):
    r = client.post(P, json={"titulo": "x"}, headers={"X-Tenant-ID": str(TENANT_A)})
    assert r.status_code == 403

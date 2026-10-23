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
VIGENCIA = "2026-01-01"


@pytest.fixture
def grants():
    return {TENANT_A: {"access", "read", "write"}, TENANT_B: {"access", "read", "write"}}


@pytest.fixture
def client(monkeypatch, tmp_path, grants):
    engine = create_engine(f"sqlite:///{tmp_path / 'rot.sqlite3'}", connect_args={"check_same_thread": False})

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


def nova_rotina(c, titulo="R1", tenant=TENANT_A, **extra):
    corpo = {"titulo": titulo, "tipo_agendamento": "SEMANAL", "dia_semana": "Segunda", "inicio_vigencia": VIGENCIA}
    corpo.update(extra)
    r = send(c, "POST", "/rotinas", corpo, tenant)
    assert r.status_code == 201, r.text
    return r.json()


def nova_semana(c, ident="S1", tenant=TENANT_A, inicio="2026-01-05", fim="2026-01-11"):
    corpo = {"identificacao": ident, "data_inicio": inicio, "data_fim": fim}
    r = send(c, "POST", "/semanas", corpo, tenant)
    assert r.status_code == 201, r.text
    return r.json()


def executar(c, rotina, semana, ocorrencia="SEMANA", status="CONCLUIDA", tenant=TENANT_A, **extra):
    corpo = {"semana_id": semana["id"], "ocorrencia": ocorrencia, "status": status, **extra}
    return send(c, "PUT", f"/rotinas/{rotina['id']}/execucao", corpo, tenant)


def test_rotinas_crud(client):
    r = nova_rotina(client, "Backup", categoria="build", esforco_estimado_min=30, link_recurso="https://x.com/a")
    assert r["categoria"] == "BUILD" and r["periodo"] == "Manhã" and r["ativo"] is True and r["ordem"] == 0
    assert r["dia_mes"] is None and r["updated_at"] and r["created_at"]
    assert get(client, f"/rotinas/{r['id']}").json()["titulo"] == "Backup"
    p = send(client, "PATCH", f"/rotinas/{r['id']}", {"titulo": "Backup 2", "ativo": False, "esforco_estimado_min": 45})
    assert p.status_code == 200
    assert (p.json()["titulo"], p.json()["ativo"], p.json()["esforco_estimado_min"]) == ("Backup 2", False, 45)
    assert p.json()["categoria"] == "BUILD" and p.json()["dia_semana"] == "Segunda"
    limpa = send(client, "PATCH", f"/rotinas/{r['id']}", {"link_recurso": None})
    assert limpa.json()["link_recurso"] is None
    assert get(client, "/rotinas?ativo=true").json() == []
    assert [x["id"] for x in get(client, "/rotinas?ativo=false").json()] == [r["id"]]
    assert len(get(client, "/rotinas").json()) == 1
    assert send(client, "DELETE", f"/rotinas/{r['id']}").status_code == 204
    assert send(client, "DELETE", f"/rotinas/{r['id']}").status_code == 404
    assert get(client, f"/rotinas/{r['id']}").status_code == 404
    assert send(client, "PATCH", f"/rotinas/{r['id']}", {"titulo": "x"}).status_code == 404


def test_rotinas_ordem_e_normalizacao_de_tipo(client):
    nova_rotina(client, "B", ordem=2)
    nova_rotina(client, "A", ordem=2)
    nova_rotina(client, "Z", ordem=1)
    assert [x["titulo"] for x in get(client, "/rotinas").json()] == ["Z", "A", "B"]
    mensal = nova_rotina(client, "M", tipo_agendamento="mensal", dia_semana=None, dia_mes=10)
    assert mensal["tipo_agendamento"] == "MENSAL_DIA_FIXO"
    ult = nova_rotina(client, "U", tipo_agendamento="ultimo_dia", dia_semana="Sexta", dia_mes=3)
    assert ult["tipo_agendamento"] == "MENSAL_ULTIMO_UTIL" and ult["dia_semana"] is None and ult["dia_mes"] is None


def test_rotinas_validacoes(client):
    base = {"titulo": "X", "inicio_vigencia": VIGENCIA}
    invalidos = (
        {**base, "tipo_agendamento": "SEMANAL"},
        {**base, "tipo_agendamento": "MENSAL_DIA_FIXO"},
        {**base, "tipo_agendamento": "DIARIA", "link_recurso": "javascript:alert(1)"},
        {**base, "tipo_agendamento": "DIARIA", "link_recurso": "ftp://x.com"},
        {**base, "tipo_agendamento": "DIARIA", "esforco_estimado_min": 1441},
        {**base, "tipo_agendamento": "DIARIA", "esforco_estimado_min": -1},
        {**base, "tipo_agendamento": "QUALQUER"},
        {**base, "tipo_agendamento": "SEMANAL", "dia_semana": "Funday"},
        {**base, "tipo_agendamento": "MENSAL_DIA_FIXO", "dia_mes": 32},
        {**base, "tipo_agendamento": "DIARIA", "categoria": "OUTRA"},
        {**base, "tipo_agendamento": "DIARIA", "periodo": "Noite"},
        {**base, "tipo_agendamento": "DIARIA", "ordem": -1},
        {**base, "tipo_agendamento": "DIARIA", "titulo": ""},
        {**base, "tipo_agendamento": "DIARIA", "tenant_id": str(TENANT_B)},
    )
    for corpo in invalidos:
        assert send(client, "POST", "/rotinas", corpo).status_code == 422, corpo
    assert get(client, "/rotinas").json() == []
    r = nova_rotina(client)
    # O PATCH revalida com o estado resultante.
    assert send(client, "PATCH", f"/rotinas/{r['id']}", {"dia_semana": None}).status_code == 422
    assert send(client, "PATCH", f"/rotinas/{r['id']}", {"tipo_agendamento": "MENSAL"}).status_code == 422
    assert send(client, "PATCH", f"/rotinas/{r['id']}", {"link_recurso": "javascript:x"}).status_code == 422
    ok = send(client, "PATCH", f"/rotinas/{r['id']}", {"tipo_agendamento": "MENSAL", "dia_mes": 5})
    assert ok.status_code == 200
    assert (ok.json()["tipo_agendamento"], ok.json()["dia_semana"], ok.json()["dia_mes"]) == (
        "MENSAL_DIA_FIXO",
        None,
        5,
    )
    assert send(client, "PATCH", f"/rotinas/{r['id']}", {"tipo_agendamento": "DIARIA"}).json()["dia_mes"] is None


def test_rotinas_padrao_idempotente(client):
    r = send(client, "POST", "/rotinas/padrao")
    assert r.status_code == 200 and r.json() == {"created": 13, "skipped": 0}
    assert send(client, "POST", "/rotinas/padrao").json() == {"created": 0, "skipped": 13}
    itens = get(client, "/rotinas").json()
    assert len(itens) == 13
    assert all(i["link_recurso"] is None and i["esforco_estimado_min"] == 0 for i in itens)
    assert [i["ordem"] for i in itens] == sorted(i["ordem"] for i in itens)
    assert len({i["ordem"] for i in itens}) == 13
    assert {i["tipo_agendamento"] for i in itens} == {"SEMANAL", "MENSAL_DIA_FIXO", "MENSAL_ULTIMO_UTIL"}
    assert all("bloco" not in i for i in itens)


def test_semana_expande_ocorrencias(client):
    s = nova_semana(client)
    diaria = nova_rotina(client, "Diária", tipo_agendamento="DIARIA", dia_semana=None, esforco_estimado_min=10)
    quarta = nova_rotina(client, "Quarta", dia_semana="Quarta", categoria="BUILD")
    nova_rotina(client, "Dia 20", tipo_agendamento="MENSAL_DIA_FIXO", dia_semana=None, dia_mes=20)
    nova_rotina(client, "Dia 7", tipo_agendamento="MENSAL_DIA_FIXO", dia_semana=None, dia_mes=7)
    nova_rotina(client, "Futura", inicio_vigencia="2026-02-01")
    v = get(client, f"/rotinas/semana?semana_id={s['id']}&hoje=2026-01-05").json()
    assert v["semana_identificacao"] == "S1" and v["hoje"] == "2026-01-05"
    por_titulo: dict[str, list] = {}
    for o in v["ocorrencias"]:
        por_titulo.setdefault(o["titulo"], []).append(o)
    assert set(por_titulo) == {"Diária", "Quarta", "Dia 7"}
    dias = por_titulo["Diária"]
    assert [o["ocorrencia"] for o in dias] == ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]
    assert [o["data_prevista"] for o in dias][0] == "2026-01-05"
    assert dias[0]["situacao"] == "VENCE_HOJE" and dias[1]["situacao"] == "PREVISTA"
    assert por_titulo["Quarta"][0]["data_prevista"] == "2026-01-07"
    assert por_titulo["Quarta"][0]["ocorrencia"] == "SEMANA" and por_titulo["Quarta"][0]["status"] == "PENDENTE"
    assert por_titulo["Dia 7"][0]["data_prevista"] == "2026-01-07"
    assert v["resumo"]["TOTAL"]["ocorrencias"] == 7 and v["resumo"]["RUN"]["ocorrencias"] == 6
    assert v["resumo"]["BUILD"]["ocorrencias"] == 1
    assert v["resumo"]["RUN"]["minutos_previstos"] == 50
    # Filtros: o resumo considera as ocorrências filtradas.
    f = get(client, f"/rotinas/semana?semana_id={s['id']}&categoria=BUILD&hoje=2026-01-05").json()
    assert [o["titulo"] for o in f["ocorrencias"]] == ["Quarta"] and f["resumo"]["TOTAL"]["ocorrencias"] == 1
    assert executar(client, quarta, s).status_code == 200
    f = get(client, f"/rotinas/semana?semana_id={s['id']}&status=CONCLUIDA").json()
    assert [o["titulo"] for o in f["ocorrencias"]] == ["Quarta"]
    f = get(client, f"/rotinas/semana?semana_id={s['id']}&tipo_agendamento=DIARIA").json()
    assert len(f["ocorrencias"]) == 5 and f["resumo"]["TOTAL"]["minutos_previstos"] == 50
    f = get(client, f"/rotinas/semana?semana_id={s['id']}&tipo_agendamento=mensal").json()
    assert [o["titulo"] for o in f["ocorrencias"]] == ["Dia 7"]
    assert get(client, f"/rotinas/semana?semana_id={s['id']}&tipo_agendamento=xx").status_code == 422
    assert get(client, f"/rotinas/semana?semana_id={uuid4()}").status_code == 404
    assert get(client, "/rotinas/semana").status_code == 422
    assert diaria["id"]


def test_execucao_conclui_com_esforco_real(client):
    s = nova_semana(client)
    d = nova_rotina(client, "Diária", tipo_agendamento="DIARIA", dia_semana=None, esforco_estimado_min=30)
    r = executar(client, d, s, "Segunda", esforco_real_min=45, observacao="ok")
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["status"] == "CONCLUIDA" and o["situacao"] == "CONCLUIDA" and o["esforco_real_min"] == 45
    assert o["concluido_por"] == "user-a" and o["concluido_em"] and o["observacao"] == "ok"
    assert o["esforco_estimado_min"] == 30 and o["data_prevista"] == "2026-01-05"
    # Sem esforço real, vale o estimado.
    assert executar(client, d, s, "Terça").status_code == 200
    resumo = get(client, f"/rotinas/semana?semana_id={s['id']}&hoje=2026-01-05").json()["resumo"]["RUN"]
    assert resumo == {
        "ocorrencias": 5,
        "concluidas": 2,
        "pendentes": 3,
        "minutos_previstos": 150,
        "minutos_executados": 75,
    }
    # Reabrir limpa conclusão e esforço real e mantém a observação.
    r = executar(client, d, s, "Segunda", status="PENDENTE", esforco_real_min=99)
    o = r.json()
    assert o["status"] == "PENDENTE" and o["esforco_real_min"] is None
    assert o["concluido_em"] is None and o["concluido_por"] is None and o["observacao"] == "ok"
    resumo = get(client, f"/rotinas/semana?semana_id={s['id']}&hoje=2026-01-05").json()["resumo"]["TOTAL"]
    assert resumo["concluidas"] == 1 and resumo["minutos_executados"] == 30


def test_execucao_ocorrencia_invalida(client):
    s = nova_semana(client)
    semanal = nova_rotina(client, "Seg", dia_semana="Segunda")
    diaria = nova_rotina(client, "Dia", tipo_agendamento="DIARIA", dia_semana=None)
    mensal = nova_rotina(client, "Mes", tipo_agendamento="MENSAL_DIA_FIXO", dia_semana=None, dia_mes=25)
    futura = nova_rotina(client, "Fut", inicio_vigencia="2026-03-01")
    for rotina, ocorrencia in (
        (semanal, "Terça"),
        (diaria, "SEMANA"),
        (diaria, "Sábado"),
        (mensal, "SEMANA"),
        (futura, "SEMANA"),
        (semanal, "xyz"),
    ):
        assert executar(client, rotina, s, ocorrencia).status_code == 422, (rotina["titulo"], ocorrencia)
    assert executar(client, semanal, s, esforco_real_min=1441).status_code == 422
    assert executar(client, semanal, s, esforco_real_min=-1).status_code == 422
    assert executar(client, semanal, s, status="OUTRO").status_code == 422
    assert get(client, f"/rotinas/semana?semana_id={s['id']}").json()["resumo"]["TOTAL"]["concluidas"] == 0
    outra = {"id": str(uuid4())}
    assert executar(client, outra, s).status_code == 404
    assert executar(client, semanal, {"id": str(uuid4())}).status_code == 404


def test_reset_semana(client):
    s1, s2 = nova_semana(client, "S1"), nova_semana(client, "S2", inicio="2026-01-12", fim="2026-01-18")
    a = nova_rotina(client, "A", dia_semana="Segunda", esforco_estimado_min=20)
    b = nova_rotina(client, "B", dia_semana="Terça", esforco_estimado_min=20)
    executar(client, a, s1, esforco_real_min=50, observacao="nota")
    executar(client, b, s1)
    executar(client, a, s2)
    r = send(client, "POST", "/rotinas/semana/reset", {"semana_id": s1["id"]})
    assert r.status_code == 200 and r.json() == {"reset_count": 2}
    v = get(client, f"/rotinas/semana?semana_id={s1['id']}").json()
    assert v["resumo"]["TOTAL"]["concluidas"] == 0 and v["resumo"]["TOTAL"]["minutos_executados"] == 0
    primeiro = next(o for o in v["ocorrencias"] if o["titulo"] == "A")
    assert primeiro["observacao"] == "nota" and primeiro["esforco_real_min"] is None
    assert primeiro["concluido_em"] is None and primeiro["concluido_por"] is None
    assert get(client, f"/rotinas/semana?semana_id={s2['id']}").json()["resumo"]["TOTAL"]["concluidas"] == 1
    assert send(client, "POST", "/rotinas/semana/reset", {"semana_id": s1["id"]}).json() == {"reset_count": 0}
    assert send(client, "POST", "/rotinas/semana/reset", {"semana_id": str(uuid4())}).status_code == 404


def test_pendencias(client):
    s = nova_semana(client)
    nova_semana(client, "Futura", inicio="2026-02-02", fim="2026-02-08")
    nova_semana(client, "SemDatas", inicio=None, fim=None)
    seg = nova_rotina(client, "Seg", dia_semana="Segunda")
    ter = nova_rotina(client, "Ter", dia_semana="Terça")
    qua = nova_rotina(client, "Qua", dia_semana="Quarta")
    sex = nova_rotina(client, "Sex", dia_semana="Sexta")
    executar(client, ter, s)
    p = get(client, "/rotinas/pendencias?hoje=2026-01-07").json()
    assert p["hoje"] == "2026-01-07"
    assert [(o["titulo"], o["data_prevista"], o["situacao"]) for o in p["vence_hoje"]] == [
        ("Qua", "2026-01-07", "VENCE_HOJE")
    ]
    assert [(o["titulo"], o["situacao"]) for o in p["atrasadas"]] == [("Seg", "ATRASADA")]
    # Concluída sai das pendências; atrasada de semana anterior continua até concluir.
    executar(client, qua, s)
    p = get(client, "/rotinas/pendencias?hoje=2026-01-15").json()
    assert p["vence_hoje"] == []
    assert [o["titulo"] for o in p["atrasadas"]] == ["Seg", "Sex"]
    assert [o["data_prevista"] for o in p["atrasadas"]] == ["2026-01-05", "2026-01-09"]
    executar(client, seg, s)
    assert [o["titulo"] for o in get(client, "/rotinas/pendencias?hoje=2026-01-15").json()["atrasadas"]] == ["Sex"]
    assert get(client, "/rotinas/pendencias?hoje=2026-01-04").json()["atrasadas"] == []
    assert get(client, "/rotinas/pendencias").status_code == 200
    assert sex["id"]


def test_rotina_inativa_permanece_no_historico(client):
    s1, s2 = nova_semana(client, "S1"), nova_semana(client, "S2", inicio="2026-01-12", fim="2026-01-18")
    r = nova_rotina(client, "Velha", esforco_estimado_min=60)
    executar(client, r, s1, esforco_real_min=90)
    send(client, "PATCH", f"/rotinas/{r['id']}", {"ativo": False})
    v1 = get(client, f"/rotinas/semana?semana_id={s1['id']}").json()
    assert [o["titulo"] for o in v1["ocorrencias"]] == ["Velha"]
    assert v1["resumo"]["TOTAL"]["minutos_executados"] == 90
    assert get(client, f"/rotinas/semana?semana_id={s2['id']}").json()["ocorrencias"] == []
    # Inativa sem execução na semana não aceita ocorrência nova.
    assert executar(client, r, s2).status_code == 422
    assert get(client, "/rotinas/pendencias?hoje=2026-02-01").json()["atrasadas"] == []


def test_isolamento_entre_tenants(client):
    s = nova_semana(client)
    r = nova_rotina(client, "Segredo")
    executar(client, r, s)
    for metodo, caminho, corpo in (
        ("GET", f"/rotinas/{r['id']}", None),
        ("PATCH", f"/rotinas/{r['id']}", {"titulo": "x"}),
        ("DELETE", f"/rotinas/{r['id']}", None),
        ("PUT", f"/rotinas/{r['id']}/execucao", {"semana_id": s["id"], "ocorrencia": "SEMANA", "status": "PENDENTE"}),
        ("POST", "/rotinas/semana/reset", {"semana_id": s["id"]}),
    ):
        assert send(client, metodo, caminho, corpo, TENANT_B).status_code == 404, (metodo, caminho)
    assert get(client, f"/rotinas/semana?semana_id={s['id']}", TENANT_B).status_code == 404
    sb = nova_semana(client, "SB", TENANT_B)
    rb = nova_rotina(client, "DeB", TENANT_B, dia_semana="Terça")
    # Rotina de A com semana de B e vice-versa: 404.
    assert executar(client, r, sb, tenant=TENANT_B).status_code == 404
    assert executar(client, rb, s, tenant=TENANT_B).status_code == 404
    assert [x["id"] for x in get(client, "/rotinas", TENANT_B).json()] == [rb["id"]]
    vb = get(client, f"/rotinas/semana?semana_id={sb['id']}", TENANT_B).json()
    assert [o["titulo"] for o in vb["ocorrencias"]] == ["DeB"]
    pb = get(client, "/rotinas/pendencias?hoje=2026-01-20", TENANT_B).json()
    assert [o["titulo"] for o in pb["atrasadas"]] == ["DeB"]
    # Tudo de A segue intacto.
    assert get(client, f"/rotinas/semana?semana_id={s['id']}").json()["resumo"]["TOTAL"]["concluidas"] == 1
    assert send(client, "POST", "/rotinas/padrao", None, TENANT_B).json()["created"] == 13
    assert len(get(client, "/rotinas").json()) == 1
    assert nova_rotina(client, "DeB", TENANT_A)["titulo"] == "DeB"


def test_leitor_nao_escreve(client, grants):
    s = nova_semana(client)
    r = nova_rotina(client)
    grants[TENANT_A] = {"access", "read"}
    assert get(client, "/rotinas").status_code == 200
    assert get(client, f"/rotinas/semana?semana_id={s['id']}").status_code == 200
    assert get(client, "/rotinas/pendencias").status_code == 200
    escritas = (
        ("POST", "/rotinas", {"titulo": "X", "dia_semana": "Segunda"}),
        ("POST", "/rotinas/padrao", None),
        ("PATCH", f"/rotinas/{r['id']}", {"titulo": "Y"}),
        ("DELETE", f"/rotinas/{r['id']}", None),
        ("PUT", f"/rotinas/{r['id']}/execucao", {"semana_id": s["id"], "ocorrencia": "SEMANA", "status": "CONCLUIDA"}),
        ("POST", "/rotinas/semana/reset", {"semana_id": s["id"]}),
    )
    for metodo, caminho, corpo in escritas:
        assert send(client, metodo, caminho, corpo).status_code == 403, (metodo, caminho)
    assert len(get(client, "/rotinas").json()) == 1


def test_cascata_ao_excluir_rotina_ou_semana(client):
    s1, s2 = nova_semana(client, "S1"), nova_semana(client, "S2", inicio="2026-01-12", fim="2026-01-18")
    a, b = nova_rotina(client, "A"), nova_rotina(client, "B", dia_semana="Terça")
    for rotina in (a, b):
        executar(client, rotina, s1)
        executar(client, rotina, s2)
    assert send(client, "DELETE", f"/rotinas/{a['id']}").status_code == 204
    v = get(client, f"/rotinas/semana?semana_id={s1['id']}").json()
    assert [o["titulo"] for o in v["ocorrencias"]] == ["B"]
    assert send(client, "DELETE", f"/semanas/{s1['id']}").status_code == 204
    assert get(client, f"/rotinas/semana?semana_id={s1['id']}").status_code == 404
    v2 = get(client, f"/rotinas/semana?semana_id={s2['id']}").json()
    assert [(o["titulo"], o["status"]) for o in v2["ocorrencias"]] == [("B", "CONCLUIDA")]
    # Recriar a rotina não ressuscita execuções antigas.
    a2 = nova_rotina(client, "A")
    assert get(client, f"/rotinas/semana?semana_id={s2['id']}").json()["resumo"]["TOTAL"]["concluidas"] == 1
    assert a2["id"] != a["id"]


def test_escrita_exige_csrf(client):
    corpo = {"titulo": "X", "dia_semana": "Segunda"}
    r = client.post(P + "/rotinas", json=corpo, headers={"X-Tenant-ID": str(TENANT_A), "Origin": settings.PUBLIC_URL})
    assert r.status_code == 403

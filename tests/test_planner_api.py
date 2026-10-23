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
API = "/api/v1"
P = "/api/v1/planner"
D1, D2, D3 = "2026-01-05", "2026-01-06", "2026-01-07"


@pytest.fixture
def grants():
    return {TENANT_A: {"access", "read", "write"}, TENANT_B: {"access", "read", "write"}}


@pytest.fixture
def who():
    return {"sub": "user-a"}


@pytest.fixture
def client(monkeypatch, tmp_path, grants, who):
    engine = create_engine(f"sqlite:///{tmp_path / 'plan.sqlite3'}", connect_args={"check_same_thread": False})

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


def item(c, dia, texto="Fazer", tipo="TAREFA", tenant=TENANT_A, **extra):
    r = send(c, "POST", f"/dias/{dia}/itens", {"tipo": tipo, "texto": texto, **extra}, tenant)
    assert r.status_code == 201, r.text
    return r.json()


def dia(c, data, tenant=TENANT_A):
    r = get(c, f"/meu-dia?data={data}", tenant)
    assert r.status_code == 200, r.text
    return r.json()


# --- leitura sem efeito colateral ---------------------------------------------------------------------------------


def test_get_nao_cria_dia(client):
    v = dia(client, D1)
    assert v["data"] == D1 and v["dia"] == {"id": None, "foco": None, "notas": None, "versao": 0, "updated_at": None}
    assert v["prioridades"] == [] and v["tarefas"] == [] and v["pendentes_anteriores"] == []
    assert v["rotinas"] == {"vence_hoje": [], "atrasadas": []} and v["renovacoes"] == []
    assert v["resumo"] == {"itens_total": 0, "itens_concluidos": 0, "prioridades_concluidas": 0, "rotinas_pendentes": 0}
    assert get(client, "/dias?de=2026-01-01&ate=2026-01-31").json() == []
    assert get(client, "/meu-dia").status_code == 200 and get(client, "/dias").json() == []


def test_datas_invalidas(client):
    assert get(client, "/meu-dia?data=2026-13-40").status_code == 422
    assert send(client, "PUT", "/dias/nao-e-data", {"versao": 0}).status_code == 422
    assert send(client, "POST", "/dias/2026-02-30/itens", {"tipo": "TAREFA", "texto": "x"}).status_code == 422
    assert get(client, "/dias?de=2026-01-01&ate=2027-01-02").status_code == 422
    assert get(client, "/dias?de=2026-01-01&ate=2027-01-01").status_code == 200
    assert get(client, "/dias?de=2026-02-01&ate=2026-01-01").status_code == 422


# --- dia: foco, notas e versão otimista ---------------------------------------------------------------------------


def test_dia_versao_otimista(client):
    r = send(client, "PUT", f"/dias/{D1}", {"foco": "  Entregar  ", "notas": "n1", "versao": 0})
    assert r.status_code == 200
    assert (r.json()["foco"], r.json()["notas"], r.json()["versao"]) == ("Entregar", "n1", 2)
    assert r.json()["id"] and r.json()["updated_at"]
    velha = send(client, "PUT", f"/dias/{D1}", {"foco": "x", "versao": 1})
    assert velha.status_code == 409 and velha.json()["detail"]["versao_atual"] == 2
    assert send(client, "PUT", f"/dias/{D1}", {"foco": "x", "versao": 0}).status_code == 409
    # campos ausentes não são alterados; null limpa.
    r = send(client, "PUT", f"/dias/{D1}", {"notas": "n2", "versao": 2})
    assert (r.json()["foco"], r.json()["notas"], r.json()["versao"]) == ("Entregar", "n2", 3)
    r = send(client, "PUT", f"/dias/{D1}", {"foco": None, "versao": 3})
    assert r.json()["foco"] is None and r.json()["notas"] == "n2"
    assert dia(client, D1)["dia"]["versao"] == 4
    # versão ausente vale 0 só para dia inexistente.
    assert send(client, "PUT", f"/dias/{D2}", {"foco": "novo"}).status_code == 200
    assert send(client, "PUT", f"/dias/{D2}", {"foco": "outro"}).status_code == 409
    assert send(client, "PUT", f"/dias/{D3}", {"notas": "x" * 20_001, "versao": 0}).status_code == 422
    assert send(client, "PUT", f"/dias/{D3}", {"foco": "x" * 501, "versao": 0}).status_code == 422
    assert send(client, "PUT", f"/dias/{D3}", {"versao": 0, "sub": "outro"}).status_code == 422
    assert send(client, "PUT", f"/dias/{D3}", {"versao": 0, "tenant_id": str(TENANT_B)}).status_code == 422


def test_remover_dia(client):
    i = item(client, D1)
    assert send(client, "DELETE", f"/dias/{D1}").status_code == 204
    assert dia(client, D1)["tarefas"] == []
    assert send(client, "PATCH", f"/itens/{i['id']}", {"texto": "x"}).status_code == 404
    assert send(client, "DELETE", f"/dias/{D1}").status_code == 404


# --- itens --------------------------------------------------------------------------------------------------------


def test_item_crud_e_conclusao(client):
    a = item(client, D1, "A")
    b = item(client, D1, "B", concluido=True)
    p = item(client, D1, "P", "prioridade")
    assert a["tipo"] == "TAREFA" and a["concluido"] is False and a["concluido_em"] is None and a["ordem"] == 0
    assert a["origem_item_id"] is None and "sub" not in a and "tenant_id" not in a
    assert b["ordem"] == 1 and b["concluido"] is True and b["concluido_em"]
    assert p["tipo"] == "PRIORIDADE" and p["ordem"] == 0
    v = dia(client, D1)
    assert [x["texto"] for x in v["tarefas"]] == ["A", "B"] and [x["texto"] for x in v["prioridades"]] == ["P"]
    assert v["resumo"] == {"itens_total": 3, "itens_concluidos": 1, "prioridades_concluidas": 0, "rotinas_pendentes": 0}
    r = send(client, "PATCH", f"/itens/{a['id']}", {"concluido": True, "texto": "  A2 "})
    assert r.status_code == 200 and r.json()["texto"] == "A2" and r.json()["concluido_em"]
    r = send(client, "PATCH", f"/itens/{a['id']}", {"concluido": False})
    assert r.json()["concluido"] is False and r.json()["concluido_em"] is None
    r = send(client, "PATCH", f"/itens/{a['id']}", {"ordem": 5})
    assert r.json()["ordem"] == 5
    assert [x["texto"] for x in dia(client, D1)["tarefas"]] == ["B", "A2"]
    # promover para prioridade e voltar.
    r = send(client, "PATCH", f"/itens/{a['id']}", {"tipo": "prioridade"})
    assert r.json()["tipo"] == "PRIORIDADE"
    assert dia(client, D1)["resumo"]["itens_total"] == 3
    # validações.
    assert send(client, "PATCH", f"/itens/{a['id']}", {"texto": ""}).status_code == 422
    assert send(client, "PATCH", f"/itens/{a['id']}", {"texto": None}).status_code == 422
    assert send(client, "PATCH", f"/itens/{a['id']}", {"tipo": "OUTRO"}).status_code == 422
    assert send(client, "PATCH", f"/itens/{a['id']}", {"sub": "x"}).status_code == 422
    assert send(client, "POST", f"/dias/{D1}/itens", {"tipo": "TAREFA", "texto": "x" * 501}).status_code == 422
    assert send(client, "POST", f"/dias/{D1}/itens", {"tipo": "TAREFA", "texto": "   "}).status_code == 422
    assert send(client, "POST", f"/dias/{D1}/itens", {"tipo": "X", "texto": "a"}).status_code == 422
    assert send(client, "DELETE", f"/itens/{a['id']}").status_code == 204
    assert send(client, "DELETE", f"/itens/{a['id']}").status_code == 404
    assert send(client, "PATCH", f"/itens/{uuid4()}", {"texto": "x"}).status_code == 404


def test_limite_de_tres_prioridades(client):
    ps = [item(client, D1, f"P{n}", "PRIORIDADE") for n in range(3)]
    r = send(client, "POST", f"/dias/{D1}/itens", {"tipo": "PRIORIDADE", "texto": "P4"})
    assert r.status_code == 422
    t = item(client, D1, "T")
    assert send(client, "PATCH", f"/itens/{t['id']}", {"tipo": "PRIORIDADE"}).status_code == 422
    # outro dia tem seu próprio limite; editar prioridade existente continua permitido.
    item(client, D2, "P", "PRIORIDADE")
    assert send(client, "PATCH", f"/itens/{ps[0]['id']}", {"texto": "novo", "tipo": "PRIORIDADE"}).status_code == 200
    # liberar uma vaga permite a próxima.
    assert send(client, "DELETE", f"/itens/{ps[1]['id']}").status_code == 204
    assert send(client, "PATCH", f"/itens/{t['id']}", {"tipo": "PRIORIDADE"}).status_code == 200
    assert len(dia(client, D1)["prioridades"]) == 3


def test_limite_de_itens_por_dia(client):
    for n in range(200):
        r = send(client, "POST", f"/dias/{D1}/itens", {"tipo": "TAREFA", "texto": f"t{n}"})
        assert r.status_code == 201
    assert send(client, "POST", f"/dias/{D1}/itens", {"tipo": "TAREFA", "texto": "extra"}).status_code == 422


# --- pendentes de dias anteriores ----------------------------------------------------------------------------------


def test_pendentes_e_trazer(client):
    p1 = item(client, D1, "P1", "PRIORIDADE")
    t1 = item(client, D1, "T1")
    item(client, D1, "Feita", concluido=True)
    t2 = item(client, D2, "T2")
    v = dia(client, D3)
    assert [(x["texto"], x["data_origem"]) for x in v["pendentes_anteriores"]] == [
        ("T2", D2),
        ("P1", D1),
        ("T1", D1),
    ]
    assert dia(client, D1)["pendentes_anteriores"] == []
    assert [x["texto"] for x in dia(client, D2)["pendentes_anteriores"]] == ["P1", "T1"]
    # trazer selecionados.
    r = send(client, "POST", f"/dias/{D3}/trazer-pendentes", {"item_ids": [p1["id"], t2["id"]]})
    assert r.status_code == 200 and r.json() == {"trazidos": 2, "como_tarefa": 0}
    v = dia(client, D3)
    assert [x["texto"] for x in v["prioridades"]] == ["P1"] and [x["texto"] for x in v["tarefas"]] == ["T2"]
    assert v["prioridades"][0]["origem_item_id"] == p1["id"] and v["prioridades"][0]["id"] != p1["id"]
    assert [x["texto"] for x in v["pendentes_anteriores"]] == ["T1"]
    # o original migrado não é mais pendente e não pode ser trazido de novo.
    assert send(client, "POST", f"/dias/{D3}/trazer-pendentes", {"item_ids": [p1["id"]]}).status_code == 409
    # item de hoje ou concluído não é pendente anterior.
    hoje_item = v["tarefas"][0]
    assert send(client, "POST", f"/dias/{D3}/trazer-pendentes", {"item_ids": [hoje_item["id"]]}).status_code == 409
    # um item inválido na lista não altera nada (atômico).
    r = send(client, "POST", f"/dias/{D3}/trazer-pendentes", {"item_ids": [t1["id"], p1["id"]]})
    assert r.status_code == 409 and len(dia(client, D3)["pendentes_anteriores"]) == 1
    assert send(client, "POST", f"/dias/{D3}/trazer-pendentes", {"item_ids": [str(uuid4())]}).status_code == 404
    # sem lista: traz todos os restantes. Corpo ausente também vale.
    r = send(client, "POST", f"/dias/{D3}/trazer-pendentes")
    assert r.json() == {"trazidos": 1, "como_tarefa": 0}
    assert dia(client, D3)["pendentes_anteriores"] == []
    assert send(client, "POST", f"/dias/{D3}/trazer-pendentes", {}).json() == {"trazidos": 0, "como_tarefa": 0}
    # dia anterior continua consultável com o item original.
    assert [x["texto"] for x in dia(client, D1)["tarefas"]] == ["T1", "Feita"]


def test_trazer_sem_pendentes_nao_cria_dia(client):
    assert send(client, "POST", f"/dias/{D3}/trazer-pendentes", {}).json() == {"trazidos": 0, "como_tarefa": 0}
    assert dia(client, D3)["dia"]["id"] is None


def test_trazer_prioridade_vira_tarefa_com_tres_prioridades(client):
    antigas = [item(client, D1, f"A{n}", "PRIORIDADE") for n in range(3)]
    for n in range(2):
        item(client, D3, f"H{n}", "PRIORIDADE")
    r = send(client, "POST", f"/dias/{D3}/trazer-pendentes", {"item_ids": [x["id"] for x in antigas]})
    assert r.json() == {"trazidos": 3, "como_tarefa": 2}
    v = dia(client, D3)
    assert len(v["prioridades"]) == 3 and [x["texto"] for x in v["prioridades"]] == ["H0", "H1", "A0"]
    assert [x["texto"] for x in v["tarefas"]] == ["A1", "A2"]
    assert all(x["origem_item_id"] for x in v["tarefas"])


def test_descartar_pendentes(client):
    a = item(client, D1, "A")
    b = item(client, D1, "B")
    assert send(client, "POST", f"/dias/{D2}/descartar-pendentes", {"item_ids": []}).status_code == 422
    assert send(client, "POST", f"/dias/{D2}/descartar-pendentes", {}).status_code == 422
    r = send(client, "POST", f"/dias/{D2}/descartar-pendentes", {"item_ids": [a["id"]]})
    assert r.status_code == 200 and r.json() == {"descartados": 1}
    assert [x["texto"] for x in dia(client, D2)["pendentes_anteriores"]] == ["B"]
    assert dia(client, D2)["dia"]["id"] is None  # descartar não cria o dia
    assert send(client, "POST", f"/dias/{D2}/descartar-pendentes", {"item_ids": [a["id"]]}).status_code == 409
    assert send(client, "POST", f"/dias/{D2}/descartar-pendentes", {"item_ids": [str(uuid4())]}).status_code == 404
    send(client, "PATCH", f"/itens/{b['id']}", {"concluido": True})
    assert send(client, "POST", f"/dias/{D2}/descartar-pendentes", {"item_ids": [b["id"]]}).status_code == 409
    assert dia(client, D3)["pendentes_anteriores"] == []


# --- histórico ----------------------------------------------------------------------------------------------------


def test_historico(client):
    item(client, D1, "A")
    item(client, D1, "B", concluido=True)
    send(client, "PUT", f"/dias/{D2}", {"foco": "Foco 2", "versao": 0})
    item(client, "2025-06-01", "velho")
    r = get(client, "/dias?de=2026-01-01&ate=2026-01-31")
    assert r.json() == [
        {"data": D2, "foco": "Foco 2", "itens_total": 0, "itens_concluidos": 0},
        {"data": D1, "foco": None, "itens_total": 2, "itens_concluidos": 1},
    ]
    assert len(get(client, "/dias?de=2025-05-01&ate=2026-01-31").json()) == 3
    hoje = date.today()
    item(client, hoje.isoformat(), "hoje")
    item(client, (hoje - timedelta(days=29)).isoformat(), "limite")
    item(client, (hoje - timedelta(days=30)).isoformat(), "fora")
    assert len(get(client, "/dias").json()) == 2


# --- integração com Rotinas e Despesas -----------------------------------------------------------------------------


def test_rotinas_e_renovacoes_no_meu_dia(client):
    def rot(titulo, dia_semana):
        corpo = {
            "titulo": titulo,
            "tipo_agendamento": "SEMANAL",
            "dia_semana": dia_semana,
            "inicio_vigencia": "2026-01-01",
        }
        r = send(client, "POST", "/rotinas", corpo, base=API)
        assert r.status_code == 201, r.text
        return r.json()

    semana = send(
        client, "POST", "/semanas", {"identificacao": "S1", "data_inicio": D1, "data_fim": "2026-01-11"}, base=API
    ).json()
    rot("Seg", "Segunda")
    qua = rot("Qua", "Quarta")
    rot("Sex", "Sexta")
    v = dia(client, "2026-01-07")
    assert [o["titulo"] for o in v["rotinas"]["vence_hoje"]] == ["Qua"]
    assert [o["titulo"] for o in v["rotinas"]["atrasadas"]] == ["Seg"]
    assert v["rotinas"]["vence_hoje"][0]["semana_id"] == semana["id"] and v["resumo"]["rotinas_pendentes"] == 2
    # concluir pela API de Rotinas tira do Meu Dia.
    corpo = {"semana_id": semana["id"], "ocorrencia": "SEMANA", "status": "CONCLUIDA"}
    assert send(client, "PUT", f"/rotinas/{qua['id']}/execucao", corpo, base=API).status_code == 200
    v = dia(client, "2026-01-07")
    assert v["rotinas"]["vence_hoje"] == [] and v["resumo"]["rotinas_pendentes"] == 1

    def desp(nome, renovacao, **extra):
        corpo = {"nome": nome, "categoria": "SaaS", "tipo_custo": "RECORRENTE_MENSAL", "valor": 100}
        corpo.update({"data_renovacao": renovacao, **extra})
        r = send(client, "POST", "", corpo, base=API + "/despesas")
        assert r.status_code == 201, r.text

    desp("Perto", "2026-01-20", fornecedor="Acme")
    desp("Hoje", "2026-01-07", valor=250)
    desp("Longe", "2026-03-01")
    desp("Passado", "2026-01-01")
    desp("Cancelada", "2026-01-10", status_auditoria="EM_REVISAO")
    cancelada = get(client, "", base=API + "/despesas").json()
    cancelada = next(d for d in cancelada if d["nome"] == "Cancelada")
    r = send(client, "POST", f"/{cancelada['id']}/cancelar", {"mes": "2026-01"}, base=API + "/despesas")
    assert r.status_code == 200, r.text
    v = dia(client, "2026-01-07")
    achados = [(r["nome"], r["dias"], r["custo_mensal"]) for r in v["renovacoes"]]
    assert achados == [("Hoje", 0, 250.0), ("Perto", 13, 100.0)]
    assert v["renovacoes"][1]["fornecedor"] == "Acme" and v["renovacoes"][1]["data_renovacao"] == "2026-01-20"
    assert set(v["renovacoes"][0]) == {"id", "nome", "fornecedor", "data_renovacao", "dias", "custo_mensal"}


# --- isolamento ---------------------------------------------------------------------------------------------------


def test_isolamento_entre_pessoas_do_mesmo_tenant(client, who):
    a_prio = item(client, D1, "Minha", "PRIORIDADE")
    a_tarefa = item(client, D1, "Tarefa A")
    send(client, "PUT", f"/dias/{D1}", {"foco": "foco A", "notas": "segredo", "versao": 1})
    who["sub"] = "user-b"
    v = dia(client, D1)
    assert v["dia"]["id"] is None and v["dia"]["foco"] is None and v["prioridades"] == [] and v["tarefas"] == []
    assert dia(client, D3)["pendentes_anteriores"] == []
    assert get(client, "/dias?de=2026-01-01&ate=2026-01-31").json() == []
    # item e dia de A são 404 para B (nunca 403/200).
    assert send(client, "PATCH", f"/itens/{a_tarefa['id']}", {"concluido": True}).status_code == 404
    assert send(client, "DELETE", f"/itens/{a_tarefa['id']}").status_code == 404
    assert send(client, "POST", f"/dias/{D3}/trazer-pendentes", {"item_ids": [a_tarefa["id"]]}).status_code == 404
    assert send(client, "POST", f"/dias/{D3}/descartar-pendentes", {"item_ids": [a_prio["id"]]}).status_code == 404
    assert send(client, "DELETE", f"/dias/{D1}").status_code == 404
    # B escreve no mesmo dia sem colidir com A.
    b = item(client, D1, "Tarefa B")
    assert send(client, "PUT", f"/dias/{D1}", {"foco": "foco B", "versao": 1}).json()["foco"] == "foco B"
    assert [x["texto"] for x in dia(client, D1)["tarefas"]] == ["Tarefa B"]
    # B pode ter suas 3 prioridades independentemente de A.
    for n in range(3):
        item(client, D1, f"BP{n}", "PRIORIDADE")
    who["sub"] = "user-a"
    v = dia(client, D1)
    assert [x["texto"] for x in v["tarefas"]] == ["Tarefa A"] and [x["texto"] for x in v["prioridades"]] == ["Minha"]
    assert v["dia"]["foco"] == "foco A" and v["dia"]["notas"] == "segredo" and v["dia"]["versao"] == 2
    assert send(client, "PATCH", f"/itens/{b['id']}", {"texto": "invadido"}).status_code == 404
    assert len(get(client, "/dias?de=2026-01-01&ate=2026-01-31").json()) == 1


def test_isolamento_entre_tenants(client):
    i = item(client, D1, "A")
    send(client, "PUT", f"/dias/{D1}", {"foco": "foco", "versao": 0})
    v = dia(client, D1, TENANT_B)
    assert v["dia"]["id"] is None and v["tarefas"] == [] and v["prioridades"] == []
    assert get(client, "/dias?de=2026-01-01&ate=2026-01-31", TENANT_B).json() == []
    assert send(client, "PATCH", f"/itens/{i['id']}", {"concluido": True}, TENANT_B).status_code == 404
    assert send(client, "DELETE", f"/itens/{i['id']}", tenant=TENANT_B).status_code == 404
    assert send(client, "DELETE", f"/dias/{D1}", tenant=TENANT_B).status_code == 404
    assert send(client, "POST", f"/dias/{D3}/trazer-pendentes", {"item_ids": [i["id"]]}, TENANT_B).status_code == 404
    assert dia(client, D1)["tarefas"][0]["texto"] == "A"


# --- permissões ---------------------------------------------------------------------------------------------------


def test_leitor_sem_write(client, grants):
    i = item(client, D1, "A")
    grants[TENANT_A] = {"access", "read"}
    assert get(client, f"/meu-dia?data={D1}").status_code == 200
    assert get(client, "/dias").status_code == 200
    escritas = [
        ("PUT", f"/dias/{D1}", {"versao": 0}),
        ("DELETE", f"/dias/{D1}", None),
        ("POST", f"/dias/{D1}/itens", {"tipo": "TAREFA", "texto": "x"}),
        ("PATCH", f"/itens/{i['id']}", {"texto": "x"}),
        ("DELETE", f"/itens/{i['id']}", None),
        ("POST", f"/dias/{D2}/trazer-pendentes", {}),
        ("POST", f"/dias/{D2}/descartar-pendentes", {"item_ids": [i["id"]]}),
    ]
    for metodo, caminho, corpo in escritas:
        assert send(client, metodo, caminho, corpo).status_code == 403, (metodo, caminho)
    grants[TENANT_A] = {"access", "read", "write"}
    assert dia(client, D1)["tarefas"][0]["texto"] == "A"


def test_sem_acesso_ao_tenant(client):
    assert get(client, f"/meu-dia?data={D1}", uuid4()).status_code == 403

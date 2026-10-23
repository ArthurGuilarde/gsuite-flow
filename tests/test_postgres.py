from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.integration


def context(db, tenant):
    db.execute(text("SELECT set_config('app.tenant_id', :tenant, true)"), {"tenant": str(tenant)})


def insert(db, tenant, title="test"):
    db.execute(
        text("INSERT INTO tenant_test_records(id,tenant_id,created_by,title) VALUES (:id,:tenant,'user',:title)"),
        {"id": uuid4(), "tenant": tenant, "title": title},
    )


def test_rls_unfiltered_query_and_pool_reset(db_factory):
    a, b = uuid4(), uuid4()
    for tenant in [a, b]:
        with db_factory.begin() as db:
            context(db, tenant)
            insert(db, tenant)
    with db_factory.begin() as db:
        context(db, a)
        assert db.execute(text("SELECT tenant_id FROM tenant_test_records")).scalars().all() == [a]
    with db_factory.begin() as db:
        assert db.execute(text("SELECT count(*) FROM tenant_test_records")).scalar() == 0
        context(db, b)
        assert db.execute(text("SELECT tenant_id FROM tenant_test_records")).scalars().all() == [b]


def test_rls_insert_mismatch_denied(db_factory):
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, uuid4())
        insert(db, uuid4())


def test_rls_update_and_delete_denied(db_factory):
    a, b = uuid4(), uuid4()
    with db_factory.begin() as db:
        context(db, a)
        insert(db, a)
    with db_factory.begin() as db:
        context(db, b)
        assert db.execute(text("UPDATE tenant_test_records SET title='stolen'")).rowcount == 0
        assert db.execute(text("DELETE FROM tenant_test_records")).rowcount == 0
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, a)
        db.execute(text("UPDATE tenant_test_records SET tenant_id=:b"), {"b": b})


def test_runtime_privileges(db_factory):
    with db_factory.begin() as db:
        row = db.execute(text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")).one()
        assert not row.rolsuper and not row.rolbypassrls
        assert (
            db.execute(
                text("SELECT tableowner=current_user FROM pg_tables WHERE tablename='tenant_test_records'")
            ).scalar()
            is False
        )
        assert (
            db.execute(
                text("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname='tenant_test_records'")
            ).scalar()
            is True
        )
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        db.execute(text("ALTER TABLE tenant_test_records DISABLE ROW LEVEL SECURITY"))


def test_shared_family_and_rollback(db_factory):
    a = uuid4()
    with db_factory.begin() as db:
        context(db, a)
        insert(db, a)
    with db_factory.begin() as db:
        context(db, a)
        db.execute(text("SELECT set_config('app.subject','other-member',true)"))
        assert db.execute(text("SELECT count(*) FROM tenant_test_records")).scalar() == 1
    with pytest.raises(RuntimeError), db_factory.begin() as db:
        context(db, a)
        insert(db, a)
        raise RuntimeError("rollback")
    with db_factory.begin() as db:
        context(db, a)
        assert db.execute(text("SELECT count(*) FROM tenant_test_records")).scalar() == 1


def test_api_authorized_flow(db_factory, monkeypatch):
    from fastapi.testclient import TestClient

    from src.backend.api import deps
    from src.backend.core import sessions
    from src.backend.core.config import settings
    from src.backend.integrations.guilarde.contracts import Authorization, Principal
    from tests.support.tenant_example import create_test_app

    a = uuid4()
    monkeypatch.setattr(deps, "SessionLocal", db_factory)
    monkeypatch.setattr(sessions, "load_session", lambda _sid: {"access_token": "test", "csrf": "csrf"})
    monkeypatch.setattr(deps, "validate_access_token", lambda _token: Principal(sub="member-one"))

    async def authorize(token, tenant, permission):
        return Authorization(
            sub="member-one",
            tenant_id=tenant,
            app_id=settings.APP_ID,
            allowed=tenant == a,
            permissions={"access", "read", "write"},
        )

    monkeypatch.setattr(deps.core_client, "authorize", authorize)
    client = TestClient(create_test_app())
    client.cookies.set(settings.SESSION_COOKIE, "a" * 43)
    headers = {"X-Tenant-ID": str(a), "X-CSRF-Token": "csrf", "Origin": settings.PUBLIC_URL}
    created = client.post("/api/v1/test-records", json={"title": "shared"}, headers=headers)
    assert created.status_code == 201
    assert client.get("/api/v1/test-records", headers=headers).json()[0]["title"] == "shared"
    assert client.get("/api/v1/test-records", headers={"X-Tenant-ID": str(uuid4())}).status_code == 403


def test_session_storage_encryption_rotation_and_expiry(db_factory, monkeypatch):
    from datetime import UTC, datetime, timedelta

    from src.backend.core import sessions
    from src.backend.models.session import BrowserSession

    monkeypatch.setattr(sessions, "SessionLocal", db_factory)
    sid = "a" * 43
    sessions.save_session(sid, {"access_token": "secret-bearer", "csrf": "secret-csrf"})
    with db_factory.begin() as db:
        row = db.get(BrowserSession, sessions.session_hash(sid))
        assert row and row.id != sid and "secret-bearer" not in row.payload
    assert sessions.load_session(sid)["access_token"] == "secret-bearer"
    next_sid = "b" * 43
    sessions.save_session(next_sid, {"access_token": "second"}, old_sid=sid)
    assert sessions.load_session(sid) == {}
    with db_factory.begin() as db:
        row = db.get(BrowserSession, sessions.session_hash(next_sid))
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert sessions.load_session(next_sid) == {}
    sessions.save_session(next_sid, {})
    assert sessions.load_session(next_sid) == {}


def test_runtime_startup_and_health(db_factory, postgres, monkeypatch):
    from fastapi.testclient import TestClient

    from src.backend import main

    monkeypatch.setattr(main, "engine", db_factory.kw["bind"])
    with TestClient(main.app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        assert client.get("/").status_code == 200
    monkeypatch.setattr(main, "engine", postgres[0])
    with pytest.raises(RuntimeError, match="Runtime role"):
        with TestClient(main.app):
            pass


CAPACIDADE_TABLES = ("grupos", "semanas", "lancamentos")


def add_grupo(db, tenant, nome="Projetos", categoria="BUILD", grupo_id=None):
    grupo_id = grupo_id or uuid4()
    db.execute(
        text("INSERT INTO grupos(id,tenant_id,created_by,nome,categoria) VALUES (:id,:tenant,'user',:nome,:categoria)"),
        {"id": grupo_id, "tenant": tenant, "nome": nome, "categoria": categoria},
    )
    return grupo_id


def add_semana(db, tenant, identificacao="S01"):
    semana_id = uuid4()
    db.execute(
        text("INSERT INTO semanas(id,tenant_id,created_by,identificacao) VALUES (:id,:tenant,'user',:ident)"),
        {"id": semana_id, "tenant": tenant, "ident": identificacao},
    )
    return semana_id


def add_lancamento(db, tenant, grupo_id, semana_id, status="ABERTO"):
    lancamento_id = uuid4()
    db.execute(
        text(
            "INSERT INTO lancamentos(id,tenant_id,created_by,grupo_id,semana_id,status) "
            "VALUES (:id,:tenant,'user',:grupo,:semana,:status)"
        ),
        {"id": lancamento_id, "tenant": tenant, "grupo": grupo_id, "semana": semana_id, "status": status},
    )
    return lancamento_id


def seed_capacidade(db, tenant, sufixo="1"):
    context(db, tenant)
    grupo = add_grupo(db, tenant, nome=f"Grupo {sufixo}")
    semana = add_semana(db, tenant, identificacao=f"S{sufixo}")
    return grupo, semana, add_lancamento(db, tenant, grupo, semana)


def test_capacidade_tables_force_rls_and_not_owned_by_runtime(db_factory):
    with db_factory.begin() as db:
        for table in CAPACIDADE_TABLES:
            flags = db.execute(
                text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname=:t"), {"t": table}
            ).one()
            assert tuple(flags) == (True, True), table
            owned = db.execute(
                text("SELECT tableowner=current_user FROM pg_tables WHERE tablename=:t"), {"t": table}
            ).scalar()
            assert owned is False, table
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        db.execute(text("ALTER TABLE grupos DISABLE ROW LEVEL SECURITY"))


def test_capacidade_unfiltered_select_sees_only_current_tenant(db_factory):
    a, b = uuid4(), uuid4()
    for tenant, sufixo in [(a, "A"), (b, "B")]:
        with db_factory.begin() as db:
            seed_capacidade(db, tenant, sufixo)
    with db_factory.begin() as db:
        context(db, a)
        for table in CAPACIDADE_TABLES:
            assert db.execute(text(f"SELECT tenant_id FROM {table}")).scalars().all() == [a], table  # noqa: S608
    with db_factory.begin() as db:
        for table in CAPACIDADE_TABLES:
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0, table  # noqa: S608


def test_capacidade_insert_with_other_tenant_denied(db_factory):
    for insert_row in (
        lambda db, other: add_grupo(db, other),
        lambda db, other: add_semana(db, other),
    ):
        with pytest.raises(DBAPIError), db_factory.begin() as db:
            context(db, uuid4())
            insert_row(db, uuid4())


def test_capacidade_update_and_delete_other_tenant_affect_zero_rows(db_factory):
    a, b = uuid4(), uuid4()
    with db_factory.begin() as db:
        seed_capacidade(db, a)
    with db_factory.begin() as db:
        context(db, b)
        assert db.execute(text("UPDATE grupos SET nome='roubado'")).rowcount == 0
        assert db.execute(text("UPDATE semanas SET identificacao='roubada'")).rowcount == 0
        assert db.execute(text("UPDATE lancamentos SET quantidade=99")).rowcount == 0
        for table in reversed(CAPACIDADE_TABLES):
            assert db.execute(text(f"DELETE FROM {table}")).rowcount == 0, table  # noqa: S608
    with db_factory.begin() as db:
        context(db, a)
        assert db.execute(text("SELECT nome FROM grupos")).scalars().all() == ["Grupo 1"]
        assert db.execute(text("SELECT quantidade FROM lancamentos")).scalars().all() == [0]


def test_capacidade_composite_fk_blocks_cross_tenant_lancamento(db_factory):
    a, b = uuid4(), uuid4()
    with db_factory.begin() as db:
        grupo_a, semana_a, _ = seed_capacidade(db, a, "A")
    with db_factory.begin() as db:
        context(db, b)
        grupo_b = add_grupo(db, b, nome="Grupo B")
        semana_b = add_semana(db, b, "SB")
    cases = [(grupo_a, semana_b), (grupo_b, semana_a), (grupo_a, semana_a)]
    for grupo, semana in cases:
        with pytest.raises(DBAPIError), db_factory.begin() as db:
            context(db, b)
            add_lancamento(db, b, grupo, semana)


def test_capacidade_group_delete_cascades_to_lancamentos(db_factory):
    a = uuid4()
    with db_factory.begin() as db:
        grupo, semana, _ = seed_capacidade(db, a)
        add_lancamento(db, a, grupo, semana, status="RESOLVIDO")
    with db_factory.begin() as db:
        context(db, a)
        assert db.execute(text("SELECT count(*) FROM lancamentos")).scalar() == 2
        assert db.execute(text("DELETE FROM grupos WHERE id=:id"), {"id": grupo}).rowcount == 1
        assert db.execute(text("SELECT count(*) FROM lancamentos")).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM semanas")).scalar() == 1


ROTINAS_TABLES = ("rotinas", "rotina_execucoes")


def add_rotina(db, tenant, titulo="Triagem", rotina_id=None):
    rotina_id = rotina_id or uuid4()
    db.execute(
        text(
            "INSERT INTO rotinas(id,tenant_id,created_by,titulo,tipo_agendamento,dia_semana,inicio_vigencia) "
            "VALUES (:id,:tenant,'user',:titulo,'SEMANAL','Segunda','2026-01-01')"
        ),
        {"id": rotina_id, "tenant": tenant, "titulo": titulo},
    )
    return rotina_id


def add_execucao(db, tenant, rotina_id, semana_id, ocorrencia="SEMANA"):
    execucao_id = uuid4()
    db.execute(
        text(
            "INSERT INTO rotina_execucoes(id,tenant_id,created_by,rotina_id,semana_id,ocorrencia) "
            "VALUES (:id,:tenant,'user',:rotina,:semana,:ocorrencia)"
        ),
        {"id": execucao_id, "tenant": tenant, "rotina": rotina_id, "semana": semana_id, "ocorrencia": ocorrencia},
    )
    return execucao_id


def seed_rotinas(db, tenant, sufixo="1"):
    context(db, tenant)
    semana = add_semana(db, tenant, identificacao=f"S{sufixo}")
    rotina = add_rotina(db, tenant, titulo=f"Rotina {sufixo}")
    return rotina, semana, add_execucao(db, tenant, rotina, semana)


def test_rotinas_tables_force_rls_and_not_owned_by_runtime(db_factory):
    with db_factory.begin() as db:
        for table in ROTINAS_TABLES:
            flags = db.execute(
                text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname=:t"), {"t": table}
            ).one()
            assert tuple(flags) == (True, True), table
            owned = db.execute(
                text("SELECT tableowner=current_user FROM pg_tables WHERE tablename=:t"), {"t": table}
            ).scalar()
            assert owned is False, table
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        db.execute(text("ALTER TABLE rotinas DISABLE ROW LEVEL SECURITY"))


def test_rotinas_unfiltered_select_sees_only_current_tenant(db_factory):
    a, b = uuid4(), uuid4()
    for tenant, sufixo in [(a, "A"), (b, "B")]:
        with db_factory.begin() as db:
            seed_rotinas(db, tenant, sufixo)
    with db_factory.begin() as db:
        context(db, a)
        for table in ROTINAS_TABLES:
            assert db.execute(text(f"SELECT tenant_id FROM {table}")).scalars().all() == [a], table  # noqa: S608
    with db_factory.begin() as db:
        for table in ROTINAS_TABLES:
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0, table  # noqa: S608


def test_rotinas_insert_with_other_tenant_denied(db_factory):
    tenant, other = uuid4(), uuid4()
    with db_factory.begin() as db:
        context(db, tenant)
        rotina_a = add_rotina(db, tenant)
        semana_a = add_semana(db, tenant)
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, tenant)
        add_rotina(db, other)
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, tenant)
        add_execucao(db, other, rotina_a, semana_a)


def test_rotinas_composite_fk_blocks_cross_tenant_execucao(db_factory):
    a, b = uuid4(), uuid4()
    with db_factory.begin() as db:
        rotina_a, semana_a, _ = seed_rotinas(db, a, "A")
    with db_factory.begin() as db:
        context(db, b)
        rotina_b = add_rotina(db, b, titulo="Rotina B")
        semana_b = add_semana(db, b, "SB")
    cases = [(rotina_a, semana_b), (rotina_b, semana_a), (rotina_a, semana_a)]
    for rotina, semana in cases:
        with pytest.raises(DBAPIError), db_factory.begin() as db:
            context(db, b)
            add_execucao(db, b, rotina, semana)


def test_rotinas_ocorrencia_is_unique_per_rotina_semana(db_factory):
    a = uuid4()
    with db_factory.begin() as db:
        rotina, semana, _ = seed_rotinas(db, a)
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, a)
        add_execucao(db, a, rotina, semana, "SEMANA")
    with db_factory.begin() as db:
        context(db, a)
        add_execucao(db, a, rotina, semana, "Segunda")
        assert db.execute(text("SELECT count(*) FROM rotina_execucoes")).scalar() == 2


def test_rotinas_delete_cascades_to_execucoes(db_factory):
    a = uuid4()
    with db_factory.begin() as db:
        rotina, semana, _ = seed_rotinas(db, a)
    with db_factory.begin() as db:
        context(db, a)
        assert db.execute(text("DELETE FROM rotinas WHERE id=:id"), {"id": rotina}).rowcount == 1
        assert db.execute(text("SELECT count(*) FROM rotina_execucoes")).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM semanas")).scalar() == 1


def test_semana_delete_cascades_to_execucoes(db_factory):
    a = uuid4()
    with db_factory.begin() as db:
        rotina, semana, _ = seed_rotinas(db, a)
    with db_factory.begin() as db:
        context(db, a)
        assert db.execute(text("DELETE FROM semanas WHERE id=:id"), {"id": semana}).rowcount == 1
        assert db.execute(text("SELECT count(*) FROM rotina_execucoes")).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM rotinas")).scalar() == 1


FINOPS_TABLES = ("perfis_custo", "fontes_custo", "faturas", "iniciativas", "iniciativa_participantes")


def add_perfil(db, tenant, nome="Analista"):
    perfil_id = uuid4()
    db.execute(
        text("INSERT INTO perfis_custo(id,tenant_id,created_by,nome,custo_hora) VALUES (:id,:tenant,'user',:nome,80)"),
        {"id": perfil_id, "tenant": tenant, "nome": nome},
    )
    return perfil_id


def add_fonte(db, tenant, nome="Fabric"):
    fonte_id = uuid4()
    db.execute(
        text("INSERT INTO fontes_custo(id,tenant_id,created_by,nome) VALUES (:id,:tenant,'user',:nome)"),
        {"id": fonte_id, "tenant": tenant, "nome": nome},
    )
    return fonte_id


def add_fatura(db, tenant, fonte_id, competencia="2026-01-01"):
    fatura_id = uuid4()
    db.execute(
        text(
            "INSERT INTO faturas(id,tenant_id,created_by,fonte_id,competencia,valor_realizado) "
            "VALUES (:id,:tenant,'user',:fonte,:competencia,100)"
        ),
        {"id": fatura_id, "tenant": tenant, "fonte": fonte_id, "competencia": competencia},
    )
    return fatura_id


def add_iniciativa(db, tenant, titulo="Automacao", fonte_id=None):
    iniciativa_id = uuid4()
    db.execute(
        text(
            "INSERT INTO iniciativas"
            "(id,tenant_id,created_by,titulo,tipo,modo_calculo,valor_mensal,mes_inicio,fonte_id) "
            "VALUES (:id,:tenant,'user',:titulo,'OTIMIZACAO_CUSTO','DIRETO_REAIS',500,'2026-01-01',:fonte)"
        ),
        {"id": iniciativa_id, "tenant": tenant, "titulo": titulo, "fonte": fonte_id},
    )
    return iniciativa_id


def add_participante(db, tenant, iniciativa_id):
    participante_id = uuid4()
    db.execute(
        text(
            "INSERT INTO iniciativa_participantes"
            "(id,tenant_id,created_by,iniciativa_id,perfil_nome,custo_hora,qtd_pessoas,horas_antes,horas_depois) "
            "VALUES (:id,:tenant,'user',:iniciativa,'Analista',80,1,3,1)"
        ),
        {"id": participante_id, "tenant": tenant, "iniciativa": iniciativa_id},
    )
    return participante_id


def seed_finops(db, tenant, sufixo="1"):
    context(db, tenant)
    add_perfil(db, tenant, f"Perfil {sufixo}")
    fonte = add_fonte(db, tenant, f"Fonte {sufixo}")
    add_fatura(db, tenant, fonte)
    iniciativa = add_iniciativa(db, tenant, f"Iniciativa {sufixo}", fonte)
    add_participante(db, tenant, iniciativa)
    return fonte, iniciativa


def test_finops_tables_force_rls_and_not_owned_by_runtime(db_factory):
    with db_factory.begin() as db:
        for table in FINOPS_TABLES:
            flags = db.execute(
                text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname=:t"), {"t": table}
            ).one()
            assert tuple(flags) == (True, True), table
            owned = db.execute(
                text("SELECT tableowner=current_user FROM pg_tables WHERE tablename=:t"), {"t": table}
            ).scalar()
            assert owned is False, table
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        db.execute(text("ALTER TABLE iniciativas DISABLE ROW LEVEL SECURITY"))


def test_finops_unfiltered_select_sees_only_current_tenant(db_factory):
    a, b = uuid4(), uuid4()
    for tenant, sufixo in [(a, "A"), (b, "B")]:
        with db_factory.begin() as db:
            seed_finops(db, tenant, sufixo)
    with db_factory.begin() as db:
        context(db, a)
        for table in FINOPS_TABLES:
            assert db.execute(text(f"SELECT tenant_id FROM {table}")).scalars().all() == [a], table  # noqa: S608
    with db_factory.begin() as db:
        for table in FINOPS_TABLES:
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0, table  # noqa: S608


def test_finops_insert_with_other_tenant_denied(db_factory):
    tenant, other = uuid4(), uuid4()
    with db_factory.begin() as db:
        context(db, tenant)
        fonte_a = add_fonte(db, tenant)
        iniciativa_a = add_iniciativa(db, tenant)
    inserts = [
        lambda db: add_perfil(db, other),
        lambda db: add_fonte(db, other, "Outra"),
        lambda db: add_fatura(db, other, fonte_a),
        lambda db: add_iniciativa(db, other, "Outra"),
        lambda db: add_participante(db, other, iniciativa_a),
    ]
    for insert_row in inserts:
        with pytest.raises(DBAPIError), db_factory.begin() as db:
            context(db, tenant)
            insert_row(db)


def test_finops_composite_fk_blocks_cross_tenant_fonte_and_iniciativa(db_factory):
    a, b = uuid4(), uuid4()
    with db_factory.begin() as db:
        fonte_a, iniciativa_a = seed_finops(db, a, "A")
    with db_factory.begin() as db:
        context(db, b)
        fonte_b = add_fonte(db, b, "Fonte B")
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, b)
        add_fatura(db, b, fonte_a)
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, b)
        add_iniciativa(db, b, "Aponta para A", fonte_a)
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, b)
        add_participante(db, b, iniciativa_a)
    with db_factory.begin() as db:
        context(db, b)
        add_fatura(db, b, fonte_b)
        add_iniciativa(db, b, "Aponta para B", fonte_b)


def test_finops_fatura_is_unique_per_fonte_competencia(db_factory):
    a = uuid4()
    with db_factory.begin() as db:
        fonte, _ = seed_finops(db, a)
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, a)
        add_fatura(db, a, fonte, "2026-01-01")
    with db_factory.begin() as db:
        context(db, a)
        add_fatura(db, a, fonte, "2026-02-01")
        assert db.execute(text("SELECT count(*) FROM faturas")).scalar() == 2


def test_finops_cascades_and_fonte_with_iniciativa_is_protected(db_factory):
    a = uuid4()
    with db_factory.begin() as db:
        fonte, iniciativa = seed_finops(db, a)
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, a)
        db.execute(text("DELETE FROM fontes_custo WHERE id=:id"), {"id": fonte})
    with db_factory.begin() as db:
        context(db, a)
        assert db.execute(text("DELETE FROM iniciativas WHERE id=:id"), {"id": iniciativa}).rowcount == 1
        assert db.execute(text("SELECT count(*) FROM iniciativa_participantes")).scalar() == 0
        assert db.execute(text("DELETE FROM fontes_custo WHERE id=:id"), {"id": fonte}).rowcount == 1
        assert db.execute(text("SELECT count(*) FROM faturas")).scalar() == 0


DESPESAS_TABLES = ("despesas", "orcamentos_despesas")


def add_despesa(db, tenant, nome="Licenca", fonte_id=None):
    despesa_id = uuid4()
    db.execute(
        text(
            "INSERT INTO despesas(id,tenant_id,created_by,nome,categoria,tipo_custo,valor,status_auditoria,fonte_id) "
            "VALUES (:id,:tenant,'user',:nome,'Outros Servicos','RECORRENTE_MENSAL',300,'EM_REVISAO',:fonte)"
        ),
        {"id": despesa_id, "tenant": tenant, "nome": nome, "fonte": fonte_id},
    )
    return despesa_id


def add_orcamento(db, tenant, competencia="2026-01-01"):
    orcamento_id = uuid4()
    db.execute(
        text(
            "INSERT INTO orcamentos_despesas(id,tenant_id,created_by,competencia,valor) "
            "VALUES (:id,:tenant,'user',:competencia,1000)"
        ),
        {"id": orcamento_id, "tenant": tenant, "competencia": competencia},
    )
    return orcamento_id


def add_iniciativa_despesa(db, tenant, despesa_id, titulo="Cancelamento"):
    iniciativa_id = uuid4()
    db.execute(
        text(
            "INSERT INTO iniciativas"
            "(id,tenant_id,created_by,titulo,tipo,modo_calculo,valor_mensal,mes_inicio,despesa_id,conversao_despesa) "
            "VALUES (:id,:tenant,'user',:titulo,'OTIMIZACAO_CUSTO','DIRETO_REAIS',300,'2026-01-01',:despesa,true)"
        ),
        {"id": iniciativa_id, "tenant": tenant, "titulo": titulo, "despesa": despesa_id},
    )
    return iniciativa_id


def seed_despesas(db, tenant, sufixo="1"):
    context(db, tenant)
    fonte = add_fonte(db, tenant, f"Fonte {sufixo}")
    despesa = add_despesa(db, tenant, f"Despesa {sufixo}", fonte)
    add_orcamento(db, tenant)
    add_iniciativa_despesa(db, tenant, despesa)
    return fonte, despesa


def test_despesas_tables_force_rls_and_not_owned_by_runtime(db_factory):
    with db_factory.begin() as db:
        for table in DESPESAS_TABLES:
            flags = db.execute(
                text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname=:t"), {"t": table}
            ).one()
            assert tuple(flags) == (True, True), table
            owned = db.execute(
                text("SELECT tableowner=current_user FROM pg_tables WHERE tablename=:t"), {"t": table}
            ).scalar()
            assert owned is False, table
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        db.execute(text("ALTER TABLE despesas DISABLE ROW LEVEL SECURITY"))


def test_despesas_unfiltered_select_sees_only_current_tenant(db_factory):
    a, b = uuid4(), uuid4()
    for tenant, sufixo in [(a, "A"), (b, "B")]:
        with db_factory.begin() as db:
            seed_despesas(db, tenant, sufixo)
    with db_factory.begin() as db:
        context(db, a)
        for table in DESPESAS_TABLES:
            assert db.execute(text(f"SELECT tenant_id FROM {table}")).scalars().all() == [a], table  # noqa: S608
    with db_factory.begin() as db:
        for table in DESPESAS_TABLES:
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0, table  # noqa: S608


def test_despesas_insert_with_other_tenant_denied(db_factory):
    tenant, other = uuid4(), uuid4()
    inserts = [
        lambda db: add_despesa(db, other, "Outra"),
        lambda db: add_orcamento(db, other),
    ]
    for insert_row in inserts:
        with pytest.raises(DBAPIError), db_factory.begin() as db:
            context(db, tenant)
            insert_row(db)


def test_despesas_composite_fk_blocks_cross_tenant_fonte_and_iniciativa(db_factory):
    a, b = uuid4(), uuid4()
    with db_factory.begin() as db:
        fonte_a, despesa_a = seed_despesas(db, a, "A")
    with db_factory.begin() as db:
        context(db, b)
        fonte_b = add_fonte(db, b, "Fonte B")
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, b)
        add_despesa(db, b, "Aponta para fonte de A", fonte_a)
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, b)
        add_iniciativa_despesa(db, b, despesa_a, "Aponta para despesa de A")
    with db_factory.begin() as db:
        context(db, b)
        despesa_b = add_despesa(db, b, "Despesa B", fonte_b)
        add_iniciativa_despesa(db, b, despesa_b)


def test_despesas_orcamento_is_unique_per_competencia(db_factory):
    a = uuid4()
    with db_factory.begin() as db:
        seed_despesas(db, a)
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, a)
        add_orcamento(db, a, "2026-01-01")
    with db_factory.begin() as db:
        context(db, a)
        add_orcamento(db, a, "2026-02-01")
        assert db.execute(text("SELECT count(*) FROM orcamentos_despesas")).scalar() == 2


def test_despesas_with_iniciativa_or_fonte_link_are_protected(db_factory):
    a = uuid4()
    with db_factory.begin() as db:
        fonte, despesa = seed_despesas(db, a)
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, a)
        db.execute(text("DELETE FROM despesas WHERE id=:id"), {"id": despesa})
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, a)
        db.execute(text("DELETE FROM iniciativas WHERE despesa_id=:id"), {"id": despesa})
        db.execute(text("DELETE FROM fontes_custo WHERE id=:id"), {"id": fonte})
    with db_factory.begin() as db:
        context(db, a)
        db.execute(text("DELETE FROM iniciativas WHERE despesa_id=:id"), {"id": despesa})
        assert db.execute(text("DELETE FROM despesas WHERE id=:id"), {"id": despesa}).rowcount == 1
        assert db.execute(text("DELETE FROM fontes_custo WHERE id=:id"), {"id": fonte}).rowcount == 1


PLANNER_TABLES = ("planner_dias", "planner_itens")


def pessoa(db, tenant, sub):
    context(db, tenant)
    db.execute(text("SELECT set_config('app.subject', :sub, true)"), {"sub": sub})


def add_dia(db, tenant, sub, data="2026-10-23"):
    dia_id = uuid4()
    db.execute(
        text("INSERT INTO planner_dias(id,tenant_id,created_by,sub,data) VALUES (:id,:tenant,:sub,:sub,:data)"),
        {"id": dia_id, "tenant": tenant, "sub": sub, "data": data},
    )
    return dia_id


def add_item_planner(db, tenant, sub, dia_id, texto="Tarefa", tipo="TAREFA"):
    item_id = uuid4()
    db.execute(
        text(
            "INSERT INTO planner_itens(id,tenant_id,created_by,sub,dia_id,tipo,texto) "
            "VALUES (:id,:tenant,:sub,:sub,:dia,:tipo,:texto)"
        ),
        {"id": item_id, "tenant": tenant, "sub": sub, "dia": dia_id, "tipo": tipo, "texto": texto},
    )
    return item_id


def seed_planner(db, tenant, sub):
    pessoa(db, tenant, sub)
    dia = add_dia(db, tenant, sub)
    add_item_planner(db, tenant, sub, dia)
    return dia


def test_planner_tables_force_rls_and_not_owned_by_runtime(db_factory):
    with db_factory.begin() as db:
        for table in PLANNER_TABLES:
            flags = db.execute(
                text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname=:t"), {"t": table}
            ).one()
            assert tuple(flags) == (True, True), table
            owned = db.execute(
                text("SELECT tableowner=current_user FROM pg_tables WHERE tablename=:t"), {"t": table}
            ).scalar()
            assert owned is False, table
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        db.execute(text("ALTER TABLE planner_dias DISABLE ROW LEVEL SECURITY"))


def test_planner_same_tenant_other_subject_sees_and_changes_nothing(db_factory):
    tenant = uuid4()
    with db_factory.begin() as db:
        seed_planner(db, tenant, "pessoa-a")
    with db_factory.begin() as db:
        pessoa(db, tenant, "pessoa-b")
        for table in PLANNER_TABLES:
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0, table  # noqa: S608
        assert db.execute(text("UPDATE planner_dias SET foco='roubado'")).rowcount == 0
        assert db.execute(text("DELETE FROM planner_itens")).rowcount == 0
        assert db.execute(text("DELETE FROM planner_dias")).rowcount == 0
    with db_factory.begin() as db:
        pessoa(db, tenant, "pessoa-a")
        for table in PLANNER_TABLES:
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 1, table  # noqa: S608


def test_planner_without_subject_sees_nothing(db_factory):
    tenant = uuid4()
    with db_factory.begin() as db:
        seed_planner(db, tenant, "pessoa-a")
    with db_factory.begin() as db:
        context(db, tenant)
        for table in PLANNER_TABLES:
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0, table  # noqa: S608


def test_planner_insert_for_other_subject_denied(db_factory):
    tenant = uuid4()
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        pessoa(db, tenant, "pessoa-b")
        add_dia(db, tenant, "pessoa-a")
    with db_factory.begin() as db:
        pessoa(db, tenant, "pessoa-a")
        dia_a = add_dia(db, tenant, "pessoa-a")
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        pessoa(db, tenant, "pessoa-a")
        add_item_planner(db, tenant, "pessoa-b", dia_a)  # RLS nega; item.sub == dia.sub é garantido pelo serviço


def test_planner_insert_with_other_tenant_denied(db_factory):
    tenant, other = uuid4(), uuid4()
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        pessoa(db, tenant, "pessoa-a")
        add_dia(db, other, "pessoa-a")
    with db_factory.begin() as db:
        pessoa(db, tenant, "pessoa-a")
        dia = add_dia(db, tenant, "pessoa-a")
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        pessoa(db, tenant, "pessoa-a")
        add_item_planner(db, other, "pessoa-a", dia)
    with db_factory.begin() as db:
        pessoa(db, other, "pessoa-a")
        for table in PLANNER_TABLES:
            assert db.execute(text(f"SELECT count(*) FROM {table}")).scalar() == 0, table  # noqa: S608


def test_planner_composite_fk_blocks_cross_tenant_item(db_factory):
    a, b = uuid4(), uuid4()
    with db_factory.begin() as db:
        dia_a = seed_planner(db, a, "pessoa-a")
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        pessoa(db, b, "pessoa-a")
        add_item_planner(db, b, "pessoa-a", dia_a, "Aponta para dia de outro tenant")
    with db_factory.begin() as db:
        pessoa(db, b, "pessoa-a")
        dia_b = add_dia(db, b, "pessoa-a")
        add_item_planner(db, b, "pessoa-a", dia_b)


def test_planner_dia_is_unique_per_tenant_sub_data(db_factory):
    tenant, other = uuid4(), uuid4()
    with db_factory.begin() as db:
        seed_planner(db, tenant, "pessoa-a")
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        pessoa(db, tenant, "pessoa-a")
        add_dia(db, tenant, "pessoa-a", "2026-10-23")
    with db_factory.begin() as db:
        pessoa(db, tenant, "pessoa-a")
        add_dia(db, tenant, "pessoa-a", "2026-10-24")  # outra data
    with db_factory.begin() as db:
        pessoa(db, tenant, "pessoa-b")
        add_dia(db, tenant, "pessoa-b", "2026-10-23")  # mesma data, outra pessoa
    with db_factory.begin() as db:
        pessoa(db, other, "pessoa-a")
        add_dia(db, other, "pessoa-a", "2026-10-23")  # mesma pessoa e data, outro tenant


def test_planner_dia_delete_cascades_to_itens_and_tipo_is_checked(db_factory):
    tenant = uuid4()
    with db_factory.begin() as db:
        dia = seed_planner(db, tenant, "pessoa-a")
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        pessoa(db, tenant, "pessoa-a")
        add_item_planner(db, tenant, "pessoa-a", dia, tipo="OUTRO")
    with db_factory.begin() as db:
        pessoa(db, tenant, "pessoa-a")
        assert db.execute(text("DELETE FROM planner_dias WHERE id=:id"), {"id": dia}).rowcount == 1
        assert db.execute(text("SELECT count(*) FROM planner_itens")).scalar() == 0


def test_capacidade_api_authorized_flow(db_factory, monkeypatch):
    from fastapi.testclient import TestClient

    from src.backend.api import deps
    from src.backend.core import sessions
    from src.backend.core.config import settings
    from src.backend.integrations.guilarde.contracts import Authorization, Principal
    from src.backend.main import app

    a = uuid4()
    monkeypatch.setattr(deps, "SessionLocal", db_factory)
    monkeypatch.setattr(sessions, "load_session", lambda _sid: {"access_token": "test", "csrf": "csrf"})
    monkeypatch.setattr(deps, "validate_access_token", lambda _token: Principal(sub="member-one"))

    async def authorize(token, tenant, permission):
        return Authorization(
            sub="member-one",
            tenant_id=tenant,
            app_id=settings.APP_ID,
            allowed=tenant == a,
            permissions={"access", "read", "write"},
        )

    monkeypatch.setattr(deps.core_client, "authorize", authorize)
    client = TestClient(app)  # sem "with": o lifespan não roda
    client.cookies.set(settings.SESSION_COOKIE, "a" * 43)
    headers = {"X-Tenant-ID": str(a), "X-CSRF-Token": "csrf", "Origin": settings.PUBLIC_URL}
    created = client.post("/api/v1/grupos", json={"nome": "Projetos", "categoria": "BUILD"}, headers=headers)
    assert created.status_code == 201
    assert created.json()["nome"] == "Projetos"
    assert [g["nome"] for g in client.get("/api/v1/grupos", headers=headers).json()] == ["Projetos", "Triagem"]
    assert client.get("/api/v1/dashboard", headers=headers).status_code == 200
    assert client.get("/api/v1/grupos", headers={"X-Tenant-ID": str(uuid4())}).status_code == 403


def add_grupo_sistema(db, tenant, nome="Triagem"):
    grupo_id = uuid4()
    db.execute(
        text(
            "INSERT INTO grupos(id,tenant_id,created_by,nome,categoria,sistema) "
            "VALUES (:id,:tenant,'user',:nome,'RUN',true)"
        ),
        {"id": grupo_id, "tenant": tenant, "nome": nome},
    )
    return grupo_id


def add_demanda(db, tenant, grupo_id, titulo="Preciso de acesso", status="ABERTA", prioridade="MEDIA", concluida=None):
    demanda_id = uuid4()
    if concluida is None:
        concluida = status == "CONCLUIDA"
    db.execute(
        text(
            "INSERT INTO demandas(id,tenant_id,created_by,grupo_id,titulo,prioridade,status,"
            "solicitante_sub,concluido_em) "
            "VALUES (:id,:tenant,'user',:grupo,:titulo,:prioridade,:status,'user',"
            "CASE WHEN CAST(:concluida AS boolean) THEN now() END)"
        ),
        {
            "id": demanda_id,
            "tenant": tenant,
            "grupo": grupo_id,
            "titulo": titulo,
            "prioridade": prioridade,
            "status": status,
            "concluida": concluida,
        },
    )
    return demanda_id


def seed_demandas(db, tenant, sufixo="1"):
    context(db, tenant)
    grupo = add_grupo(db, tenant, f"Grupo {sufixo}")
    return grupo, add_demanda(db, tenant, grupo, f"Demanda {sufixo}")


def test_demandas_table_forces_rls_and_not_owned_by_runtime(db_factory):
    with db_factory.begin() as db:
        flags = db.execute(
            text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='demandas'")
        ).one()
        assert tuple(flags) == (True, True)
        owned = db.execute(text("SELECT tableowner=current_user FROM pg_tables WHERE tablename='demandas'")).scalar()
        assert owned is False
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        db.execute(text("ALTER TABLE demandas DISABLE ROW LEVEL SECURITY"))


def test_demandas_unfiltered_select_sees_only_current_tenant(db_factory):
    a, b = uuid4(), uuid4()
    for tenant, sufixo in [(a, "A"), (b, "B")]:
        with db_factory.begin() as db:
            seed_demandas(db, tenant, sufixo)
    with db_factory.begin() as db:
        context(db, a)
        assert db.execute(text("SELECT tenant_id FROM demandas")).scalars().all() == [a]
    with db_factory.begin() as db:
        assert db.execute(text("SELECT count(*) FROM demandas")).scalar() == 0


def test_demandas_insert_with_other_tenant_denied(db_factory):
    tenant, other = uuid4(), uuid4()
    with db_factory.begin() as db:
        context(db, other)
        grupo_other = add_grupo(db, other, "Do outro")
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, tenant)
        add_demanda(db, other, grupo_other)


def test_demandas_composite_fk_blocks_cross_tenant_grupo(db_factory):
    a, b = uuid4(), uuid4()
    with db_factory.begin() as db:
        grupo_a, _ = seed_demandas(db, a, "A")
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, b)
        add_demanda(db, b, grupo_a, "Aponta para grupo de A")
    with db_factory.begin() as db:
        context(db, b)
        add_demanda(db, b, add_grupo(db, b, "Grupo B"))


def test_demandas_grupo_with_demandas_is_protected_and_constraints_hold(db_factory):
    tenant = uuid4()
    with db_factory.begin() as db:
        grupo, demanda = seed_demandas(db, tenant)
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, tenant)
        db.execute(text("DELETE FROM grupos WHERE id=:id"), {"id": grupo})
    for kwargs in (
        {"status": "OUTRO"},
        {"status": "TRIAGEM"},
        {"prioridade": "URGENTE"},
        {"status": "CONCLUIDA", "concluida": False},
        {"status": "ABERTA", "concluida": True},
    ):
        with pytest.raises(DBAPIError), db_factory.begin() as db:
            context(db, tenant)
            add_demanda(db, tenant, grupo, **kwargs)
    with db_factory.begin() as db:
        context(db, tenant)
        add_demanda(db, tenant, grupo, status="CONCLUIDA")
        add_demanda(db, tenant, grupo, status="CANCELADA")
        db.execute(text("DELETE FROM demandas WHERE tenant_id=:t"), {"t": tenant})
        assert db.execute(text("DELETE FROM grupos WHERE id=:id"), {"id": grupo}).rowcount == 1
    assert demanda


def test_grupos_only_one_system_grupo_per_tenant(db_factory):
    a, b = uuid4(), uuid4()
    with db_factory.begin() as db:
        context(db, a)
        add_grupo_sistema(db, a)
    with pytest.raises(DBAPIError), db_factory.begin() as db:
        context(db, a)
        add_grupo_sistema(db, a, "Outro de sistema")
    with db_factory.begin() as db:
        context(db, a)
        add_grupo(db, a, "Comum")
    with db_factory.begin() as db:
        context(db, b)
        add_grupo_sistema(db, b)

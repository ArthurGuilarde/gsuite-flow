from fastapi.testclient import TestClient

from src.backend.main import app
from src.backend.models import Base


def test_template_domain_is_only_capacidade():
    from tests.support.tenant_example import TestBase

    assert set(TestBase.metadata.tables) == {"tenant_test_records"}
    assert set(Base.metadata.tables) == {
        "browser_sessions",
        "grupos",
        "semanas",
        "lancamentos",
        "rotinas",
        "rotina_execucoes",
        "perfis_custo",
        "fontes_custo",
        "faturas",
        "iniciativas",
        "iniciativa_participantes",
        "despesas",
        "orcamentos_despesas",
        "planner_dias",
        "planner_itens",
    }
    paths = app.openapi()["paths"]
    assert "/api/v1/context" in paths
    assert not any("notes" in path or "test-records" in path for path in paths)
    page = TestClient(app).get("/")
    assert page.status_code == 200
    assert 'id="tenant"' in page.text

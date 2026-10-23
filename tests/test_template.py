from fastapi.testclient import TestClient

from src.backend.main import app
from src.backend.models import Base


def test_template_has_no_business_domain():
    from tests.support.tenant_example import TestBase

    assert set(TestBase.metadata.tables) == {"tenant_test_records"}
    assert set(Base.metadata.tables) == {"browser_sessions"}
    paths = app.openapi()["paths"]
    assert "/api/v1/context" in paths
    assert not any("notes" in path or "test-records" in path for path in paths)
    page = TestClient(app).get("/")
    assert page.status_code == 200
    assert 'id="tenant"' in page.text
    assert 'id="create"' not in page.text

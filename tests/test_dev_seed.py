from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text

from src.backend import dev_seed
from src.backend.core.config import settings
from src.backend.integrations.guilarde.local import TENANT_A
from src.backend.models import Base


@pytest.fixture
def engine(monkeypatch, tmp_path):
    seed_engine = create_engine(f"sqlite:///{tmp_path / 'seed.sqlite3'}")

    @event.listens_for(seed_engine, "connect")
    def _fk(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(seed_engine)
    monkeypatch.setattr(dev_seed, "engine", seed_engine)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "AUTH_MODE", "local")
    return seed_engine


def test_seed_moves_snapshot_to_current_week_and_month(engine):
    message = dev_seed.seed(today=date(2026, 12, 2))
    assert message.startswith("Seed concluído: 174 registros")
    with engine.connect() as db:
        semanas = db.execute(text("SELECT identificacao, data_inicio FROM semanas ORDER BY data_inicio")).all()
        assert [s.identificacao for s in semanas] == ["Semana 47", "Semana 48", "Semana 49", "Semana 50"]
        assert semanas[2].data_inicio == "2026-11-30"
        assert db.execute(text("SELECT max(competencia) FROM faturas")).scalar() == "2026-12-01"
        assert db.execute(text("SELECT count(*) FROM demandas")).scalar() == 7
        assert {row[0] for row in db.execute(text("SELECT DISTINCT tenant_id FROM demandas"))} == {TENANT_A.hex}
    assert dev_seed.seed(today=date(2026, 12, 2)).startswith("Seed ignorado")


def test_seed_reuses_existing_triagem(engine):
    triagem = uuid4()
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO grupos (id, tenant_id, created_by, nome, categoria, icone, cor, ativo, sistema) "
                "VALUES (:id, :tenant, 'editor-a', 'Triagem', 'RUN', 'x', '#64748B', 1, 1)"
            ),
            {"id": triagem.hex, "tenant": TENANT_A.hex},
        )
    assert dev_seed.seed(today=date(2026, 10, 23)).startswith("Seed concluído")
    with engine.connect() as db:
        assert db.execute(text("SELECT count(*) FROM grupos WHERE sistema")).scalar() == 1
        em_triagem = db.execute(text("SELECT count(*) FROM demandas WHERE grupo_id = :id"), {"id": triagem.hex})
        assert em_triagem.scalar() == 3


def test_seed_refuses_outside_local_dev(engine, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_MODE", "oidc")
    with pytest.raises(RuntimeError, match="dev profile"):
        dev_seed.seed()


def test_add_months_clamps_to_month_end():
    assert dev_seed._add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert dev_seed._add_months(date(2026, 11, 10), 2) == date(2027, 1, 10)

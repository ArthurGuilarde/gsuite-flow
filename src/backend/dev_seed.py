"""Fictitious demo data for the isolated dev profile only (espaço A of the local fixtures)."""

import json
from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Numeric, Uuid, select

from src.backend.core.config import settings
from src.backend.core.database import engine
from src.backend.integrations.guilarde.local import TENANT_A
from src.backend.models import Base

SEED_FILE = Path(__file__).with_name("dev_seed.json")
# Colunas de data que seguem a semana; as demais datas são mensais (competência, renovação, vigência).
WEEK_DATES = {("semanas", "data_inicio"), ("semanas", "data_fim"), ("planner_dias", "data")}


def _add_months(value: date, months: int) -> date:
    total = value.year * 12 + value.month - 1 + months
    year, month = divmod(total, 12)
    return value.replace(year=year, month=month + 1, day=min(value.day, monthrange(year, month + 1)[1]))


def _shifts(reference: date, today: date) -> tuple[timedelta, int]:
    """Move the snapshot so its reference week and month become the current ones."""
    monday = today - timedelta(days=today.weekday())
    reference_monday = reference - timedelta(days=reference.weekday())
    months = (today.year * 12 + today.month) - (reference.year * 12 + reference.month)
    return monday - reference_monday, months


def _convert(table: str, column: Any, value: Any, weeks: timedelta, months: int) -> Any:
    if value is None:
        return None
    kind = column.type
    if isinstance(kind, Uuid):
        return UUID(value)
    if isinstance(kind, DateTime):
        return datetime.fromisoformat(value) + weeks
    if isinstance(kind, Date):
        parsed = date.fromisoformat(value)
        return parsed + weeks if (table, column.name) in WEEK_DATES else _add_months(parsed, months)
    if isinstance(kind, Numeric):
        return Decimal(str(value))
    if isinstance(kind, Boolean):
        return bool(value)
    return value


def seed(today: date | None = None) -> str:
    if settings.ENVIRONMENT != "development" or settings.AUTH_MODE != "local" or engine.dialect.name != "sqlite":
        raise RuntimeError("Seed is only available in the dev profile with SQLite")
    snapshot = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    weeks, months = _shifts(date.fromisoformat(snapshot["referencia"]), today or date.today())
    rows_by_table: dict[str, list[dict[str, Any]]] = snapshot["tabelas"]
    tables = [table for table in Base.metadata.sorted_tables if table.name in rows_by_table]
    with engine.begin() as db:
        grupos = Base.metadata.tables["grupos"]
        for table in tables:
            filtro = table.c.tenant_id == TENANT_A
            if table is grupos:
                # Triagem nasce sozinha ao abrir a Capacidade; ela não conta como dado existente.
                filtro = filtro & grupos.c.sistema.is_(False)
            if db.execute(select(table.c.id).where(filtro).limit(1)).first() is not None:
                return "Seed ignorado: o espaço A já tem dados. Apague .local/dev.sqlite3 para recomeçar."
        remap: dict[str, UUID] = {}
        triagem = db.execute(
            select(grupos.c.id).where(grupos.c.tenant_id == TENANT_A, grupos.c.sistema.is_(True))
        ).scalar()
        if triagem is not None:
            remap = {row["id"]: triagem for row in rows_by_table["grupos"] if row["sistema"]}
        total = 0
        for table in tables:
            rows: list[dict[str, Any]] = []
            for raw in rows_by_table[table.name]:
                if table is grupos and raw["id"] in remap:
                    continue
                row: dict[str, Any] = {
                    name: remap[value]
                    if isinstance(value, str) and value in remap
                    else _convert(table.name, table.c[name], value, weeks, months)
                    for name, value in raw.items()
                }
                row["tenant_id"] = TENANT_A
                if table.name == "semanas":
                    row["identificacao"] = f"Semana {row['data_inicio'].isocalendar().week}"
                rows.append(row)
            if rows:
                db.execute(table.insert(), rows)
                total += len(rows)
    return f"Seed concluído: {total} registros fictícios no espaço A ({len(tables)} tabelas)."

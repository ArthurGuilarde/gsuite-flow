"""Executable RLS/domain reference used only by tests, never mounted by the application."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, UniqueConstraint, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from src.backend.api.auth import router as auth_router
from src.backend.api.deps import read_context, read_db, write_context, write_db
from src.backend.api.v1.router import api_v1_router
from src.backend.models.base import TenantRecord
from src.backend.tenancy.context import TenantContext


class TestBase(DeclarativeBase):
    pass


class TestRecord(TenantRecord):
    __tablename__ = "tenant_test_records"
    __table_args__ = (UniqueConstraint("tenant_id", "id"),)
    # Keep test-only metadata out of Alembic's production autogeneration.
    metadata = TestBase.metadata
    title: Mapped[str] = mapped_column(String(200))


class RecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)


class RecordView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    title: str


router = APIRouter(prefix="/api/v1/test-records")
ReadDB = Annotated[Session, Depends(read_db, scope="function")]
WriteDB = Annotated[Session, Depends(write_db, scope="function")]
ReadContext = Annotated[TenantContext, Depends(read_context)]
WriteContext = Annotated[TenantContext, Depends(write_context)]


@router.get("", response_model=list[RecordView])
def list_records(db: ReadDB, ctx: ReadContext):
    return db.scalars(select(TestRecord).where(TestRecord.tenant_id == ctx.tenant_id)).all()


@router.post("", response_model=RecordView, status_code=201)
def create_record(body: RecordCreate, db: WriteDB, ctx: WriteContext):
    row = TestRecord(title=body.title, tenant_id=ctx.tenant_id, created_by=ctx.sub)
    db.add(row)
    db.flush()
    return row


def create_test_app():
    from src.backend.main import app as production_app

    app = FastAPI(middleware=production_app.user_middleware, exception_handlers=production_app.exception_handlers)
    app.include_router(auth_router)
    app.include_router(api_v1_router)
    app.include_router(router)
    return app

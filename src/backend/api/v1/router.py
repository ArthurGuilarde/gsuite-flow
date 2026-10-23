from fastapi import APIRouter, Depends

from src.backend.api.deps import read_context
from src.backend.api.v1.capacidade import router as capacidade_router
from src.backend.api.v1.rotinas import router as rotinas_router
from src.backend.schemas.context import ContextView

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(capacidade_router)
api_v1_router.include_router(rotinas_router)


@api_v1_router.get("/context", response_model=ContextView, tags=["workspace"])
def current_context(ctx=Depends(read_context)):
    return ContextView(tenant_id=ctx.tenant_id, permissions=sorted(ctx.permissions), features=sorted(ctx.features))

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from src.backend.core.config import settings
from src.backend.integrations.guilarde.contracts import Authorization, TenantSummary


class GuilardeClient:
    """Versioned proposed Core contract; Core owns memberships and entitlements."""

    async def _request(self, method: str, path: str, token: str, **kwargs):
        try:
            async with httpx.AsyncClient(base_url=settings.CORE_URL, timeout=5, follow_redirects=False) as client:
                response = await client.request(method, path, headers={"Authorization": f"Bearer {token}"}, **kwargs)
            if response.status_code in (401, 403):
                raise HTTPException(response.status_code, "Central authorization denied")
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "Central authorization unavailable") from exc

    async def authorize(self, token: str, tenant_id, permission: str) -> Authorization:
        data = await self._request(
            "POST",
            "/v1/authorize",
            token,
            json={
                "app_id": settings.APP_ID,
                "tenant_id": str(tenant_id),
                "permission": permission,
            },
        )
        try:
            return Authorization.model_validate(data)
        except ValidationError as exc:
            raise HTTPException(503, "Invalid central authorization response") from exc

    async def tenants(self, token: str) -> list[TenantSummary]:
        data = await self._request("GET", "/v1/me/tenants", token, params={"app_id": settings.APP_ID})
        try:
            return [TenantSummary.model_validate(item) for item in data["tenants"]]
        except (ValidationError, KeyError, TypeError) as exc:
            raise HTTPException(503, "Invalid tenant response") from exc


core_client = GuilardeClient()

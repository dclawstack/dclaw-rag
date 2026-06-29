from fastapi import APIRouter, Depends, Header, HTTPException

from app.api.dependencies import get_api_key_store
from app.core.config import settings
from app.db.api_key_store import ApiKeyStore
from app.models.schemas import ApiKeyCreate, ApiKeyResponse

router = APIRouter()


@router.post("/keys", response_model=ApiKeyResponse)
async def create_api_key(
    body: ApiKeyCreate,
    x_admin_key: str | None = Header(default=None),
    store: ApiKeyStore = Depends(get_api_key_store),
) -> ApiKeyResponse:
    """Mint a new API key for a tenant. Requires the admin key."""
    if not settings.admin_api_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Admin key required")
    raw_key, record = store.create(body.tenant_id, body.name)
    return ApiKeyResponse(api_key=raw_key, tenant_id=record["tenant_id"], name=record["name"])

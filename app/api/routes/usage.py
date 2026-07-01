from fastapi import APIRouter, Depends

from app.api.dependencies import Principal, get_principal, get_usage_store
from app.db.usage_store import UsageStore

router = APIRouter()


@router.get("/usage")
async def usage(
    principal: Principal = Depends(get_principal),
    store: UsageStore = Depends(get_usage_store),
) -> dict:
    """Cumulative LLM usage (tokens + estimated cost) for the caller's tenant."""
    return {"tenant_id": principal.tenant_id, **store.get(principal.tenant_id)}

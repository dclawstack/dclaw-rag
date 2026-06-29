from fastapi import APIRouter, Depends

from app.api.dependencies import Principal, get_principal
from app.core.config import settings
from app.models.schemas import SystemInfo

router = APIRouter()


@router.get("/system", response_model=SystemInfo)
async def system_info(principal: Principal = Depends(get_principal)) -> SystemInfo:
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        llm_model = settings.ollama_model
    elif provider == "openrouter":
        llm_model = settings.openrouter_model
    else:
        llm_model = settings.llm_model
    return SystemInfo(
        backend_port=settings.api_port,
        embedding_model=settings.embedding_model,
        reranker_model=settings.reranker_model,
        llm_provider=settings.llm_provider,
        llm_model=llm_model,
    )

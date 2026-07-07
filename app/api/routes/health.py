from fastapi import APIRouter, Response

from app.core import metrics
from app.core.config import settings
from app.db.backend import get_qdrant_client, make_kv
from app.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness: the process is up and serving."""
    return HealthResponse(status="ok")


def _check_kv() -> bool:
    try:
        return bool(make_kv().ping())
    except Exception:
        return False


def _check_qdrant() -> bool:
    try:
        get_qdrant_client().get_collections()
        return True
    except Exception:
        return False


@router.get("/health/ready")
async def ready(response: Response) -> dict:
    """Readiness: the KV store (Redis / local SQLite) and Qdrant are reachable.
    503 if not."""
    kv_name = "kv" if settings.app_mode == "local" else "redis"
    checks = {kv_name: _check_kv(), "qdrant": _check_qdrant()}
    ok = all(checks.values())
    response.status_code = 200 if ok else 503
    return {"status": "ready" if ok else "not ready", "checks": checks}


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    payload, content_type = metrics.render()
    return Response(content=payload, media_type=content_type)

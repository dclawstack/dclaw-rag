import secrets
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import Principal, get_principal, get_user_store
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.user_store import UserStore
from app.models.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter()


def _token_for(user_id: str, tenant_id: str, email: str) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user_id=user_id, tenant_id=tenant_id, email=email),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/auth/register", response_model=TokenResponse)
async def register(
    body: RegisterRequest,
    users: UserStore = Depends(get_user_store),
) -> TokenResponse:
    """Self-serve signup. Each new account gets its own isolated tenant."""
    email = body.email.strip().lower()
    record = {
        "id": uuid4().hex,
        "email": email,
        "password_hash": hash_password(body.password),
        "tenant_id": "t_" + secrets.token_hex(8),
        "created_at": datetime.now(tz=UTC).isoformat(),
    }
    try:
        users.create(record)
    except ValueError:
        raise HTTPException(status_code=409, detail="Email already registered") from None
    return _token_for(record["id"], record["tenant_id"], email)


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    users: UserStore = Depends(get_user_store),
) -> TokenResponse:
    user = users.get_by_email(body.email.strip().lower())
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _token_for(user["id"], user["tenant_id"], user["email"])


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(principal: Principal = Depends(get_principal)) -> TokenResponse:
    if not principal.user_id:
        raise HTTPException(status_code=403, detail="A user session is required")
    return _token_for(principal.user_id, principal.tenant_id, principal.email or "")


@router.get("/auth/me", response_model=UserResponse)
async def me(principal: Principal = Depends(get_principal)) -> UserResponse:
    if not principal.user_id:
        raise HTTPException(status_code=403, detail="A user session is required")
    return UserResponse(
        id=principal.user_id, email=principal.email or "", tenant_id=principal.tenant_id
    )

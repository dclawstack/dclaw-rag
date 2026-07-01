import secrets
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    Principal,
    enforce_auth_rate_limit,
    get_principal,
    get_refresh_token_store,
    get_user_store,
)
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.db.refresh_token_store import RefreshTokenStore
from app.db.user_store import UserStore
from app.models.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter()


def _issue_tokens(
    user_id: str, tenant_id: str, email: str, refresh_store: RefreshTokenStore
) -> TokenResponse:
    jti = refresh_store.issue(user_id)
    return TokenResponse(
        access_token=create_access_token(user_id=user_id, tenant_id=tenant_id, email=email),
        refresh_token=create_refresh_token(
            user_id=user_id, tenant_id=tenant_id, email=email, jti=jti
        ),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post(
    "/auth/register",
    response_model=TokenResponse,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
async def register(
    body: RegisterRequest,
    users: UserStore = Depends(get_user_store),
    refresh_store: RefreshTokenStore = Depends(get_refresh_token_store),
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
    return _issue_tokens(record["id"], record["tenant_id"], email, refresh_store)


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    dependencies=[Depends(enforce_auth_rate_limit)],
)
async def login(
    body: LoginRequest,
    users: UserStore = Depends(get_user_store),
    refresh_store: RefreshTokenStore = Depends(get_refresh_token_store),
) -> TokenResponse:
    user = users.get_by_email(body.email.strip().lower())
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _issue_tokens(user["id"], user["tenant_id"], user["email"], refresh_store)


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    refresh_store: RefreshTokenStore = Depends(get_refresh_token_store),
) -> TokenResponse:
    """Rotate: verify the refresh token (and that it hasn't been revoked), then
    revoke it and issue a fresh access + refresh pair."""
    claims = decode_refresh_token(body.refresh_token)
    if not claims or not refresh_store.is_valid(claims["jti"], claims["sub"]):
        raise HTTPException(status_code=401, detail="Invalid or revoked refresh token")
    refresh_store.revoke(claims["jti"], claims["sub"])
    return _issue_tokens(
        claims["sub"], claims["tenant_id"], claims.get("email", ""), refresh_store
    )


@router.post("/auth/logout")
async def logout(
    body: RefreshRequest,
    refresh_store: RefreshTokenStore = Depends(get_refresh_token_store),
) -> dict:
    """Revoke the presented refresh token (this session)."""
    claims = decode_refresh_token(body.refresh_token)
    if claims:
        refresh_store.revoke(claims["jti"], claims["sub"])
    return {"status": "logged out"}


@router.post("/auth/logout-all")
async def logout_all(
    principal: Principal = Depends(get_principal),
    refresh_store: RefreshTokenStore = Depends(get_refresh_token_store),
) -> dict:
    """Revoke every refresh token for the current user (all devices)."""
    if not principal.user_id:
        raise HTTPException(status_code=403, detail="A user session is required")
    revoked = refresh_store.revoke_all(principal.user_id)
    return {"status": "logged out", "sessions_revoked": revoked}


@router.get("/auth/me", response_model=UserResponse)
async def me(principal: Principal = Depends(get_principal)) -> UserResponse:
    if not principal.user_id:
        raise HTTPException(status_code=403, detail="A user session is required")
    return UserResponse(
        id=principal.user_id, email=principal.email or "", tenant_id=principal.tenant_id
    )

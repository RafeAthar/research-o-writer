from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings


async def require_auth(
    x_auth_token: str | None = Header(default=None, alias="X-Auth-Token"),
    settings: Settings = Depends(get_settings),
) -> int:
    """Trivial single-user auth in Phase 1. Returns user_id for the caller."""
    if not x_auth_token or x_auth_token != settings.app_auth_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    return settings.app_default_user_id

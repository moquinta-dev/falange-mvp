import secrets

from fastapi import Depends, Header, HTTPException, status

from app.core.settings import Settings, get_settings


async def require_admin_api_key(
    settings: Settings = Depends(get_settings),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    """Exige API key nos endpoints internos quando ADMIN_API_TOKEN está configurado."""

    if not settings.admin_api_token:
        return

    token = x_api_key
    if token is None and authorization:
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() == "bearer" and credentials:
            token = credentials

    if token is None or not secrets.compare_digest(token, settings.admin_api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

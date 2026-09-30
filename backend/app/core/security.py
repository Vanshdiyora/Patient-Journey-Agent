from typing import Any
import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import settings

bearer = HTTPBearer(auto_error=False)


def unauthorized(detail: str = "Invalid or missing access token") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def validate_token(token: str) -> dict[str, Any]:
    if not settings.azure_tenant_id or not settings.azure_audience or not settings.azure_issuer:
        raise unauthorized("Entra ID is not configured")
    jwks = PyJWKClient(
        f"https://login.microsoftonline.com/{settings.azure_tenant_id}/discovery/v2.0/keys",
        cache_keys=True,
        lifespan=3600,
    )
    try:
        key = jwks.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            audience=settings.azure_audience,
            issuer=settings.azure_issuer,
            options={"require": ["exp", "iat"]},
        )
        if claims.get("tid") != settings.azure_tenant_id:
            raise unauthorized("Unexpected tenant")
        if not claims.get("oid"):
            raise unauthorized("Token does not contain oid")
        return claims
    except HTTPException:
        raise
    except jwt.PyJWTError as exc:
        raise unauthorized("Token validation failed") from exc


def get_claims(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not settings.auth_required:
        return {
            "oid": settings.dev_user_entra_object_id,
            "tid": settings.azure_tenant_id or "local-tenant",
            "name": settings.dev_user_name,
            "email": settings.dev_user_email,
            "roles": [settings.dev_user_role],
        }
    if not credentials:
        raise unauthorized()
    return validate_token(credentials.credentials)

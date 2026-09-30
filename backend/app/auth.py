"""
CarePath authentication against the application user registry (users table).

- Login accepts email + entra_object_id.
- BOTH values are compared against the users table in the database: a user row
  must exist with a matching email AND matching entra_object_id, and be active.
- A signed JWT bound to the user's entra_object_id is returned.
- Every authenticated request re-validates the token AND re-checks the users
  table, so deactivating or removing a user revokes access immediately.

Replace this local bridge with Microsoft Entra ID (OIDC) token validation when
real Entra integration is enabled (see app/core/security.py validate_token).
"""
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)

JWT_SECRET = settings.auth_jwt_secret
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MINUTES = settings.auth_jwt_expires_minutes


class LoginRequest(BaseModel):
    email: EmailStr
    entra_object_id: str


class UserResponse(BaseModel):
    email: EmailStr
    entra_object_id: str
    name: str
    role: str | None = None


def _user_response(user: User) -> dict[str, Any]:
    return {
        "email": user.email,
        "entra_object_id": user.entra_object_id,
        "name": user.display_name or user.email.split("@")[0].replace(".", " ").title(),
        "role": user.role,
    }


def _create_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.entra_object_id,
        "email": user.email,
        "entra_object_id": user.entra_object_id,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRES_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _load_authenticated_user(db: Session, claims: dict[str, Any]) -> User:
    """Re-check the users table so revoked/deactivated users lose access at once."""
    user = (
        db.query(User)
        .filter(
            User.entra_object_id == claims.get("entra_object_id"),
            User.email == claims.get("email"),
        )
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated identity is no longer registered.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Application user is inactive.",
        )
    return user


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Session = Depends(get_db),
):
    """Validate the JWT and re-verify the user against the database."""
    if not credentials:
        if not settings.auth_required:
            # Local development convenience: fall back to the configured dev user.
            user = (
                db.query(User)
                .filter(User.entra_object_id == settings.dev_user_entra_object_id)
                .first()
            )
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No token supplied and no dev user found in the database.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return _user_response(user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = _decode_token(credentials.credentials)
    user = _load_authenticated_user(db, claims)
    return _user_response(user)


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Compare BOTH the email and the Entra object ID against the users table."""
    user = (
        db.query(User)
        .filter(User.email == body.email.lower(), User.entra_object_id == body.entra_object_id)
        .first()
    )
    if not user:
        # Distinguish the case where the email exists but the object ID is wrong.
        email_exists = db.query(User.id).filter(User.email == body.email.lower()).first()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Entra object ID for this email."
            if email_exists
            else "No registered user matches this email and Entra object ID.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Application user is inactive.",
        )

    return {
        "access_token": _create_token(user),
        "token_type": "bearer",
        "user": _user_response(user),
    }


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[dict, Depends(current_user)]):
    return user


def require_auth():
    """Use this dependency on existing endpoints that do not already have HTTPBearer."""
    return Depends(current_user)

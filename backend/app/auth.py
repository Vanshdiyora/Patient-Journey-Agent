"""Email/password authentication backed by bcrypt hashes in PostgreSQL."""
from datetime import datetime, timedelta, timezone
import re
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.passwords import verify_password
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)
JWT_ALGORITHM = "HS256"


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def validate_login_email(cls, value: Any) -> str:
        return normalize_account_email(value)


class UserResponse(BaseModel):
    email: str
    name: str
    role: str

    @field_validator("email", mode="before")
    @classmethod
    def validate_user_email(cls, value: Any) -> str:
        return normalize_account_email(value)


def normalize_account_email(value: Any) -> str:
    """Validate normal emails while allowing seeded, non-deliverable .test accounts."""
    if not isinstance(value, str):
        raise ValueError("Email address must be text.")
    email = value.strip().lower()
    if email.count("@") != 1:
        raise ValueError("Enter a valid email address.")
    local, domain = email.rsplit("@", 1)
    if domain.endswith(".test"):
        # RFC-style simple syntax validation for reserved local test domains.
        if not local or len(local) > 64 or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local):
            raise ValueError("Enter a valid email address.")
        if len(email) > 254 or ".." in local or local.startswith(".") or local.endswith("."):
            raise ValueError("Enter a valid email address.")
        return email
    try:
        return validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc


def user_response(user: User) -> dict[str, Any]:
    return {
        "email": user.email,
        "name": user.display_name or user.email.split("@")[0].replace(".", " ").title(),
        "role": user.role,
    }


def create_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "iat": now,
        "exp": now + timedelta(minutes=settings.auth_jwt_expires_minutes),
    }
    return jwt.encode(payload, settings.auth_jwt_secret, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.auth_jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def load_authenticated_user(db: Session, claims: dict[str, Any]) -> User:
    try:
        user_id = UUID(claims.get("sub", ""))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid authentication token.")

    user = db.query(User).filter(User.id == user_id, User.email == claims.get("email")).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated account is no longer registered.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Application user is inactive.")
    return user


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Session = Depends(get_db),
):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return load_authenticated_user(db, decode_token(credentials.credentials))


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    # Keep the error the same for unknown email and invalid password.
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Application user is inactive.")

    return {"access_token": create_token(user), "token_type": "bearer", "user": user_response(user)}


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(current_user)]):
    return user_response(user)

"""Email/password authentication backed by bcrypt hashes in PostgreSQL."""
from datetime import date, datetime, timedelta, timezone
import re
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.passwords import hash_password, verify_password
from app.models.patient import Patient
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


class SignupRequest(BaseModel):
    """Public self-service signup creates a patient identity only."""
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: str
    role: str = Field(min_length=2, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    # Required only when role == PATIENT (patients.date_of_birth is NOT NULL).
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=30)

    @field_validator("email", mode="before")
    @classmethod
    def validate_signup_email(cls, value: Any) -> str:
        return normalize_account_email(value)

    @field_validator("first_name", "last_name", "gender", mode="before")
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


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


VALID_SIGNUP_ROLES = ("PATIENT",)


def _signup_error(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


@router.post("/signup", status_code=201)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    """
    Create an application account. PATIENT signups also create the linked
    patient record (DOB + gender required). The response matches /auth/login
    so the UI can sign the new user straight in.
    """
    role = body.role.strip().upper()
    if role not in VALID_SIGNUP_ROLES:
        raise _signup_error(422, f"Role must be one of: {', '.join(VALID_SIGNUP_ROLES)}")

    if role == "PATIENT":
        if not body.date_of_birth:
            raise _signup_error(422, "Date of birth is required for patient accounts")
        if body.date_of_birth > date.today():
            raise _signup_error(422, "Date of birth cannot be in the future")
        if not body.gender or not body.gender.strip():
            raise _signup_error(422, "Gender is required for patient accounts")

    email = body.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise _signup_error(409, "An account with this email already exists")
    if role == "PATIENT" and db.query(Patient).filter(Patient.email == email).first():
        raise _signup_error(409, "A patient record with this email already exists")

    from uuid import uuid4

    now = datetime.now(timezone.utc)
    patient_id = None
    if role == "PATIENT":
        patient_id = uuid4()
        db.add(Patient(
            id=patient_id,
            patient_reference=f"WEB-{now.strftime('%Y')}-{uuid4().hex[:8].upper()}",
            first_name=body.first_name,
            last_name=body.last_name,
            email=email,
            date_of_birth=body.date_of_birth,
            gender=body.gender.strip(),
            created_at=now,
            updated_at=now,
        ))

    user = User(
        id=uuid4(),
        email=email,
        password_hash=hash_password(body.password),
        display_name=f"{body.first_name} {body.last_name}" + (" (Patient)" if role == "PATIENT" else ""),
        role=role,
        patient_id=patient_id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Race on the unique email index between the check above and commit.
        db.rollback()
        raise _signup_error(409, "An account with this email already exists")
    db.refresh(user)

    return {
        "access_token": create_token(user),
        "token_type": "bearer",
        "user": user_response(user),
    }

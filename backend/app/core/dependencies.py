from datetime import datetime, timezone
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.auth import bearer as auth_bearer, _decode_token, _load_authenticated_user


def get_current_user(
    credentials=Depends(auth_bearer),
    db: Session = Depends(get_db),
):
    """
    Single auth path for all API endpoints.

    - If a Bearer token is present: decode the JWT and re-verify the user
      against the users table (email + entra_object_id + is_active).
    - If no token and auth is disabled (local development): fall back to the
      configured dev user, auto-creating it on first use.
    """
    if credentials:
        claims = _decode_token(credentials.credentials)
        return _load_authenticated_user(db, claims)

    if not settings.auth_required:
        user = (
            db.query(User)
            .filter(User.entra_object_id == settings.dev_user_entra_object_id)
            .first()
        )
        if not user:
            now = datetime.now(timezone.utc)
            user = User(
                entra_object_id=settings.dev_user_entra_object_id,
                email=settings.dev_user_email,
                display_name=settings.dev_user_name,
                role=settings.dev_user_role,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    raise HTTPException(401, "Missing authentication token")


def require_roles(*roles):
    def checker(user=Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return user
    return checker

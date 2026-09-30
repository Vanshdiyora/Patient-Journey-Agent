from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.auth import bearer as auth_bearer, decode_token, load_authenticated_user


def get_current_user(
    credentials=Depends(auth_bearer),
    db: Session = Depends(get_db),
):
    """Require a valid bearer token for every protected API endpoint."""
    if not credentials:
        raise HTTPException(401, "Missing authentication token", headers={"WWW-Authenticate": "Bearer"})
    return load_authenticated_user(db, decode_token(credentials.credentials))


def require_roles(*roles):
    def checker(user=Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return user
    return checker

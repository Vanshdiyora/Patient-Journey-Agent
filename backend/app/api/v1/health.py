from fastapi import APIRouter
from app.core.database import check_database
router = APIRouter()
@router.get("/health")
def health():
    ok = check_database(); return {"status": "ok" if ok else "degraded", "database": "connected" if ok else "unavailable"}

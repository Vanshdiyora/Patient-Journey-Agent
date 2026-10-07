from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.api.v1 import health, patients, journeys, events, exceptions, agents, actions, dashboard, me, admin, pathways
from app.api.v1.chat import router as chat_router
from app.auth import router as auth_router
api_router=APIRouter()
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(me.router, tags=["patient"])
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(pathways.router)
api_router.include_router(health.router, tags=["health"])
api_router.include_router(patients.router, tags=["patients"])
api_router.include_router(journeys.router, tags=["journeys"])
api_router.include_router(events.router, tags=["events"])
api_router.include_router(exceptions.router, tags=["exceptions"])
api_router.include_router(agents.router, tags=["agents"])
api_router.include_router(actions.router, tags=["actions"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(chat_router, tags=["chat"])

@api_router.get("/users/me")
def me(user=Depends(get_current_user)):
    # Same shape as the login response so the frontend can treat them identically.
    return {
        "email": user.email,
        "name": user.display_name,
        "role": user.role,
    }

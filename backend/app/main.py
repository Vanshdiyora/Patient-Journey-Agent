from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.router import api_router

app = FastAPI(title=settings.app_name, version="2.0.0", description="Patient Journey Orchestrator — deterministic control plane + 3-agent architecture")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(api_router, prefix=settings.api_prefix)

@app.get("/")
def root():
    return {"service": settings.app_name, "version": "2.0.0", "docs": "/docs"}

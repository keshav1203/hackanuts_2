from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select

from .config import settings
from .db import Base, SessionLocal, engine
from .models import User
from .routers import analyses, auth
from .security import hash_password
from .services.groq_client import test_groq_connection


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    if settings.enable_demo:
        with SessionLocal() as db:
            if not db.scalar(select(User).where(User.email == settings.demo_email)):
                db.add(User(email=settings.demo_email, password_hash=hash_password(settings.demo_password)))
                db.commit()
    yield


cors_list = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
for origin in ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"]:
    if origin not in cors_list:
        cors_list.append(origin)

app = FastAPI(title="ScaleAI API", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(analyses.router, prefix="/api/analyses", tags=["analyses"])
Instrumentator().instrument(app).expose(app, include_in_schema=False)  # Prometheus: GET /metrics


@app.get("/health")
@app.get("/api/health")
def health():
    return {"ok": True, "service": "ScaleAI API"}


@app.get("/health/groq")
@app.get("/api/health/groq")
def health_groq():
    """Check Groq API connectivity and configuration without leaking secrets."""
    return test_groq_connection()

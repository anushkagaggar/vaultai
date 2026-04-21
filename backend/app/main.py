from fastapi import FastAPI, Depends
import os
import uvicorn
import logging

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import auth
from app.middleware.auth import get_current_user
from app.models.user import User
from app.routes import expenses
from app.middleware.errors import (
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.vectordb.qdrant_client import init_collection
from app.routes import rag
from app.middleware.logging import log_requests
from app.routes import insights
from app.routes import executions
from app.routes.system import router as system_router
from app.routes import plans

# ── LLMOps Phase 1: structured JSON logging ───────────────────────────────────
from app.agents.ops_logger import configure_logging

# ── LLMOps Phase 3: Prometheus HTTP instrumentation ──────────────────────────
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="VaultAI V3")

# ── LLMOps Phase 3: expose GET /metrics ──────────────────────────────────────
# Must be called before routes are added so every route gets instrumented.
Instrumentator().instrument(app).expose(app)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ────────────────────────────────────────────────────────
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# ── HTTP middleware ───────────────────────────────────────────────────────────
app.middleware("http")(log_requests)

# ── Routers (unchanged) ───────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(expenses.router)
app.include_router(insights.router)
app.include_router(executions.router)
app.include_router(system_router)
app.include_router(plans.router)
app.include_router(rag.router)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# ── LLMOps Phase 1: configure vaultai.ops and vaultai.agents loggers ─────────
configure_logging(log_level="INFO")

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    # Qdrant
    try:
        init_collection()
        print("Qdrant connected")
    except Exception as e:
        print("Qdrant unavailable — RAG disabled:", e)

    # ── LLMOps Phase 2: initialise MLflow experiments ─────────────────────
    # Degrades silently when MLFLOW_TRACKING_URI is not set or server is down.
    try:
        from app.agents.mlflow_tracker import init_mlflow_experiments
        init_mlflow_experiments()
    except Exception as e:
        logging.getLogger("vaultai.ops").warning(
            '{"event":"mlflow_startup_skipped","reason":"%s"}', str(e)
        )

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "VaultAI V3 API Running"}

@app.get("/health")
def health():
    return {"status": "ok", "env": settings.ENV}

@app.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email}

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
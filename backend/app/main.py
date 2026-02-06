from fastapi import FastAPI
from app.config import settings
from app.routes import auth
from app.middleware.auth import get_current_user
from app.models.user import User
from fastapi import Depends
from app.routes import expenses
from app.middleware.errors import (
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
from app.middleware.logging import log_requests
from app.routes import insights

app = FastAPI()
app.include_router(auth.router)
app.include_router(expenses.router)
app.include_router(insights.router)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
app.middleware("http")(log_requests)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://vaultaifrontend-czhf8ik0o-anushkas-projects-d6a64224.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "env": settings.ENV
    }

@app.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email
    }
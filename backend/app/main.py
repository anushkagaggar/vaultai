from fastapi import FastAPI
from app.config import settings
from app.routes import auth

app = FastAPI()
app.include_router(auth.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "env": settings.ENV
    }

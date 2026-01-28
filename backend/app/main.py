from fastapi import FastAPI
from app.config import settings
from app.routes import auth
from app.middleware.auth import get_current_user
from app.models.user import User
from fastapi import Depends

app = FastAPI()
app.include_router(auth.router)


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
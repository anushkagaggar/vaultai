from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str
    SECRET_KEY: str

    class Config:
        env_file = ".env"

class Settings(BaseSettings):
    ENV: str
    SECRET_KEY: str
    DATABASE_URL: str

settings = Settings()

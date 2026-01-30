import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


# Force load .env always
load_dotenv()


class Settings(BaseSettings):
    ENV: str
    SECRET_KEY: str
    DATABASE_URL: str
    TEST_DATABASE_URL: str | None = None


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_ALGORITHM: str = "HS256"



settings = Settings()

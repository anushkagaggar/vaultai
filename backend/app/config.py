from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str
    SECRET_KEY: str

    class Config:
        env_file = ".env"


settings = Settings()

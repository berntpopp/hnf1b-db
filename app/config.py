# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGODB_URI: str
    DATABASE_NAME: str
    JWT_SECRET: str

    class Config:
        env_file = ".env"

settings = Settings()

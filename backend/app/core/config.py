from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List
import os
import json


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Sistema de Gestión de Parque Automotor"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    ALLOWED_ORIGINS: str = '["http://localhost:5173", "http://localhost:3000"]'

    @property
    def cors_origins(self) -> List[str]:
        val = self.ALLOWED_ORIGINS.strip() if isinstance(self.ALLOWED_ORIGINS, str) else ""
        if val.startswith("["):
            try:
                res = json.loads(val)
                if isinstance(res, list):
                    return res
            except Exception:
                pass
        return [origin.strip() for origin in val.split(",") if origin.strip()] or ["*"]

    # Database
    DB_HOST: str = "168.90.177.232"
    DB_PORT: int = 2024
    DB_USER: str = "cid_admin_user"
    DB_PASSWORD: str = ""
    DB_NAME: str = "bbdd-monitoreo-cid"
    DB_SCHEMA: str = "registro_habilitacion"
    DB_SSL: bool = False

    # JWT
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email (Gmail)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_FROM_NAME: str = "Sistema Parque Automotor VMT"

    # Alertas
    ALERT_DAYS_CRITICAL: int = 7
    ALERT_DAYS_WARNING: int = 15
    ALERT_DAYS_INFO: int = 30
    ALERT_SCHEDULE_HOUR: int = 7
    ALERT_SCHEDULE_MINUTE: int = 0

    @property
    def DATABASE_URL(self) -> str:
        """URL para SQLAlchemy async con asyncpg"""
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """URL para Alembic (sync)"""
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

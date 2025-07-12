from pydantic_settings import BaseSettings, SettingsConfigDict
import json
import os

from src.schemas.enums import LoggerLevels


class TgSettings(BaseSettings):
    TG_BOT_TOKEN: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore"
    )


class LoggerSettings(BaseSettings):
    LOG_LEVEL: LoggerLevels = LoggerLevels.INFO
    LOG_FILE_PATH: str = "app_data/logs/app.log"
    LOG_ROTATION: str = "10 MB"
    LOG_RETENTION: str = "7 days"
    LOG_COMPRESSION: str = "gz"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore"
    )


class DBSettings(BaseSettings):
    DB_USER: str = "admin"
    DB_PASSWORD: str = "admin"
    DB_DATABASE: str = "postgres"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432

    @property
    def sqlalchemy_postgresql_url(self):
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_DATABASE}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore"
    )


class RedisSettings(BaseSettings):
    REDIS_USER: str | None = None
    REDIS_PASSWORD: str | None = None
    REDIS_DATABASE: int = 0
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    @property
    def redis_url(self):
        if self.REDIS_USER:
            redis_user = self.REDIS_USER
        else:
            redis_user = ""
        if self.REDIS_PASSWORD:
            redis_password = self.REDIS_PASSWORD
        else:
            redis_password = ""
        return f"redis://{redis_user}:{redis_password}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DATABASE}"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


class GenericSettings(BaseSettings):
    PROXIES_FILE_PATH: str = "proxies.txt"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="allow"
    )

    @classmethod
    def load(cls, json_path="config.json"):
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(**data)
        return cls()


logger_settings = LoggerSettings()
tg_settings = TgSettings()
db_settings = DBSettings()
redis_settings = RedisSettings()
generic_settings = GenericSettings().load()

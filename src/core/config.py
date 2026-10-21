from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Config(BaseSettings):
    DEBUG: bool = False

    API_URL: str

    APP_API_KEY: SecretStr
    BOT_TOKEN: SecretStr
    TEACHER_ID: int
    QUEUE_MAX_SLOTS: int = 100

    PGHOST: str
    PGDATABASE: str
    PGUSER: str
    PGPASSWORD: SecretStr
    PGSSL: bool

    @property
    def tortoise_orm(self) -> dict:
        return {
            "connections": {
                "default": {
                    "engine": "tortoise.backends.asyncpg",
                    "credentials": {
                        "host": self.PGHOST,
                        "port": 5432,
                        "user": self.PGUSER,
                        "password": self.PGPASSWORD.get_secret_value(),
                        "database": self.PGDATABASE,
                        "ssl": self.PGSSL,
                    },
                }
            },
            "apps": {
                "models": {
                    "models": ["src.db.models", "aerich.models"],
                    "default_connection": "default",
                },
            },
        }

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = Config()

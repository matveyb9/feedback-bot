"""
Конфигурация приложения через переменные окружения.
При старте бота все поля валидируются — если обязательная переменная
не задана или имеет неверный формат, бот не запускается.
"""
from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Обязательные ---
    bot_token: SecretStr
    admin_chat_id: int
    database_url: str

    # --- Опциональные ---
    rate_limit_messages: int = 5   # макс. сообщений за окно
    rate_limit_window: int = 60    # окно в секундах
    log_level: str = "INFO"

    # ------------------------------------------------------------------ #
    # Валидация                                                            #
    # ------------------------------------------------------------------ #

    @field_validator("database_url")
    @classmethod
    def normalise_database_url(cls, v: str) -> str:
        """Гарантирует, что URL использует asyncpg-драйвер."""
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL должен начинаться с postgresql:// или postgresql+asyncpg://"
            )
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL должен быть одним из: {', '.join(sorted(allowed))}")
        return upper

    @model_validator(mode="after")
    def validate_rate_limits(self) -> "Config":
        if self.rate_limit_messages < 1:
            raise ValueError("RATE_LIMIT_MESSAGES должен быть >= 1")
        if self.rate_limit_window < 1:
            raise ValueError("RATE_LIMIT_WINDOW должен быть >= 1")
        return self

    @property
    def sync_database_url(self) -> str:
        """URL для синхронных соединений (Alembic)."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Синглтон конфига — инициализируется один раз при первом вызове."""
    return Config()

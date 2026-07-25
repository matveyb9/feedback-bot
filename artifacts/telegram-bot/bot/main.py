"""
Точка входа — запуск бота в режиме long polling.
"""
import asyncio
import logging
import sys

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import get_config
from bot.db.session import create_session_factory
from bot.handlers import setup_routers
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.logging_mw import LoggingMiddleware
from bot.middlewares.rate_limit import RateLimitMiddleware


def _configure_logging(log_level: str) -> None:
    """Настраивает structlog: красивый вывод в TTY, JSON — в prod."""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    if sys.stdout.isatty():
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level, logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


async def main() -> None:
    config = get_config()
    _configure_logging(config.log_level)

    log = structlog.get_logger()
    log.info("bot_starting", admin_chat_id=config.admin_chat_id)

    bot = Bot(
        token=config.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Передаём конфиг через data — доступен в хэндлерах как аргумент `config: Config`
    dp["config"] = config

    session_factory = create_session_factory(config.database_url)

    # --- Middleware (порядок важен) ---
    # LoggingMiddleware — на уровне Update, ловит всё
    dp.update.middleware(LoggingMiddleware())
    # DbSession — нужен всем хэндлерам (и user, и admin)
    dp.message.middleware(DbSessionMiddleware(session_factory))
    # RateLimit — только для сообщений; admin-чат исключён внутри middleware
    dp.message.middleware(
        RateLimitMiddleware(
            limit=config.rate_limit_messages,
            window=config.rate_limit_window,
            admin_chat_id=config.admin_chat_id,
        )
    )

    # --- Роутеры ---
    setup_routers(dp)

    log.info("bot_started")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        await bot.session.close()
        log.info("bot_stopped")


if __name__ == "__main__":
    asyncio.run(main())

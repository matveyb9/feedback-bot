"""
Middleware: структурированное логирование входящих апдейтов.
Логирует тип апдейта и user_id; текст сообщений не пишется в лог
(конфиденциальность пользователей).
"""
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update

logger = structlog.get_logger()


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Update):
            update_type = event.event_type
            user_id: int | None = None
            chat_id: int | None = None

            inner = event.event
            if isinstance(inner, Message) and inner.from_user:
                user_id = inner.from_user.id
                chat_id = inner.chat.id

            log = logger.bind(update_type=update_type, user_id=user_id, chat_id=chat_id)
            log.debug("update_received")
            try:
                result = await handler(event, data)
                log.debug("update_handled")
                return result
            except Exception as exc:
                log.error("update_handler_error", error=str(exc))
                raise

        return await handler(event, data)

"""
Middleware: in-memory sliding window rate limiter.

Не требует Redis — состояние хранится в памяти процесса.
При необходимости масштабирования (несколько процессов / реплик)
замените на Redis-based реализацию.

Сообщения из admin-чата не ограничиваются.
"""
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import Message

logger = structlog.get_logger()


class RateLimitMiddleware(BaseMiddleware):
    def __init__(
        self,
        *,
        limit: int = 5,
        window: int = 60,
        admin_chat_id: int,
    ) -> None:
        """
        :param limit: макс. количество сообщений за окно
        :param window: размер окна в секундах
        :param admin_chat_id: чат операторов — не ограничивается
        """
        self._limit = limit
        self._window = window
        self._admin_chat_id = admin_chat_id
        # {user_id: [timestamp, ...]} — sliding window timestamps
        self._history: dict[int, list[float]] = defaultdict(list)

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        # Пропускаем не-Message события и admin-чат
        if not isinstance(event, Message):
            return await handler(event, data)
        if event.chat.id == self._admin_chat_id:
            return await handler(event, data)
        if event.from_user is None:
            return await handler(event, data)

        user_id = event.from_user.id
        now = time.monotonic()
        cutoff = now - self._window

        # Чистим устаревшие записи
        history = self._history[user_id]
        self._history[user_id] = [ts for ts in history if ts > cutoff]

        if len(self._history[user_id]) >= self._limit:
            logger.info("rate_limit_exceeded", user_id=user_id)
            await event.answer(
                "⚠️ Вы отправляете слишком много сообщений. "
                f"Пожалуйста, подождите {self._window} секунд."
            )
            return None  # прерываем цепочку, хэндлер не вызывается

        self._history[user_id].append(now)
        return await handler(event, data)

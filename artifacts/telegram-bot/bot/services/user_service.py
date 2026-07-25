"""
Сервис: управление пользователями (бан/разбан, статистика).
Вынесен отдельно от FeedbackService для чистоты разделения обязанностей
и будущего переиспользования в FastAPI (Вариант B).
"""
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repository import MessageRepository, UserRepository

logger = structlog.get_logger()


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._user_repo = UserRepository(session)
        self._msg_repo = MessageRepository(session)

    async def ban(self, telegram_id: int) -> bool:
        """Блокирует пользователя. Возвращает True, если пользователь найден."""
        found = await self._user_repo.set_banned(telegram_id, is_banned=True)
        if found:
            await self._session.commit()
            logger.info("user_banned", telegram_id=telegram_id)
        return found

    async def unban(self, telegram_id: int) -> bool:
        """Разблокирует пользователя. Возвращает True, если пользователь найден."""
        found = await self._user_repo.set_banned(telegram_id, is_banned=False)
        if found:
            await self._session.commit()
            logger.info("user_unbanned", telegram_id=telegram_id)
        return found

    async def get_stats(self) -> dict[str, int]:
        """Возвращает агрегированную статистику."""
        user_stats = await self._user_repo.get_stats()
        total_msgs = await self._msg_repo.count_incoming()
        msgs_24h = await self._msg_repo.count_last_24h()
        return {**user_stats, "total_messages": total_msgs, "messages_24h": msgs_24h}

    async def get_recent_users(self, limit: int = 10) -> list[dict[str, object]]:
        """Возвращает последних пользователей в формате, удобном для отображения."""
        users = await self._user_repo.get_recent(limit)
        return [
            {
                "telegram_id": u.telegram_id,
                "display_name": u.display_name(),
                "username": u.username,
                "is_banned": u.is_banned,
            }
            for u in users
        ]

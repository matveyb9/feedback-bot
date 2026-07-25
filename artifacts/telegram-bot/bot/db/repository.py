"""
Repository-слой — единственное место, где выполняются SQL-запросы.
Сервисы и хэндлеры работают только через репозитории.
Это обеспечивает лёгкое переиспользование в будущем FastAPI-слое (Вариант B).
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import ContentType, MessageDirection, TgMessage, TgUser


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_telegram_id(self, telegram_id: int) -> TgUser | None:
        result = await self._s.execute(
            select(TgUser).where(TgUser.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> TgUser | None:
        return await self._s.get(TgUser, user_id)

    async def upsert(
        self,
        *,
        telegram_id: int,
        first_name: str,
        username: str | None,
        last_name: str | None,
    ) -> TgUser:
        """Создаёт пользователя или обновляет его данные (имя/username могут меняться)."""
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            user = TgUser(
                telegram_id=telegram_id,
                first_name=first_name,
                username=username,
                last_name=last_name,
            )
            self._s.add(user)
        else:
            user.first_name = first_name
            user.username = username
            user.last_name = last_name
        await self._s.flush()
        return user

    async def set_banned(self, telegram_id: int, *, is_banned: bool) -> bool:
        """Возвращает True, если пользователь найден и обновлён."""
        result = await self._s.execute(
            update(TgUser)
            .where(TgUser.telegram_id == telegram_id)
            .values(is_banned=is_banned)
        )
        await self._s.flush()
        return result.rowcount > 0  # type: ignore[return-value]

    async def get_stats(self) -> dict[str, int]:
        total: int = await self._s.scalar(select(func.count()).select_from(TgUser)) or 0
        banned: int = (
            await self._s.scalar(
                select(func.count()).select_from(TgUser).where(TgUser.is_banned.is_(True))
            )
            or 0
        )
        return {"total": total, "banned": banned, "active": total - banned}

    async def get_recent(self, limit: int = 10) -> list[TgUser]:
        result = await self._s.execute(
            select(TgUser).order_by(TgUser.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(
        self,
        *,
        user_id: int,
        telegram_message_id: int,
        direction: MessageDirection,
        content_type: ContentType,
        text: str | None = None,
        file_id: str | None = None,
        caption: str | None = None,
        admin_msg_id: int | None = None,
    ) -> TgMessage:
        msg = TgMessage(
            user_id=user_id,
            telegram_message_id=telegram_message_id,
            direction=direction,
            content_type=content_type,
            text=text,
            file_id=file_id,
            caption=caption,
            admin_msg_id=admin_msg_id,
        )
        self._s.add(msg)
        await self._s.flush()
        return msg

    async def get_by_admin_msg_id(self, admin_msg_id: int) -> TgMessage | None:
        result = await self._s.execute(
            select(TgMessage).where(TgMessage.admin_msg_id == admin_msg_id)
        )
        return result.scalar_one_or_none()

    async def count_incoming(self) -> int:
        return (
            await self._s.scalar(
                select(func.count())
                .select_from(TgMessage)
                .where(TgMessage.direction == MessageDirection.INCOMING)
            )
            or 0
        )

    async def count_incoming_since(self, since: datetime) -> int:
        return (
            await self._s.scalar(
                select(func.count())
                .select_from(TgMessage)
                .where(
                    TgMessage.direction == MessageDirection.INCOMING,
                    TgMessage.created_at >= since,
                )
            )
            or 0
        )

    async def count_last_24h(self) -> int:
        since = datetime.now(tz=timezone.utc) - timedelta(hours=24)
        return await self.count_incoming_since(since)

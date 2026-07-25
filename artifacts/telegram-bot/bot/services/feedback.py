"""
Сервис: обработка входящих обращений и ответов операторов.

Вся бизнес-логика сосредоточена здесь — хэндлеры только вызывают
методы сервиса и не содержат логики сами по себе.
Это позволяет переиспользовать сервис в FastAPI (Вариант B).
"""
import html
from typing import Any

import structlog
from aiogram import Bot
from aiogram.types import Message as TgMsg
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import ContentType, MessageDirection
from bot.db.repository import MessageRepository, UserRepository

logger = structlog.get_logger()

# Максимальная длина текста для хранения в БД (лимит Telegram — 4096)
_MAX_TEXT_LEN = 4096


class FeedbackService:
    def __init__(self, session: AsyncSession, bot: Bot, admin_chat_id: int) -> None:
        self._session = session
        self._bot = bot
        self._admin_chat_id = admin_chat_id
        self._user_repo = UserRepository(session)
        self._msg_repo = MessageRepository(session)

    # ------------------------------------------------------------------ #
    # Публичные методы                                                     #
    # ------------------------------------------------------------------ #

    async def process_user_message(self, message: TgMsg) -> None:
        """Принимает сообщение от пользователя, пересылает в admin-чат, сохраняет в БД."""
        from_user = message.from_user
        if from_user is None:
            return

        # 1. Upsert пользователя
        user = await self._user_repo.upsert(
            telegram_id=from_user.id,
            first_name=from_user.first_name,
            username=from_user.username,
            last_name=from_user.last_name,
        )

        if user.is_banned:
            # Молча игнорируем — не сообщаем о блокировке, чтобы не раскрывать механизм
            logger.info("message_from_banned_user", user_id=from_user.id)
            return

        # 2. Определяем тип контента
        content_type, text, file_id, caption = _extract_content(message)

        # 3. Формируем уведомление для операторов
        user_link = _format_user_link(from_user)
        notification_text = (
            f"📩 <b>Новое обращение</b>\n"
            f"👤 {user_link}\n"
            f"🆔 <code>{from_user.id}</code>\n"
        )

        if content_type == ContentType.TEXT and text:
            notification_text += f"\n{html.escape(text)}\n"

        notification_text += "\n💬 <i>Ответьте на это сообщение, чтобы написать пользователю.</i>"

        # 4. Отправляем в admin-чат
        sent = await self._bot.send_message(
            chat_id=self._admin_chat_id,
            text=notification_text,
        )

        # Для медиа-сообщений — копируем само медиа следом
        if content_type != ContentType.TEXT and content_type != ContentType.STICKER:
            try:
                await self._bot.copy_message(
                    chat_id=self._admin_chat_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                )
            except Exception as exc:
                # Не критично: уведомление уже отправлено
                logger.warning("failed_to_copy_media", error=str(exc), user_id=from_user.id)
        elif content_type == ContentType.STICKER:
            # Стикеры copy_message не поддерживает через все версии — используем forward
            try:
                await self._bot.forward_message(
                    chat_id=self._admin_chat_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                )
            except Exception as exc:
                logger.warning("failed_to_forward_sticker", error=str(exc), user_id=from_user.id)

        # 5. Сохраняем в БД
        await self._msg_repo.create(
            user_id=user.id,
            telegram_message_id=message.message_id,
            direction=MessageDirection.INCOMING,
            content_type=content_type,
            text=text,
            file_id=file_id,
            caption=caption,
            admin_msg_id=sent.message_id,
        )
        await self._session.commit()

        # 6. Подтверждаем получение пользователю
        await message.answer("✅ Ваше сообщение получено. Мы свяжемся с вами в ближайшее время.")

        logger.info(
            "feedback_received",
            user_id=from_user.id,
            content_type=content_type.value,
        )

    async def process_admin_reply(self, message: TgMsg, replied_to_msg_id: int) -> None:
        """Доставляет ответ оператора пользователю."""
        # Ищем исходное обращение по ID уведомления в admin-чате
        original = await self._msg_repo.get_by_admin_msg_id(replied_to_msg_id)
        if original is None:
            # Оператор ответил не на уведомление бота — игнорируем
            return

        user = await self._user_repo.get_by_id(original.user_id)
        if user is None:
            logger.error("orphan_message_user_not_found", user_id=original.user_id)
            return

        if user.is_banned:
            await message.answer("⚠️ Пользователь заблокирован, сообщение не отправлено.")
            return

        # Копируем ответ оператора пользователю (сохраняет форматирование/медиа)
        try:
            await self._bot.copy_message(
                chat_id=user.telegram_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
        except Exception as exc:
            logger.error("failed_to_deliver_reply", error=str(exc), target_user_id=user.telegram_id)
            await message.answer(f"❌ Не удалось доставить сообщение: {exc}")
            return

        # Сохраняем ответ
        content_type, text, file_id, caption = _extract_content(message)
        await self._msg_repo.create(
            user_id=user.id,
            telegram_message_id=message.message_id,
            direction=MessageDirection.OUTGOING,
            content_type=content_type,
            text=text,
            file_id=file_id,
            caption=caption,
        )
        await self._session.commit()

        # Подтверждаем оператору
        user_display = f"@{user.username}" if user.username else str(user.telegram_id)
        await message.answer(f"✅ Ответ отправлен пользователю {html.escape(user_display)}.")

        logger.info(
            "admin_reply_delivered",
            operator_id=message.from_user.id if message.from_user else None,
            target_user_id=user.telegram_id,
        )


# ------------------------------------------------------------------ #
# Вспомогательные функции (приватные)                                  #
# ------------------------------------------------------------------ #

def _extract_content(
    message: TgMsg,
) -> tuple[ContentType, str | None, str | None, str | None]:
    """
    Извлекает тип контента, текст, file_id и caption из сообщения.
    Возвращает (content_type, text, file_id, caption).
    """
    if message.text:
        return ContentType.TEXT, message.text[:_MAX_TEXT_LEN], None, None
    if message.photo:
        largest = message.photo[-1]  # последний — наибольшее разрешение
        caption = (message.caption or "")[:_MAX_TEXT_LEN] or None
        return ContentType.PHOTO, None, largest.file_id, caption
    if message.document:
        caption = (message.caption or "")[:_MAX_TEXT_LEN] or None
        return ContentType.DOCUMENT, None, message.document.file_id, caption
    if message.voice:
        return ContentType.VOICE, None, message.voice.file_id, None
    if message.video:
        caption = (message.caption or "")[:_MAX_TEXT_LEN] or None
        return ContentType.VIDEO, None, message.video.file_id, caption
    if message.sticker:
        return ContentType.STICKER, None, message.sticker.file_id, None
    return ContentType.OTHER, None, None, None


def _format_user_link(user: Any) -> str:
    """Форматирует ссылку на пользователя для HTML-сообщения в Telegram."""
    parts = [user.first_name]
    if user.last_name:
        parts.append(user.last_name)
    name = html.escape(" ".join(parts))

    if user.username:
        return f'<a href="tg://user?id={user.id}">{name}</a> (@{html.escape(user.username)})'
    return f'<a href="tg://user?id={user.id}">{name}</a>'

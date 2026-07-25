"""
Хэндлеры для операторов в admin-чате.
Все хэндлеры этого роутера защищены фильтром AdminChatFilter —
команды не работают вне admin-чата.
"""
import html

import structlog
from aiogram import Bot, F, Router
from aiogram.filters import BaseFilter, Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.services.feedback import FeedbackService
from bot.services.user_service import UserService

logger = structlog.get_logger()

router = Router(name="admin")


class AdminChatFilter(BaseFilter):
    """Пропускает только сообщения из сконфигурированного admin-чата."""

    async def __call__(self, message: Message, config: Config) -> bool:
        return message.chat.id == config.admin_chat_id


# Применяем фильтр ко всем хэндлерам роутера
router.message.filter(AdminChatFilter())


# ------------------------------------------------------------------ #
# Ответ пользователю                                                   #
# ------------------------------------------------------------------ #


@router.message(F.reply_to_message)
async def handle_admin_reply(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    config: Config,
) -> None:
    """
    Оператор ответил (reply) на уведомление бота → доставляем ответ пользователю.
    Если reply не на уведомление бота — молча игнорируем.
    """
    if message.reply_to_message is None:
        return

    service = FeedbackService(session, bot, config.admin_chat_id)
    try:
        await service.process_admin_reply(message, message.reply_to_message.message_id)
    except Exception as exc:
        logger.error("admin_reply_error", error=str(exc), exc_info=True)
        await message.answer("❌ Ошибка при отправке ответа. Подробности в логах.")


# ------------------------------------------------------------------ #
# Команды управления                                                   #
# ------------------------------------------------------------------ #


@router.message(Command("ban"))
async def cmd_ban(message: Message, session: AsyncSession) -> None:
    """
    /ban <telegram_id> — заблокировать пользователя.
    Бот перестаёт принимать сообщения от этого пользователя.
    """
    telegram_id = _parse_user_id_from_command(message)
    if telegram_id is None:
        await message.answer("⚠️ Использование: <code>/ban &lt;telegram_id&gt;</code>")
        return

    service = UserService(session)
    found = await service.ban(telegram_id)
    if found:
        await message.answer(f"🚫 Пользователь <code>{telegram_id}</code> заблокирован.")
    else:
        await message.answer(
            f"❓ Пользователь <code>{telegram_id}</code> не найден в базе.\n"
            "Убедитесь, что он когда-либо писал боту."
        )


@router.message(Command("unban"))
async def cmd_unban(message: Message, session: AsyncSession) -> None:
    """
    /unban <telegram_id> — разблокировать пользователя.
    """
    telegram_id = _parse_user_id_from_command(message)
    if telegram_id is None:
        await message.answer("⚠️ Использование: <code>/unban &lt;telegram_id&gt;</code>")
        return

    service = UserService(session)
    found = await service.unban(telegram_id)
    if found:
        await message.answer(f"✅ Пользователь <code>{telegram_id}</code> разблокирован.")
    else:
        await message.answer(
            f"❓ Пользователь <code>{telegram_id}</code> не найден в базе."
        )


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession) -> None:
    """Статистика: пользователи, сообщения, активность за 24 ч."""
    service = UserService(session)
    stats = await service.get_stats()
    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total']}</b>\n"
        f"✅ Активных: <b>{stats['active']}</b>\n"
        f"🚫 Заблокированных: <b>{stats['banned']}</b>\n\n"
        f"📨 Всего обращений: <b>{stats['total_messages']}</b>\n"
        f"🕐 За последние 24 ч: <b>{stats['messages_24h']}</b>"
    )
    await message.answer(text)


@router.message(Command("list"))
async def cmd_list(message: Message, session: AsyncSession) -> None:
    """Последние 10 пользователей, написавших боту."""
    service = UserService(session)
    users = await service.get_recent_users(limit=10)

    if not users:
        await message.answer("📭 Пользователей пока нет.")
        return

    lines = ["👥 <b>Последние пользователи:</b>\n"]
    for i, u in enumerate(users, start=1):
        name = html.escape(str(u["display_name"]))
        tid = u["telegram_id"]
        username = f" (@{html.escape(str(u['username']))})" if u["username"] else ""
        banned = " 🚫" if u["is_banned"] else ""
        lines.append(f"{i}. <a href=\"tg://user?id={tid}\">{name}</a>{username} — <code>{tid}</code>{banned}")

    await message.answer("\n".join(lines))


# ------------------------------------------------------------------ #
# Вспомогательные функции                                              #
# ------------------------------------------------------------------ #


def _parse_user_id_from_command(message: Message) -> int | None:
    """
    Парсит Telegram ID из аргумента команды (/ban 123456789).
    Возвращает None если аргумент отсутствует или не является целым числом.
    """
    if message.text is None:
        return None
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None
    try:
        return int(parts[1].strip())
    except ValueError:
        return None

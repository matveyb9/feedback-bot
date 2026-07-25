"""
Хэндлеры для пользовательских сообщений.
Все обращения из приватных чатов попадают сюда.
"""
import structlog
from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import Config
from bot.services.feedback import FeedbackService

logger = structlog.get_logger()

router = Router(name="user")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Приветствие при первом запуске или команде /start."""
    await message.answer(
        "👋 <b>Здравствуйте!</b>\n\n"
        "Напишите ваше сообщение — мы его получим и обязательно ответим.\n\n"
        "Поддерживаются: текст, фото, документы, голосовые и видео.",
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "ℹ️ <b>Как это работает:</b>\n\n"
        "1. Напишите ваше обращение (текст, фото, документ, голосовое)\n"
        "2. Бот передаст его операторам\n"
        "3. Вы получите ответ прямо в этом чате\n\n"
        "Это всё — никаких команд не нужно.",
    )


@router.callback_query(lambda c: c.data == "write_message")
async def cb_write_message(callback: CallbackQuery) -> None:
    """Обработка нажатия кнопки «Написать сообщение» из /start."""
    await callback.answer()
    if callback.message:
        await callback.message.answer("✏️ Просто напишите ваше сообщение:")


@router.message()
async def handle_message(
    message: Message,
    bot: Bot,
    session: AsyncSession,
    config: Config,
) -> None:
    """Универсальный хэндлер: принимает любой тип контента от пользователя."""
    # Игнорируем сообщения без отправителя (технические/системные)
    if message.from_user is None:
        return

    service = FeedbackService(session, bot, config.admin_chat_id)
    try:
        await service.process_user_message(message)
    except Exception as exc:
        logger.error(
            "user_message_processing_error",
            user_id=message.from_user.id,
            error=str(exc),
            exc_info=True,
        )
        await message.answer(
            "⚠️ Произошла ошибка при отправке сообщения. Попробуйте позже."
        )

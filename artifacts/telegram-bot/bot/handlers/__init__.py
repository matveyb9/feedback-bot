from aiogram import Dispatcher

from bot.handlers.admin import router as admin_router
from bot.handlers.user import router as user_router


def setup_routers(dp: Dispatcher) -> None:
    """
    Регистрирует роутеры в диспетчере.
    Порядок важен: admin_router должен быть первым,
    так как его фильтры более специфичны (admin_chat_id).
    """
    dp.include_router(admin_router)
    dp.include_router(user_router)

"""
Inline-клавиатуры. Пока используется только в user.py для /start.
Расширяйте этот модуль при добавлении Variant B (web admin panel).
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def start_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура под приветственным сообщением."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✉️ Написать сообщение",
                    callback_data="write_message",
                )
            ]
        ]
    )

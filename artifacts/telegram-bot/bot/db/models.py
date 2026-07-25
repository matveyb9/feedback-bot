"""
ORM-модели. Таблицы имеют префикс tg_ чтобы не конфликтовать
с другими пакетами в монорепе.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.db.base import Base


class MessageDirection(str, enum.Enum):
    INCOMING = "incoming"   # пользователь → бот
    OUTGOING = "outgoing"   # бот → пользователь (ответ оператора)


class ContentType(str, enum.Enum):
    TEXT = "text"
    PHOTO = "photo"
    DOCUMENT = "document"
    VOICE = "voice"
    VIDEO = "video"
    STICKER = "sticker"
    OTHER = "other"


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class TgUser(Base):
    __tablename__ = "tg_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=_utcnow,
        onupdate=_utcnow,
    )

    messages: Mapped[list["TgMessage"]] = relationship("TgMessage", back_populates="user")

    def display_name(self) -> str:
        parts = [self.first_name]
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts)


class TgMessage(Base):
    __tablename__ = "tg_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("tg_users.id"), nullable=False, index=True)

    # ID оригинального сообщения в чате пользователя
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # ID уведомления в admin-чате (для привязки ответов оператора)
    admin_msg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection, name="messagedirection"), nullable=False
    )
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, name="contenttype"), nullable=False
    )

    # Для текстовых сообщений — сам текст (до 4096 символов — лимит Telegram)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Для медиа — Telegram file_id
    file_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Подпись к медиа
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_utcnow
    )

    user: Mapped["TgUser"] = relationship("TgUser", back_populates="messages")

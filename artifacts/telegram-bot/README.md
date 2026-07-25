# feedback-tgbot

Open-source Telegram feedback bot. Пользователи пишут боту — сообщения поступают в admin-чат, операторы отвечают через reply.

## Возможности

- Приём текста, фото, документов, голосовых, видео, стикеров
- Пересылка обращений в admin-чат с данными отправителя
- Ответ пользователю через reply в admin-чате
- Rate limiting (защита от флуда)
- Блокировка пользователей (`/ban` / `/unban`)
- Статистика и список пользователей
- Полное логирование (structlog, JSON в prod)
- PostgreSQL + Alembic миграции

## Требования

- Python 3.12+
- PostgreSQL 14+
- [uv](https://docs.astral.sh/uv/) или pip

## Настройка

### 1. Переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

```env
BOT_TOKEN=123456:ABC...          # Токен от @BotFather (обязательно)
ADMIN_CHAT_ID=-1001234567890     # ID группы/супергруппы для операторов (обязательно)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/feedback_bot  # (обязательно)

# Опциональные
RATE_LIMIT_MESSAGES=5            # Макс. сообщений от пользователя (по умолчанию: 5)
RATE_LIMIT_WINDOW=60             # Окно rate limit в секундах (по умолчанию: 60)
LOG_LEVEL=INFO                   # DEBUG | INFO | WARNING | ERROR (по умолчанию: INFO)
```

> **Admin chat:** бот должен быть добавлен в группу как администратор с правом отправки сообщений.

### 2. Установка зависимостей

```bash
# с uv (рекомендуется)
uv sync

# или с pip
pip install -e .
```

### 3. Миграции базы данных

```bash
# с uv
uv run alembic upgrade head

# или напрямую
alembic upgrade head
```

### 4. Запуск

```bash
# с uv
uv run python -m bot.main

# или напрямую
python -m bot.main
```

## Структура проекта

```
artifacts/telegram-bot/
├── bot/
│   ├── config.py            # Конфигурация (pydantic-settings)
│   ├── main.py              # Точка входа
│   ├── handlers/
│   │   ├── user.py          # /start и обработка сообщений от пользователей
│   │   └── admin.py         # Команды и ответы операторов
│   ├── middlewares/
│   │   ├── db.py            # Инъекция DB-сессии
│   │   ├── rate_limit.py    # Rate limiting (in-memory)
│   │   └── logging_mw.py   # Структурированное логирование апдейтов
│   ├── services/
│   │   ├── feedback.py      # Бизнес-логика обработки обращений
│   │   └── user_service.py  # Управление пользователями
│   ├── db/
│   │   ├── base.py          # DeclarativeBase
│   │   ├── models.py        # ORM-модели (TgUser, TgMessage)
│   │   ├── repository.py    # CRUD-слой (UserRepository, MessageRepository)
│   │   ├── session.py       # Фабрика async-сессий
│   │   └── migrations/      # Alembic миграции
│   └── keyboards/
│       └── inline.py        # Inline-клавиатуры
├── pyproject.toml
├── alembic.ini
└── README.md
```

## Команды операторов

Все команды работают только в admin-чате:

| Команда | Описание |
|---|---|
| `/ban <telegram_id>` | Заблокировать пользователя |
| `/unban <telegram_id>` | Разблокировать пользователя |
| `/stats` | Статистика (пользователи, сообщения) |
| `/list` | Последние 10 пользователей |

## Как отвечать пользователям

1. Найдите уведомление от бота в admin-чате
2. Нажмите **Reply** на уведомление (не на скопированное медиа)
3. Напишите ответ — бот доставит его пользователю

## Расширение (Вариант B — Web Admin Panel)

Архитектура спроектирована для будущего расширения:
- `services/` — бизнес-логика, повторно используется в FastAPI
- `db/repository.py` — паттерн Repository, не зависит от Telegram
- `config.py` — легко добавить новые параметры

## Лицензия

MIT

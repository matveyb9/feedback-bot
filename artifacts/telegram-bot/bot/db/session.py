from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def create_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """
    Создаёт фабрику async-сессий.
    expire_on_commit=False — объекты остаются доступны после commit(),
    что важно для async-кода (lazy-loading не работает async).
    """
    engine = create_async_engine(
        database_url,
        echo=False,           # не логировать SQL в prod; при необходимости включить через LOG_LEVEL=DEBUG
        pool_pre_ping=True,   # проверять соединение перед использованием
        pool_size=5,
        max_overflow=10,
    )
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

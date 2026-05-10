from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql+asyncpg://" + database_url.removeprefix("postgres://")
    if database_url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + database_url.removeprefix("postgresql://")
    return database_url


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(normalize_database_url(database_url))


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@dataclass(frozen=True)
class PostgresSessionManager:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]

    @classmethod
    def from_url(cls, database_url: str) -> PostgresSessionManager:
        engine = create_engine(database_url)
        return cls(engine=engine, session_factory=create_session_factory(engine))

    async def dispose(self) -> None:
        await self.engine.dispose()

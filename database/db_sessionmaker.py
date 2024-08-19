from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from shared.app_config import app_config


class DatabaseSessionManager:
    def __init__(self, echo: bool = False, expire_on_commit: bool = False):
        """
        Initialize the database session manager.
        """
        self.engine = create_async_engine(
            app_config.database.url,
            future=True,
            echo=echo,
            pool_size=30,
            max_overflow=10,
            pool_recycle=59,
        )
        self.sessionmaker = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=expire_on_commit
        )

    def get_sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        """
        Get the async session maker.

        Returns:
        - async_sessionmaker: The session maker instance.
        """
        return self.sessionmaker

    async def dispose(self):
        await self.engine.dispose()


# Initialize the manager
db_manager = DatabaseSessionManager(echo=app_config.database.echo, expire_on_commit=False)

async_dbsession: async_sessionmaker[AsyncSession] = db_manager.get_sessionmaker()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_dbsession() as session:
        yield session

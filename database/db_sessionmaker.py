import asyncio
import atexit
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from shared.app_config import app_config
from sqlalchemy.ext.asyncio import async_sessionmaker


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
        """
        Dispose of the SQLAlchemy engine bound to the async session.
        """
        await self.engine.dispose()

    def dispose_sync(self):
        """
        Synchronous wrapper for dispose to use with atexit.
        """
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(self.dispose())
        else:
            loop.run_until_complete(self.dispose())


# Initialize the manager
db_manager = DatabaseSessionManager(echo=True, expire_on_commit=False)

async_dbsession: async_sessionmaker[AsyncSession] = db_manager.get_sessionmaker()

# Register the dispose method to be called on application exit
atexit.register(db_manager.dispose_sync)

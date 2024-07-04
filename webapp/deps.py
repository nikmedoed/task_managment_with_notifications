import os
from database import async_dbsession
from sqlalchemy.ext.asyncio import AsyncSession
from shared.app_config import app_config

from .titles import CustomJinja2Templates
from .utils.RedisStore import RedisTokenManager

redis = RedisTokenManager(app_config.redis.create_connector(RedisTokenManager),
                          jwt_secret_key=app_config.telegram.jwt_secret_key)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

templates = CustomJinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


async def get_db() -> AsyncSession:
    async with async_dbsession() as session:
        yield session

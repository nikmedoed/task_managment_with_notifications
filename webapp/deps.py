import os
from database import async_dbsession
from sqlalchemy.ext.asyncio import AsyncSession
from shared.app_config import app_config

from .utils.RedisStore import RedisTokenManager

from fastapi.templating import Jinja2Templates

redis = RedisTokenManager(**app_config.redis.dict(), jwt_secret_key=app_config.telegram.jwt_secret_key)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


async def get_db() -> AsyncSession:
    async with async_dbsession() as session:
        yield session

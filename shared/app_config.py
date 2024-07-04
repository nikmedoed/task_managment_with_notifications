from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv, find_dotenv
from typing import Optional
import os

DOTENV_PATH = find_dotenv()
if not DOTENV_PATH:
    DOTENV_PATH = os.path.join(os.path.dirname(__file__), '../.env')

load_dotenv(DOTENV_PATH)


class DatabaseConfig(BaseSettings):
    root_password: str
    database: str
    user: str
    password: str
    host: str = "localhost"
    port: int = 3306

    @property
    def url(self) -> str:
        return f"mysql+aiomysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    model_config = SettingsConfigDict(env_prefix='MYSQL_', env_file=DOTENV_PATH, extra='ignore')


class TelegramConfig(BaseSettings):
    token: str
    username: str
    jwt_secret_key: str

    model_config = SettingsConfigDict(env_prefix='BOT_', env_file=DOTENV_PATH, extra='ignore')


class RedisConfig(BaseSettings):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None

    model_config = SettingsConfigDict(env_prefix='REDIS_', env_file=DOTENV_PATH, extra='ignore')

    def create_connector(self, redis=None):
        if not redis:
            import redis.asyncio as redis

        auth_part = f":{self.password}@" if self.password else ""
        url = f"redis://{auth_part}{self.host}:{self.port}/{self.db}"

        return redis.from_url(url, encoding="utf-8", decode_responses=True)


class AppConfig(BaseSettings):
    database: DatabaseConfig = DatabaseConfig()
    telegram: TelegramConfig = TelegramConfig()
    redis: RedisConfig = RedisConfig()

    model_config = SettingsConfigDict(env_file=DOTENV_PATH, extra='ignore')


def load_config() -> AppConfig:
    return AppConfig()


app_config = load_config()

if __name__ == "__main__":
    print(app_config)
    print(app_config.database.url)

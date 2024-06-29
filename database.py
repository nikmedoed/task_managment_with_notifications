# database.py

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

SQLALCHEMY_DATABASE_URL = f"mysql+aiomysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}@mariadb/{os.getenv('MYSQL_DATABASE')}"

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True, pool_pre_ping=True, encoding='utf8mb4')


AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

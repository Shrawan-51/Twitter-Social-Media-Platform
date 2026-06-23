import sqlite3
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

SQLALCHEMY_DB_URL="sqlite+aiosqlite:///./blog.db"

engine=create_async_engine(
    SQLALCHEMY_DB_URL,
    connect_args={"check_same_thread":False},
)

async_SessionLocal=async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_SessionLocal() as db:
        yield db
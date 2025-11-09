"""Database connection and session management using SQLAlchemy async ORM"""
import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from redis import asyncio as aioredis
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:dev_password@localhost:5432/nerdboard")

# Convert sync postgresql:// to async postgresql+asyncpg://
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Redis Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create async SQLAlchemy engine with connection pooling
# pool_size=20: Keep 20 connections alive in the pool
# max_overflow=30: Allow 30 additional connections under load (total 50 max)
# pool_recycle=3600: Recycle connections every hour to prevent stale connections
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging during development
    pool_size=20,
    max_overflow=30,
    pool_recycle=3600,
    pool_pre_ping=True,  # Verify connection health before using
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for declarative models
Base = declarative_base()

# Redis client (initialized on app startup)
redis_client: aioredis.Redis = None


async def init_redis() -> aioredis.Redis:
    """Initialize Redis connection with async client"""
    global redis_client
    redis_client = await aioredis.from_url(
        REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
    )
    return redis_client


async def close_redis():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI endpoints to get database session.

    Usage in FastAPI:
        @app.get("/items")
        async def read_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_redis() -> aioredis.Redis:
    """
    Dependency for FastAPI endpoints to get Redis client.

    Usage in FastAPI:
        @app.get("/cached-data")
        async def get_cached_data(redis: Redis = Depends(get_redis)):
            value = await redis.get("key")
            return {"cached_value": value}
    """
    return redis_client

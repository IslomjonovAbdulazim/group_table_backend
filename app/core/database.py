# Replace app/core/database.py with this improved version:

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings
import logging

logger = logging.getLogger(__name__)

# Improved engine configuration with connection pooling
engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    # Connection pool settings
    pool_size=10,                    # Number of connections to maintain
    max_overflow=20,                 # Additional connections beyond pool_size
    pool_timeout=30,                 # Timeout for getting connection
    pool_recycle=3600,              # Recycle connections after 1 hour
    pool_pre_ping=True,             # Validate connections before use
    # Echo SQL for debugging (set to False in production)
    echo=False,
    # Additional connection settings
    connect_args={
        "server_settings": {
            "jit": "off",
        },
        "command_timeout": 60,
    }
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
    autocommit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def close_db():
    """Properly close database connections on shutdown"""
    await engine.dispose()
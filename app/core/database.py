from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import NullPool
from .config import settings
import logging

logger = logging.getLogger(__name__)

# Convert PostgreSQL URL to asyncpg
database_url = settings.database_url
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create async engine with proper configuration
engine = create_async_engine(
    database_url,
    echo=False,  # Set to True for SQL debugging
    poolclass=NullPool,  # Use NullPool for better connection management
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,  # Recycle connections every hour
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
    autocommit=False
)

Base = declarative_base()


async def get_db():
    """Dependency to get database session"""
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
    """Create all database tables"""
    try:
        async with engine.begin() as conn:
            # Import all models to ensure they're registered
            from ..models import (
                Admin, Teacher, Group, Student,
                Module, Lesson, Criteria, Grade
            )

            logger.info("Creating database tables...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise


async def close_db():
    """Close database engine"""
    try:
        await engine.dispose()
        logger.info("Database engine disposed")
    except Exception as e:
        logger.error(f"Error disposing database engine: {e}")
# app/database.py
"""Database configuration and session management for PostgreSQL."""

import logging
from typing import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

# Create async engine with proper configuration
engine = create_async_engine(
    settings.DATABASE_URL,
    # Connection pool settings
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=3600,
    # Echo SQL queries in development (set to False in production)
    echo=False,
    # Connection arguments
    connect_args={
        "command_timeout": 60,
        "server_settings": {
            "jit": "off",  # Disable JIT for better predictability in development
        },
    },
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    # Define naming conventions for constraints
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to provide database sessions.

    Yields:
        AsyncSession: Database session for the request

    Example:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            # Use db session here
            pass
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables.

    This should be called on application startup.
    """
    logger.info("Initializing database connection...")

    try:
        async with engine.begin():
            # Import all models to ensure they're registered with Base.metadata
            try:
                from app import models  # noqa: F401

                logger.info("Models imported successfully")
            except ImportError:
                logger.warning(
                    "Models not found - this is expected during initial setup"
                )

            # Create all tables (in production, use Alembic migrations instead)
            # await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized successfully")
        logger.info(
            f"Connected to database: {settings.DATABASE_URL.split('@')[1]}"
        )  # Log without credentials

    except ConnectionRefusedError:
        logger.error("Failed to connect to PostgreSQL database!")
        logger.error("Make sure to start the database services first:")
        logger.error("  1. Run: make hybrid-up")
        logger.error("  2. Wait for containers to be healthy")
        logger.error("  3. Then run: make server")
        raise
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_db() -> None:
    """Close database connections.
    This should be called on application shutdown.
    """
    logger.info("Closing database connections...")
    await engine.dispose()
    logger.info("Database connections closed")

# app/database.py
"""Database configuration and session management for PostgreSQL.

Pool settings and timeouts are loaded from config.yaml.
"""

import logging
from typing import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create async engine with configuration from config.yaml
engine = create_async_engine(
    settings.DATABASE_URL,
    # Connection pool settings (from config.yaml)
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_pre_ping=True,
    pool_recycle=settings.database.pool_recycle_seconds,
    # Echo SQL queries in development (set to False in production)
    echo=False,
    # Connection arguments
    connect_args={
        "command_timeout": settings.database.command_timeout_seconds,
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

    Important: This dependency does NOT auto-commit transactions.
    Endpoints must explicitly call `await db.commit()` to persist changes.
    If an exception occurs, the transaction will be automatically rolled back.

    Yields:
        AsyncSession: Database session for the request

    Example:
        @app.post("/users")
        async def create_user(user: User, db: AsyncSession = Depends(get_db)):
            db.add(user)
            await db.commit()  # Explicit commit required
            await db.refresh(user)
            return user
    """
    async with async_session_maker() as session:
        try:
            yield session
            # No auto-commit - endpoints must commit explicitly
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
            # DEAD CODE: models module does not exist
            # Import all models to ensure they're registered with Base.metadata
            # This import is currently unused as we don't have an app/models.py module
            # TODO: Remove this code block or create app/models.py if needed
            # try:
            #     from app import models  # noqa: F401
            #
            #     logger.info("Models imported successfully")
            # except ImportError:
            #     logger.warning(
            #         "Models not found - this is expected during initial setup"
            #     )
            logger.info(
                "Database initialization - skipping models import "
                "(no models module exists)"
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

# app/database.py
"""Database configuration and session management for PostgreSQL.

Pool settings and timeouts are loaded from config.yaml.
"""

import logging
from typing import AsyncGenerator

import sqlalchemy.exc
from sqlalchemy import MetaData, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, with_loader_criteria

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
        except sqlalchemy.exc.SQLAlchemyError:
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
            pass  # Models are registered via explicit imports in routers

            # Create all tables (in production, use Alembic migrations instead)
            # await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized successfully")
        logger.info(
            f"Connected to database: {settings.DATABASE_URL.split('@')[1]}"
        )  # Log without credentials

    except (ConnectionRefusedError, OSError):
        logger.error("Failed to connect to PostgreSQL database!")
        logger.error("Make sure to start the database services first:")
        logger.error("  1. Run: make hybrid-up")
        logger.error("  2. Wait for containers to be healthy")
        logger.error("  3. Then run: make server")
        raise
    except sqlalchemy.exc.SQLAlchemyError as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_db() -> None:
    """Close database connections.

    This should be called on application shutdown.
    """
    logger.info("Closing database connections...")
    await engine.dispose()
    logger.info("Database connections closed")


def _register_soft_delete_filter() -> None:
    """Attach a global soft-delete filter to the Phenopacket entity.

    Every SELECT touching Phenopacket gets an implicit
    ``deleted_at IS NULL`` predicate unless the statement carries
    ``execution_options(include_deleted=True)``. This mirrors the
    SQLAlchemy docs "Soft-Delete" recipe (do_orm_execute listener
    + with_loader_criteria) and is scoped to the Phenopacket entity
    only — other models are unaffected.

    The listener is registered on the ``Session`` class (the synchronous
    session underlying every ``AsyncSession``). This works for both the
    production ``async_session_maker`` and the test ``test_session_maker``
    that ``tests/conftest.py`` substitutes at runtime, because both share
    the same ``Session`` sync-session class.

    Reference:
        https://docs.sqlalchemy.org/en/20/orm/session_events.html#do-orm-execute
    """
    # Import inside the function to avoid a circular import: database.py is
    # imported early in the app bootstrap before app.phenopackets.models has
    # been loaded. The deferred import here ensures that model registration has
    # already happened by the time the listener fires.
    from app.phenopackets.models import Phenopacket  # noqa: PLC0415

    @event.listens_for(Session, "do_orm_execute")
    def _soft_delete_filter(execute_state: object) -> None:
        if not execute_state.is_select:  # type: ignore[attr-defined]
            return
        if execute_state.execution_options.get("include_deleted", False):  # type: ignore[attr-defined]
            return
        execute_state.statement = execute_state.statement.options(  # type: ignore[attr-defined]
            with_loader_criteria(
                Phenopacket,
                lambda cls: cls.deleted_at.is_(None),
                include_aliases=True,
            )
        )


_register_soft_delete_filter()


async def refresh_materialized_views(
    db: AsyncSession, *, force: bool = False
) -> dict[str, bool]:
    """Refresh all aggregation materialized views.

    Calls the PostgreSQL function `refresh_all_aggregation_views()` to update
    pre-computed statistics after data imports. Uses CONCURRENTLY option to
    allow reads during refresh.

    Args:
        db: Database session
        force: If True, refresh even if auto_refresh_after_import is disabled

    Returns:
        Dict with refresh status for each view (True if refreshed, False if skipped)

    Configuration:
        - materialized_views.enabled: Master switch for using views
        - materialized_views.auto_refresh_after_import: Auto-refresh after imports

    Example:
        >>> async with async_session_maker() as db:
        ...     result = await refresh_materialized_views(db)
        ...     print(result)
        {'mv_feature_aggregation': True, 'mv_disease_aggregation': True, ...}
    """
    views = settings.materialized_views.views
    result: dict[str, bool] = {view: False for view in views}

    # Check if refresh is enabled
    if not settings.materialized_views.enabled:
        logger.debug("Materialized views disabled, skipping refresh")
        return result

    if not force and not settings.materialized_views.auto_refresh_after_import:
        logger.debug("Auto-refresh disabled, skipping (use force=True to override)")
        return result

    logger.info("Refreshing materialized views...")

    try:
        # Use the PostgreSQL function that refreshes all views concurrently
        await db.execute(text("SELECT refresh_all_aggregation_views()"))
        await db.commit()

        for view in views:
            result[view] = True

        logger.info(f"Successfully refreshed {len(views)} materialized views")

    except sqlalchemy.exc.SQLAlchemyError as e:
        logger.warning(f"Failed to refresh materialized views: {e}")
        logger.debug(
            "This may occur if views don't exist yet. "
            "Run 'make db-upgrade' to create them."
        )
        # Don't raise - view refresh is non-critical

    return result

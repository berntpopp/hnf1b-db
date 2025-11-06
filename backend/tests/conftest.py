"""Pytest configuration and shared fixtures."""

import asyncio
import warnings

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# Suppress known harmless asyncpg warning that occurs during interpreter shutdown
# This is a known issue: https://github.com/sqlalchemy/sqlalchemy/issues/8145
warnings.filterwarnings(
    "ignore",
    message="coroutine 'Connection._cancel' was never awaited",
    category=RuntimeWarning,
)


@pytest_asyncio.fixture
async def db_session():
    """Provide a database session for testing.

    Creates a fresh session for each test and handles cleanup.

    Best practices for async cleanup:
    - Explicitly close session before engine disposal
    - Use dispose(close=True) to ensure all connections are closed
    - Shield cleanup operations from cancellation
    """
    # Create test engine (using same database as development for now)
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        # Set pool_recycle to avoid stale connections
        pool_recycle=3600,
    )

    # Create session factory
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Create session
    session = async_session_factory()

    try:
        yield session
    finally:
        # Ensure proper cleanup even if test fails
        try:
            # Rollback any uncommitted changes
            await session.rollback()
        except Exception:
            pass  # Ignore errors during rollback

        # Close session explicitly
        await session.close()

        # Dispose of engine - close all connections
        # Use asyncio.shield to protect cleanup from cancellation
        await asyncio.shield(engine.dispose(close=True))

"""Pytest configuration and shared fixtures."""

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


@pytest_asyncio.fixture
async def db_session():
    """Provide a database session for testing.

    Creates a fresh session for each test and handles cleanup.
    """
    # Create test engine (using same database as development for now)
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
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
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            # Rollback any uncommitted changes
            await session.rollback()
            await session.close()

    # Cleanup engine
    await engine.dispose()

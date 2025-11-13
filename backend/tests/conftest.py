"""Pytest configuration and shared fixtures."""

import asyncio
import warnings

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.password import get_password_hash
from app.config import settings
from app.main import app
from app.models.user import User

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


# Authentication test fixtures


@pytest_asyncio.fixture
async def test_user(db_session):
    """Create test user for authentication tests."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        role="viewer",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    yield user

    # Cleanup
    await db_session.execute(delete(User).where(User.id == user.id))
    await db_session.commit()


@pytest_asyncio.fixture
async def admin_user(db_session):
    """Create admin user for permission tests."""
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("AdminPass123!"),
        role="admin",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    yield user

    await db_session.execute(delete(User).where(User.id == user.id))
    await db_session.commit()


@pytest_asyncio.fixture
async def async_client(db_session):
    """Async HTTP client for API testing."""
    from app.database import get_db

    # Override get_db to use test session
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(test_user, async_client):
    """Get auth headers for authenticated requests."""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={
            "username": test_user.username,
            "password": "TestPass123!",
        },
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_headers(admin_user, async_client):
    """Get auth headers for admin requests."""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={
            "username": admin_user.username,
            "password": "AdminPass123!",
        },
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

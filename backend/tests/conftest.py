"""Pytest configuration and shared fixtures.

Test isolation is provided by a dedicated test database configured in the
root-level ``backend/conftest.py`` (which runs before any ``app.*`` imports).
This module assumes ``DATABASE_URL`` already points at a database whose name
contains ``test``; an assertion below enforces that invariant.

Per-test isolation strategy:

- The app-level ``async_session_maker`` is reused so that tests which spawn
  their own sessions (e.g. race-condition tests) share the same engine as the
  tests which use the ``db_session`` fixture. This means the whole suite sees
  one test database with one connection pool.
- Between tests we ``TRUNCATE`` the small set of mutable tables that test
  fixtures and endpoints write to. Static lookup tables populated by Alembic
  migrations are intentionally left alone so the schema stays valid.
- ``dispose_engine`` runs at session teardown to shut down asyncpg cleanly.
"""

import warnings
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# IMPORTANT: import app.database as a module (not ``from app.database import ...``)
# so that we can rebind its engine / session_maker attributes below. Anything
# that later does ``from app.database import engine`` will then pick up the
# test engine instead of the production-pool engine created at module load.
import app.database as app_database  # noqa: E402
from app.auth.password import get_password_hash
from app.core.config import settings
from app.main import app
from app.models.user import User

# Suppress known harmless asyncpg warning that occurs during interpreter shutdown
# This is a known issue: https://github.com/sqlalchemy/sqlalchemy/issues/8145
warnings.filterwarnings(
    "ignore",
    message="coroutine 'Connection._cancel' was never awaited",
    category=RuntimeWarning,
)


# ---------------------------------------------------------------------------
# Safety guard
# ---------------------------------------------------------------------------
#
# ``backend/conftest.py`` has already rewritten ``DATABASE_URL`` to a test
# database, but if someone adds a new import path or runs pytest from an
# unexpected location we want to fail loudly rather than silently mutate the
# developer's working database.
_TEST_DB_NAME = urlparse(settings.DATABASE_URL).path.lstrip("/").lower()
assert "test" in _TEST_DB_NAME, (
    "Refusing to run tests against a non-test database. "
    f"Resolved DATABASE_URL points at {_TEST_DB_NAME!r}. "
    "See backend/conftest.py and `make db-test-init`."
)


# ---------------------------------------------------------------------------
# Replace the production engine/session_maker with a NullPool-backed test engine
# ---------------------------------------------------------------------------
#
# ``pytest-asyncio`` creates a fresh event loop for each test. A pooled async
# engine holds asyncpg connections bound to the *first* loop they were created
# on, which triggers ``RuntimeError: Event loop is closed`` when subsequent
# tests try to reuse those connections. Using ``NullPool`` forces every
# checkout to open a new connection on the current loop, which makes the test
# suite safe to run regardless of per-test loop scoping.
#
# We dispose of the production engine first (it was created at
# ``app.database`` import time with ``settings.database.pool_size`` etc.) and
# then rebind the module attributes so that every downstream ``from
# app.database import engine`` sees the test engine.
_production_engine = app_database.engine
try:
    import asyncio

    asyncio.get_event_loop().run_until_complete(_production_engine.dispose())
except Exception:
    # If there's no running loop or dispose fails, fall through — the pool
    # will be garbage collected eventually and we've already replaced the
    # module-level reference below.
    pass

test_engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=False,
    connect_args={
        "server_settings": {
            "jit": "off",
        },
    },
)

test_session_maker = async_sessionmaker(
    test_engine,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

app_database.engine = test_engine
app_database.async_session_maker = test_session_maker

# Expose convenient local aliases for the rest of this module.
engine = test_engine
async_session_maker = test_session_maker


# Tables that tests (directly or via endpoints) mutate. Order matters because
# of foreign keys: children before parents. Anything not in this list is left
# untouched so that lookup tables populated by Alembic migrations survive.
_MUTABLE_TABLES: tuple[str, ...] = (
    "phenopacket_audit",
    "phenopackets",
    "variant_annotations",
    "publication_metadata",
    "users",
)


async def _truncate_mutable_tables() -> None:
    """Wipe test-mutable tables in a single transaction.

    Runs before every test so that each test starts from a clean, deterministic
    state. Uses ``TRUNCATE ... RESTART IDENTITY CASCADE`` so that serial/bigint
    primary keys are reset and any FK-dependent rows are removed in lock-step.
    """
    async with engine.begin() as conn:
        joined = ", ".join(_MUTABLE_TABLES)
        await conn.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture(autouse=True)
async def _isolate_database_between_tests():
    """Wipe mutable tables before each test for guaranteed isolation.

    Declared ``autouse=True`` so every test gets a clean database without
    having to remember to request the fixture. No yield body is needed — the
    cleanup runs before the test and the next invocation handles the next
    test's pre-state.
    """
    await _truncate_mutable_tables()
    yield


@pytest_asyncio.fixture
async def db_session():
    """Provide a database session for testing.

    Uses the app-level ``async_session_maker`` so tests share the same engine
    and pool as code under test. Each test gets a fresh session that is rolled
    back and closed at the end.
    """
    session = async_session_maker()
    try:
        yield session
    finally:
        try:
            await session.rollback()
        except Exception:
            # Ignore rollback errors during teardown to avoid masking the
            # original test failure.
            pass
        await session.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _dispose_engine_at_session_end():
    """Dispose of the shared async engine at the end of the test session.

    Without this, asyncpg occasionally logs ``Event loop is closed`` when the
    connection pool is GC'd after pytest tears down its last event loop.
    """
    yield
    try:
        await engine.dispose()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Authentication fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user for authentication tests."""
    # Fresh test DB + autouse truncation means we do not need pre-cleanup here.
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

    # Best-effort cleanup — the autouse truncate will catch anything we miss
    # before the next test runs.
    try:
        await db_session.execute(delete(User).where(User.id == user.id))
        await db_session.commit()
    except Exception:
        try:
            await db_session.rollback()
        except Exception:
            pass


@pytest_asyncio.fixture
async def admin_user(db_session):
    """Create an admin user for permission tests."""
    user = User(
        username="testadmin",
        email="testadmin@example.com",
        hashed_password=get_password_hash("AdminPass123!"),
        role="admin",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    yield user

    try:
        await db_session.execute(delete(User).where(User.id == user.id))
        await db_session.commit()
    except Exception:
        try:
            await db_session.rollback()
        except Exception:
            pass


@pytest_asyncio.fixture
async def async_client(db_session):
    """Async HTTP client for API testing."""
    from app.database import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def dev_auth_client(db_session):
    """Async HTTP client with the Wave 5a dev-auth router mounted.

    The dev router is only registered by ``app/main.py`` when
    ``settings.enable_dev_auth`` and ``settings.environment == "development"``
    are both true at app-import time. The test suite sets those flags to
    production defaults via ``backend/conftest.py``, so by the time this
    fixture runs the router has NOT been included on the shared ``app``.

    We temporarily flip the two ``settings`` attributes, import
    ``app.api.dev_endpoints`` inside the fixture (so the module-level
    assert sees the flipped values on its first evaluation), include the
    router if it isn't already mounted, and restore the flags on
    teardown. The module stays cached in ``sys.modules`` after the first
    run, so subsequent test invocations just re-use the same router
    object.
    """
    from app.core.config import settings as app_settings
    from app.database import get_db

    original_env = app_settings.environment
    original_flag = app_settings.enable_dev_auth
    app_settings.environment = "development"
    app_settings.enable_dev_auth = True

    try:
        # Import AFTER flipping so the module-level assert passes.
        from app.api import dev_endpoints

        if not any(
            getattr(r, "path", "").startswith("/api/v2/dev")
            for r in app.router.routes
        ):
            app.include_router(dev_endpoints.router)

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testclient"
        ) as client:
            yield client

        app.dependency_overrides.clear()
    finally:
        app_settings.environment = original_env
        app_settings.enable_dev_auth = original_flag


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


@pytest_asyncio.fixture
async def cleanup_test_phenopackets(db_session):
    """Legacy cleanup hook retained for backwards compatibility.

    The autouse ``_isolate_database_between_tests`` fixture already truncates
    ``phenopackets`` and ``phenopacket_audit`` before every test, but existing
    tests request this fixture by name. Keep it as a no-op yield so those tests
    continue to work without modification.
    """
    yield


# Silence ``pytest`` unused-import warning for the session fixture above.
_ = pytest

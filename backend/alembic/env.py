import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import your models' metadata here for 'autogenerate' support
# Import Base from database module and all Phenopackets v2 models
try:
    # Import Base from database module
    from app.database import Base

    # Import all Phenopackets v2 models to ensure metadata is complete
    # Using redundant aliases to signal intentional re-exports (models register with Base.metadata)
    from app.phenopackets.models import (
        Cohort as Cohort,
    )
    from app.phenopackets.models import (
        Family as Family,
    )
    from app.phenopackets.models import (
        Phenopacket as Phenopacket,
    )
    from app.phenopackets.models import (
        PhenopacketAudit as PhenopacketAudit,
    )
    from app.phenopackets.models import (
        Resource as Resource,
    )

    target_metadata = Base.metadata
except ImportError:
    # During initial setup, models might not exist yet
    target_metadata = None

# Get database URL from environment variable
database_url = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets",
)

# Override the sqlalchemy.url from config with environment variable
config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an async Engine.

    Associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = database_url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Check if an event loop is already running
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # If a loop is running, run the async migrations in the existing loop
        loop.run_until_complete(run_async_migrations())
    else:
        # Otherwise, create and run a new loop
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

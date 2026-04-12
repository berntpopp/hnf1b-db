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

# Import your models' metadata here for 'autogenerate' support.
#
# Wave 5b Task 2 (Wave 5a exit follow-up #1): import EVERY SQLAlchemy ORM
# model class so ``Base.metadata`` is complete. Missing imports cause
# ``alembic revision --autogenerate`` to emit spurious ``op.drop_table(...)``
# operations for unimported tables. Both Wave 5a schema migrations had to
# be hand-written because autogenerate was unusable before this fix.
#
# If you add a new ORM model anywhere under ``app/``, add it here too.
# ``tests/test_alembic_env_autogenerate.py::test_env_py_imports_all_orm_models``
# statically enforces this at test time.
try:
    # Import Base from database module
    from app.database import Base

    # User model (1).
    from app.models.user import (
        User as User,
    )

    # Phenopackets package (5 models).
    # Redundant ``as`` aliases signal intentional re-exports so ruff/pyflakes
    # does not flag the imports as unused — the import side-effect (model
    # registration with ``Base.metadata``) is what actually matters here.
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

    # Reference package (5 models: genome → genes → transcripts → exons,
    # plus protein_domains).
    from app.reference.models import (
        Exon as Exon,
    )
    from app.reference.models import (
        Gene as Gene,
    )
    from app.reference.models import (
        ProteinDomain as ProteinDomain,
    )
    from app.reference.models import (
        ReferenceGenome as ReferenceGenome,
    )
    from app.reference.models import (
        Transcript as Transcript,
    )

    target_metadata = Base.metadata
except ImportError:
    # During initial setup, models might not exist yet
    from app.database import Base

    target_metadata = Base.metadata


def include_object(object_, name, type_, reflected, compare_to):  # noqa: ARG001
    """Filter non-ORM-managed tables out of autogenerate diffs.

    Wave 5b Task 2: the following tables exist in the live database but
    are intentionally NOT exposed as SQLAlchemy ORM models:

    * ``publication_metadata`` — managed by raw SQL migration
      ``8d988c04336a_add_publication_metadata_table`` and populated via
      the ``publications-sync`` job.
    * ``variant_annotations`` — managed by raw SQL migration
      ``7b2a3c4d5e6f_add_variant_annotations_table`` and populated via
      the VEP annotation pipeline.
    * ``hpo_terms_lookup`` — populated by HPO ingestion jobs
      (``0bd1567a483c_add_phenotype_metadata_to_hpo_lookup`` and
      ``93b3e6984a6c_fix_hpo_lookup_table_repopulation``).
    * ``allelic_state_values``, ``evidence_code_values``,
      ``interpretation_status_values``, ``progress_status_values``,
      ``sex_values`` — phenopackets controlled-vocabulary tables from
      ``88b3a0c19a89_add_phenopacket_controlled_vocabularies``.
    * ``alembic_version`` — alembic's own bookkeeping table.

    Without this filter, ``alembic revision --autogenerate`` emits
    ``op.drop_table(...)`` for every one of them because they are not
    represented in ``Base.metadata``.
    """
    if type_ == "table" and name in {
        "alembic_version",
        "allelic_state_values",
        "evidence_code_values",
        "hpo_terms_lookup",
        "interpretation_status_values",
        "progress_status_values",
        "publication_metadata",
        "sex_values",
        "variant_annotations",
    }:
        return False
    return True


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
        include_object=include_object,
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
        include_object=include_object,
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
    if configuration:
        configuration["sqlalchemy.url"] = database_url

        connectable = async_engine_from_config(
            configuration,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

        await connectable.dispose()
    else:
        # Handle the case where configuration is None, e.g., raise an error or log a warning
        print("Alembic configuration section not found, cannot run async migrations.")


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

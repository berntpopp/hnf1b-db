"""Wave 5b: alembic autogenerate must not drop tables against the live DB.

Wave 5a exit follow-up #1: ``backend/alembic/env.py`` imported only 5 of
the 11 SQLAlchemy ORM model classes, so ``alembic revision --autogenerate``
emitted ``op.drop_table(...)`` for every unimported model (users,
reference_genomes, genes, transcripts, exons, protein_domains) plus the
raw-SQL-managed tables (publication_metadata, variant_annotations, the
HPO/vocabulary lookup tables). Both Wave 5a schema migrations had to be
hand-written because of this drift.

This test programmatically runs alembic's ``compare_metadata`` against
the live test DB and asserts that **no table-level drop** operations
appear. Column/index/FK level drift between the ORM and the live schema
is out of scope for Wave 5b — table drops are the dangerous ones because
they destroy data, and they are what blocked autogenerate being usable.

If a future developer adds a new ORM model and forgets to register it in
``alembic/env.py``'s import block, this test fails because
``Base.metadata`` will not contain the new table, and autogenerate will
try to drop it. The explicit ``import app.models``/``app.reference``/
``app.phenopackets`` imports below mirror the production ``env.py``
imports so that drift in the test DB schema is what triggers the failure,
not drift in which modules happen to be imported by test collection.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

# Mirror the production env.py import block so Base.metadata is complete
# regardless of test-collection import order.
import app.comments.models  # noqa: F401
import app.models.user  # noqa: F401
import app.phenopackets.models  # noqa: F401
import app.reference.models  # noqa: F401
from app.core.config import settings
from app.database import Base

# Raw-SQL-managed tables (no ORM model) that live in the schema and must
# NOT be dropped by autogenerate. Keep this in sync with the equivalent
# whitelist in ``backend/alembic/env.py::include_object``.
_RAW_SQL_TABLES = {
    "alembic_version",
    "allelic_state_values",
    "evidence_code_values",
    "hpo_terms_lookup",
    "interpretation_status_values",
    "progress_status_values",
    "publication_metadata",
    "sex_values",
    "variant_annotations",
}


def test_alembic_autogenerate_does_not_drop_tables():
    """No ``remove_table`` ops allowed in ``compare_metadata`` output.

    Column/index/FK drift is tolerated for now — see module docstring.
    """
    # alembic's MigrationContext takes a sync SQLAlchemy connection, so
    # strip the asyncpg driver prefix if present.
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url)

    try:
        with engine.connect() as connection:

            def include_object(obj, name, type_, reflected, compare_to):  # noqa: ARG001
                if type_ == "table" and name in _RAW_SQL_TABLES:
                    return False
                return True

            mc = MigrationContext.configure(
                connection,
                opts={
                    "include_object": include_object,
                    "compare_type": True,
                    "compare_server_default": True,
                },
            )
            diff = compare_metadata(mc, Base.metadata)
    finally:
        engine.dispose()

    # ``compare_metadata`` yields either bare ops or per-table sublists.
    # We only care about ``remove_table`` — i.e. the DB has a table the
    # ORM metadata does not know about. Those are the destructive ones.
    dropped_tables: list[str] = []
    for op in diff:
        if isinstance(op, tuple) and op and op[0] == "remove_table":
            table = op[1]
            dropped_tables.append(getattr(table, "name", str(table)))

    assert dropped_tables == [], (
        "alembic autogenerate wants to drop tables that env.py does not "
        "know about. Either add the ORM model import to alembic/env.py or "
        "extend the include_object whitelist in env.py AND in the "
        "_RAW_SQL_TABLES set in this test. Offending tables: "
        + ", ".join(sorted(dropped_tables))
    )


def test_env_py_imports_all_orm_models():
    """Static AST check: alembic/env.py must import every ORM model class.

    ``test_alembic_autogenerate_does_not_drop_tables`` above cannot catch
    drift in env.py's import block directly because the test itself imports
    the model packages, which puts every table into ``Base.metadata``
    before ``compare_metadata`` runs. This test parses ``alembic/env.py``
    as pure source, collects the ``from app... import (...)`` names, and
    asserts every ``__tablename__``-bearing class in the ORM package tree
    appears there. That way, adding a new ORM model without also updating
    env.py fails the test loudly.
    """
    env_py = (
        Path(__file__).resolve().parents[1] / "alembic" / "env.py"
    )  # backend/alembic/env.py
    assert env_py.exists(), f"alembic env.py not found at {env_py}"

    tree = ast.parse(env_py.read_text(encoding="utf-8"))
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("app.")
        ):
            for alias in node.names:
                imported_names.add(alias.name)

    # Discover every ORM model class currently known to Base.metadata and
    # map table-name back to its Python class name. Any class in this set
    # must appear in env.py's import block.
    expected_class_names: set[str] = set()
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        # Only include declarative models that live in the ``app`` package.
        module = getattr(cls, "__module__", "")
        if module.startswith("app."):
            expected_class_names.add(cls.__name__)

    missing = sorted(expected_class_names - imported_names)
    assert not missing, (
        "alembic/env.py is missing imports for these ORM model classes: "
        + ", ".join(missing)
        + ". Add them to the import block so Base.metadata is complete "
        "when alembic runs."
    )


# Silence unused-import warning for pytest in case a strict ruff rule lands.
_ = pytest

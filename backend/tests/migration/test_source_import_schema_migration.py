"""Structural contract for the additive source-import Alembic migration."""

import importlib.util
from pathlib import Path


def test_source_import_migration_adds_only_operational_tables_and_provenance():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/c0f422b00004_source_import_tables.py"
    )
    spec = importlib.util.spec_from_file_location("source_import_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "b9f422b00003"
    assert migration.revision == "c0f422b00004"
    assert migration.OPERATIONAL_TABLES == {
        "source_datasets",
        "source_snapshots",
        "source_import_runs",
        "phenopacket_subject_bindings",
        "source_report_bindings",
        "source_correction_registry",
    }

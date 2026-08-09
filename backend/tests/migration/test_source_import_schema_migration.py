"""Structural contract for the additive source-import Alembic migration."""

import importlib.util
from pathlib import Path

import pytest


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


class _DowngradeResult:
    def __init__(self, state: dict[str, int]) -> None:
        self.state = state

    def mappings(self):
        return self

    def one(self) -> dict[str, int]:
        return self.state


class _DowngradeBind:
    def __init__(self, state: dict[str, int]) -> None:
        self.state = state
        self.statements: list[str] = []

    def execute(self, statement):
        self.statements.append(str(statement))
        return _DowngradeResult(self.state)


def _migration_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/c0f422b00004_source_import_tables.py"
    )
    spec = importlib.util.spec_from_file_location("source_import_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


@pytest.mark.parametrize(
    "state",
    [
        {"operational_rows": 1, "imported_revisions": 0, "source_bound_records": 0},
        {"operational_rows": 0, "imported_revisions": 1, "source_bound_records": 0},
        {"operational_rows": 0, "imported_revisions": 0, "source_bound_records": 1},
    ],
)
def test_downgrade_refuses_when_database_contains_source_evidence(state):
    migration = _migration_module()
    bind = _DowngradeBind(state)

    with pytest.raises(RuntimeError, match="source-import evidence"):
        migration.assert_pre_activation_source_import_downgrade(bind)

    assert "source_import_runs" in bind.statements[0]
    assert "import_run_id" in bind.statements[0]
    assert "source_bound" in bind.statements[0]

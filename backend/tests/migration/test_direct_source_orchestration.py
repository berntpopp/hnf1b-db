"""The legacy CLI must fail closed instead of importing reviewer accounts or rows."""

import inspect

import pytest

from migration.data_sources.source_adapter import SourceSnapshot
from migration.direct_sheets_to_phenopackets import DirectSheetsToPhenopackets
from migration.source_manifest import EXPECTED_HEADERS, build_source_manifest


def test_direct_orchestration_has_no_embedded_sheet_authority_or_user_import():
    source = inspect.getsource(DirectSheetsToPhenopackets)
    assert "1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw" not in source
    assert "UserImportService" not in source


def test_direct_orchestration_refuses_legacy_raw_storage_apply():
    migration = DirectSheetsToPhenopackets(
        "postgresql+asyncpg://test:test@localhost/test_db"
    )
    assert migration.legacy_apply_is_disabled is True


class _FixtureAdapter:
    def __init__(self, snapshot: SourceSnapshot) -> None:
        self.snapshot = snapshot

    async def load(self) -> SourceSnapshot:
        return self.snapshot


def _csv(headers: tuple[str, ...], values: list[str] | None = None) -> bytes:
    row = values or ["NR"] * len(headers)
    return (",".join(headers) + "\n" + ",".join(row) + "\n").encode()


@pytest.mark.asyncio
async def test_load_data_versions_laterality_from_modifier_sheet(monkeypatch):
    raw_sheets = {
        "Individuals": _csv(EXPECTED_HEADERS["Individuals"]),
        "Phenotypes": _csv(
            EXPECTED_HEADERS["Phenotypes"], ["RenalCysts", "HP:0000107", "Renal cyst", ""]
        ),
        "Phenotype_modifier": _csv(
            EXPECTED_HEADERS["Phenotype_modifier"], ["Bilateral", "HP:0012832"]
        ),
        "Publications": _csv(EXPECTED_HEADERS["Publications"]),
    }
    # Four source terms are required; add the remaining three data rows.
    raw_sheets["Phenotype_modifier"] += (
        b"Unilateral,HP:0012833\nLeft,HP:0012835\nRight,HP:0012834\n"
    )
    manifest = build_source_manifest(
        source_system="fixture", dataset_key="hnf1b-registry", sheets=raw_sheets
    )
    migration = DirectSheetsToPhenopackets(
        "postgresql+asyncpg://test:test@localhost/test_db",
        source_adapter=_FixtureAdapter(
            SourceSnapshot(manifest=manifest, raw_sheets=raw_sheets)
        ),
    )
    monkeypatch.setattr(
        "migration.direct_sheets_to_phenopackets.settings.SOURCE_IMPORT_ENABLED", True
    )

    await migration.load_data()

    assert migration.modifier_vocabulary.version_sha256 == manifest.sheets[
        "Phenotype_modifier"
    ].sha256

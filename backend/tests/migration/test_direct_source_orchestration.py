"""The legacy CLI must fail closed instead of importing reviewer accounts or rows."""

import inspect
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from migration.data_sources.source_adapter import SourceSnapshot
from migration.direct_sheets_to_phenopackets import (
    DirectSheetsToPhenopackets,
    source_import_cli_configuration,
    write_dry_run_atomically,
)
from migration.phenopackets.builder_simple import PhenopacketBuilder
from migration.phenopackets.hpo_mapper import HPOMapper
from migration.phenopackets.laterality import modifier_vocabulary_from_rows
from migration.phenopackets.publication_mapping import publication_mapping_from_rows
from migration.phenopackets.source_column_map import SOURCE_COLUMNS
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
        "Publications": _csv(
            EXPECTED_HEADERS["Publications"],
            ["study-2026", "family-study", "123456", "10.1000/family.study"],
        ),
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
    assert migration.phenopacket_builder is None
    assert migration.publication_mapping["family-study"].pmid == "123456"
    assert migration.publication_mapping["family-study"].doi == "10.1000/family.study"


@pytest.mark.asyncio
async def test_direct_import_refuses_to_use_live_google_adapter_as_input(monkeypatch):
    migration = DirectSheetsToPhenopackets(
        "postgresql+asyncpg://test:test@localhost/test_db"
    )
    monkeypatch.setattr(
        "migration.direct_sheets_to_phenopackets.settings.SOURCE_IMPORT_ENABLED", True
    )

    with pytest.raises(RuntimeError, match="pinned source snapshot"):
        await migration.load_data()


def test_production_builder_uses_injected_source_modifier_vocabulary():
    vocabulary = modifier_vocabulary_from_rows(
        [
            {"modifier": "Bilateral", "modifier_id": "HP:0012832"},
            {"modifier": "Unilateral", "modifier_id": "HP:0012833"},
            {"modifier": "Left", "modifier_id": "HP:0012835"},
            {"modifier": "Right", "modifier_id": "HP:0012834"},
        ],
        version_sha256="a" * 64,
    )
    builder = PhenopacketBuilder(
        HPOMapper(), modifier_vocabulary=vocabulary
    )

    phenopacket = builder.build_phenopacket(
        "source-subject", pd.DataFrame([{"RenalCysts": "unilateral left"}])
    )

    renal_cyst = next(
        feature
        for feature in phenopacket["phenotypicFeatures"]
        if feature["type"]["id"] == "HP:0000107"
    )
    assert [modifier["id"] for modifier in renal_cyst["modifiers"]] == [
        "HP:0012833",
        "HP:0012835",
    ]


def test_dry_run_publication_is_atomic_when_serialization_fails(tmp_path, monkeypatch):
    destination = tmp_path / "phenopackets.json"

    def fail_dump(*_args, **_kwargs):
        raise OSError("injected serialization failure")

    monkeypatch.setattr(json, "dump", fail_dump)

    with pytest.raises(OSError, match="injected serialization failure"):
        write_dry_run_atomically(destination, [{"id": "fixture"}])

    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []


def test_typed_direct_output_omits_reviewer_email_and_comment():
    raw_sheets = {
        name: _csv(headers)
        for name, headers in EXPECTED_HEADERS.items()
    }
    manifest = build_source_manifest(
        source_system="local_fixture", dataset_key="hnf1b-registry", sheets=raw_sheets
    )
    row = {entry.header: "NR" for entry in SOURCE_COLUMNS}
    row.update(
        {
            "individual_id": "fixture-subject",
            "report_id": "fixture-report",
            "ReviewBy": "reviewer@example.test",
            "ReviewDate": "2026-08-09",
            "Comment": "source-only comment",
            "Publication": "family-study",
            "RenalCysts": "unilateral left",
            "KidneyBiopsy": "no",
        }
    )
    migration = DirectSheetsToPhenopackets(
        "postgresql+asyncpg://test:test@localhost/test_db",
        reviewer_mapping={"reviewer@example.test": ("reviewer-1", "Reviewer 1")},
        row_hmac_key=b"test-only-key",
    )
    migration.individuals_df = pd.DataFrame([row])
    migration._source_manifest = manifest
    migration.modifier_vocabulary = modifier_vocabulary_from_rows(
        [
            {"modifier": "Bilateral", "modifier_id": "HP:0012832"},
            {"modifier": "Unilateral", "modifier_id": "HP:0012833"},
            {"modifier": "Left", "modifier_id": "HP:0012835"},
            {"modifier": "Right", "modifier_id": "HP:0012834"},
        ],
        version_sha256=manifest.sheets["Phenotype_modifier"].sha256,
    )
    migration.publication_mapping = publication_mapping_from_rows(
        [
            {
                "publication_id": "study-2026",
                "publication_alias": "family-study",
                "PMID": "123456",
                "DOI": "10.1000/family.study",
            }
        ]
    )

    output = migration.build_typed_phenopackets()

    serialized = str(output)
    assert "reviewer@example.test" not in serialized
    assert "source-only comment" not in serialized
    assert output[0]["phenotypicFeatures"][0]["modifiers"][0]["id"] == "HP:0012833"
    assert {item["id"] for item in output[0]["metaData"]["externalReferences"]} == {
        "PMID:123456",
        "DOI:10.1000/family.study",
    }


@pytest.mark.asyncio
async def test_migrate_uses_typed_apply_when_session_and_actor_are_injected(monkeypatch):
    migration = DirectSheetsToPhenopackets(
        "postgresql+asyncpg://test:test@localhost/test_db"
    )
    observations = {"fixture-subject": []}
    applied: list[tuple[object, object, object]] = []

    async def load_data():
        migration._source_manifest = object()

    async def apply_typed(db, *, actor, observations_by_subject):
        applied.append((db, actor, observations_by_subject))

    monkeypatch.setattr(
        "migration.direct_sheets_to_phenopackets.settings.SOURCE_IMPORT_ENABLED", True
    )
    monkeypatch.setattr(migration, "load_data", load_data)
    monkeypatch.setattr(migration, "_build_typed_observations", lambda **_: observations)
    monkeypatch.setattr(migration, "_project_typed_observations", lambda _: [])
    monkeypatch.setattr(migration.storage, "close", lambda: _async_none())
    monkeypatch.setattr(migration, "apply_typed", apply_typed)

    session, actor = object(), object()
    await migration.migrate(db=session, actor=actor)

    assert applied == [(session, actor, observations)]


async def _async_none() -> None:
    return None


def test_cli_configuration_requires_pinned_local_snapshot_and_safe_identities(tmp_path):
    settings = SimpleNamespace(
        DATABASE_URL="postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_test",
        SOURCE_IMPORT_FIXTURE_DIR=str(tmp_path),
        SOURCE_IMPORT_MANIFEST_SHA256="a" * 64,
        SOURCE_IMPORT_ROW_HMAC_KEY="fixture-hmac-key-not-a-real-secret",
        SOURCE_IMPORT_REVIEWER_MAPPING_JSON=json.dumps(
            {"reviewer@example.test": ["reviewer-1", "Reviewer 1"]}
        ),
        SOURCE_IMPORT_ACTOR_ID=7,
    )

    configured = source_import_cli_configuration(settings)

    assert configured.actor_id == 7
    assert configured.adapter.expected_manifest_sha256 == "a" * 64
    assert configured.reviewer_mapping == {
        "reviewer@example.test": ("reviewer-1", "Reviewer 1")
    }

    settings.SOURCE_IMPORT_ROW_HMAC_KEY = ""
    with pytest.raises(RuntimeError, match="HMAC"):
        source_import_cli_configuration(settings)

    settings.SOURCE_IMPORT_ROW_HMAC_KEY = "fixture-hmac-key-not-a-real-secret"
    settings.SOURCE_IMPORT_REVIEWER_MAPPING_JSON = json.dumps(
        {"reviewer@example.test": ["reviewer@example.test", "Reviewer 1"]}
    )
    with pytest.raises(RuntimeError, match="reviewer mapping"):
        source_import_cli_configuration(settings)

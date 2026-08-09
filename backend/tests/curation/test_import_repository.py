"""Source snapshot persistence keeps only closed structural metadata."""

import pytest

from app.phenopackets.curation.import_repository import ImportRepository
from migration.source_manifest import EXPECTED_HEADERS, build_source_manifest


def _csv(headers: list[str], row: list[str] | None = None) -> bytes:
    values = row or ["value"] * len(headers)
    return (",".join(headers) + "\n" + ",".join(values) + "\n").encode()


@pytest.mark.asyncio
async def test_snapshot_persistence_accepts_typed_manifest_with_row_counts(db_session):
    manifest = build_source_manifest(
        source_system="fixture",
        dataset_key="hnf1b-registry",
        header_validation=False,
        sheets={
            "Individuals": _csv(
                list(EXPECTED_HEADERS["Individuals"]), ["source-subject"] * 60
            ),
            "Phenotypes": _csv(list(EXPECTED_HEADERS["Phenotypes"])),
            "Phenotype_modifier": _csv(
                ["modifier", "modifier_id"], ["Left", "HP:0012835"]
            ),
            "Publications": _csv(list(EXPECTED_HEADERS["Publications"])),
        },
    )
    repository = ImportRepository(db_session)
    dataset = await repository.get_or_create_dataset(
        source_system="fixture",
        dataset_key="hnf1b-registry",
        subject_namespace="fixture",
    )

    snapshot = await repository.get_or_create_snapshot(
        dataset_id=dataset.id,
        manifest_sha256=manifest.sha256,
        source_manifest=manifest,
        expected_counts={"individuals": 1},
    )

    assert snapshot.source_manifest["sheets"]["Individuals"]["row_count"] == 1
    assert snapshot.source_manifest["sha256"] == manifest.sha256
    assert "source-subject" not in repr(snapshot.source_manifest)

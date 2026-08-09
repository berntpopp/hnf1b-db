"""Typed source applies are atomic against the isolated PostgreSQL test database."""

import pytest
from sqlalchemy import func, select

from app.phenopackets.curation.import_models import (
    PhenopacketSubjectBinding,
    SourceDataset,
    SourceImportRun,
    SourceReportBinding,
    SourceSnapshot,
)
from app.phenopackets.models import Phenopacket, PhenopacketRevision
from migration.phenopackets.laterality import modifier_vocabulary_from_rows
from migration.phenopackets.observation_extractor import extract_observation
from migration.phenopackets.source_column_map import SOURCE_COLUMNS
from migration.source_manifest import EXPECTED_HEADERS, build_source_manifest
from migration.typed_import_service import TypedObservationImportService


def _csv(headers: tuple[str, ...]) -> bytes:
    return (",".join(headers) + "\n" + ",".join(["NR"] * len(headers)) + "\n").encode()


def _input():
    raw = {name: _csv(headers) for name, headers in EXPECTED_HEADERS.items()}
    manifest = build_source_manifest(
        source_system="fixture", dataset_key="hnf1b-registry", sheets=raw
    )
    row = {entry.header: "NR" for entry in SOURCE_COLUMNS}
    row.update(
        {
            "individual_id": "source-subject",
            "report_id": "source-report",
            "ReviewBy": "reviewer@example.test",
            "ReviewDate": "2026-08-09",
            "RenalCysts": "unilateral left",
            "KidneyBiopsy": "no",
        }
    )
    vocabulary = modifier_vocabulary_from_rows(
        [
            {"modifier": "Bilateral", "modifier_id": "HP:0012832"},
            {"modifier": "Unilateral", "modifier_id": "HP:0012833"},
            {"modifier": "Left", "modifier_id": "HP:0012835"},
            {"modifier": "Right", "modifier_id": "HP:0012834"},
        ],
        version_sha256=manifest.sheets["Phenotype_modifier"].sha256,
    )
    observation = extract_observation(
        row,
        row_number=2,
        source_system=manifest.source_system,
        dataset_key=manifest.dataset_key,
        manifest_sha256=manifest.sha256,
        row_hmac_key=b"test-only-key",
        reviewer_mapping={"reviewer@example.test": ("reviewer-1", "Reviewer 1")},
        modifier_vocabulary=vocabulary,
    )
    return manifest, {"source-subject": [observation]}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure_stage", ["dataset", "snapshot", "run", "record", "revision", "binding"]
)
async def test_typed_apply_rolls_back_every_stage(db_session, curator_user, failure_stage):
    manifest, observations = _input()

    async def fail(stage: str) -> None:
        if stage == failure_stage:
            raise RuntimeError("injected failure")

    service = TypedObservationImportService(db_session, actor=curator_user, stage_hook=fail)
    with pytest.raises(RuntimeError, match="injected failure"):
        await service.apply(manifest=manifest, observations_by_subject=observations)

    for model in (
        SourceDataset,
        SourceSnapshot,
        SourceImportRun,
        PhenopacketSubjectBinding,
        SourceReportBinding,
        Phenopacket,
        PhenopacketRevision,
    ):
        assert await db_session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.asyncio
async def test_typed_apply_persists_complete_accounting(db_session, curator_user):
    manifest, observations = _input()
    await TypedObservationImportService(db_session, actor=curator_user).apply(
        manifest=manifest, observations_by_subject=observations
    )

    run = (await db_session.execute(select(SourceImportRun))).scalar_one()
    revision = (await db_session.execute(select(PhenopacketRevision))).scalar_one()
    assert run.status == "applied"
    assert run.observed_counts == {"records": 1, "observations": 1}
    assert revision.import_run_id == run.id
    assert await db_session.scalar(select(func.count()).select_from(PhenopacketSubjectBinding)) == 1
    assert await db_session.scalar(select(func.count()).select_from(SourceReportBinding)) == 1

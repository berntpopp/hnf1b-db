"""Typed source applies are atomic against the isolated PostgreSQL test database."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.database import async_session_maker
from app.phenopackets.curation.import_models import (
    PhenopacketSubjectBinding,
    SourceDataset,
    SourceImportRun,
    SourceReportBinding,
    SourceSnapshot,
)
from app.phenopackets.curation.models import (
    AssessmentStatus,
    CurationCorrection,
    Hnf1bCurationProfile,
    ProjectionResolution,
)
from app.phenopackets.curation.projection import project_individual
from app.phenopackets.models import Phenopacket, PhenopacketRevision
from migration.direct_sheets_to_phenopackets import run_source_import_transaction
from migration.phenopackets.laterality import modifier_vocabulary_from_rows
from migration.phenopackets.observation_extractor import extract_observation
from migration.phenopackets.source_column_map import SOURCE_COLUMNS
from migration.source_manifest import EXPECTED_HEADERS, build_source_manifest
from migration.typed_import_service import TypedObservationImportService


def _csv(headers: tuple[str, ...], *, rows: int = 1) -> bytes:
    return (
        ",".join(headers)
        + "\n"
        + "\n".join(",".join(["NR"] * len(headers)) for _ in range(rows))
        + "\n"
    ).encode()


def _input(
    *,
    changed: bool = False,
    report_ids: tuple[str, ...] = ("source-report",),
    changed_report: str | None = None,
    subject_id: str = "source-subject",
):
    raw = {
        name: _csv(headers, rows=len(report_ids) if name == "Individuals" else 1)
        for name, headers in EXPECTED_HEADERS.items()
    }
    if changed:
        raw["Individuals"] = raw["Individuals"].replace(b"\n", b"\r\n")
    manifest = build_source_manifest(
        source_system="fixture", dataset_key="hnf1b-registry", sheets=raw
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
    observations = []
    for row_number, report_id in enumerate(report_ids, start=2):
        row = {entry.header: "NR" for entry in SOURCE_COLUMNS}
        row.update(
            {
                "individual_id": subject_id,
                "report_id": report_id,
                "ReviewBy": "reviewer@example.test",
                "ReviewDate": "2026-08-09",
                "RenalCysts": "unilateral left",
                "KidneyBiopsy": "no",
                "Comment": (
                    "changed source comment"
                    if changed and (changed_report is None or changed_report == report_id)
                    else "NR"
                ),
            }
        )
        observations.append(
            extract_observation(
                row,
                row_number=row_number,
                source_system=manifest.source_system,
                dataset_key=manifest.dataset_key,
                manifest_sha256=manifest.sha256,
                row_hmac_key=b"test-only-key",
                reviewer_mapping={
                    "reviewer@example.test": ("reviewer-1", "Reviewer 1")
                },
                modifier_vocabulary=vocabulary,
            )
        )
    return manifest, {subject_id: observations}


def _with_renal_cyst_status(observation, status: AssessmentStatus):
    """Return a valid imported observation with the named assessment polarity."""
    return observation.model_copy(
        update={
            "phenotypes": tuple(
                assessment.model_copy(update={"assessment_status": status})
                if assessment.column == "RenalCysts"
                else assessment
                for assessment in observation.phenotypes
            )
        }
    )


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
    record = (await db_session.execute(select(Phenopacket))).scalar_one()
    assert run.status == "applied"
    assert run.observed_counts == {"records": 1, "observations": 1}
    assert revision.revision_number == 1
    assert revision.import_run_id == run.id
    profile = record.phenopacket["hnf1bCuration"]
    assert profile["schemaVersion"] == "2.0"
    assert set(profile["observationsById"]) == {str(observations["source-subject"][0].observation_id)}
    stored_source = next(iter(profile["observationsById"].values()))["source"]
    assert stored_source["provider"] == manifest.source_system
    assert stored_source["datasetId"] == manifest.dataset_key
    assert stored_source["manifestSha256"] == manifest.sha256
    assert stored_source["importRunId"] == str(run.id)
    assert profile["projection"]["algorithmVersion"] == "1.0"
    assert await db_session.scalar(select(func.count()).select_from(PhenopacketSubjectBinding)) == 1
    assert await db_session.scalar(select(func.count()).select_from(SourceReportBinding)) == 1


@pytest.mark.asyncio
async def test_typed_apply_is_a_noop_for_an_exact_snapshot_rerun(
    db_session, curator_user
):
    manifest, observations = _input()
    service = TypedObservationImportService(db_session, actor=curator_user)

    await service.apply(manifest=manifest, observations_by_subject=observations)
    await service.apply(manifest=manifest, observations_by_subject=observations)

    assert await db_session.scalar(select(func.count()).select_from(SourceImportRun)) == 1
    assert await db_session.scalar(select(func.count()).select_from(PhenopacketRevision)) == 1


@pytest.mark.asyncio
async def test_typed_apply_rejects_observation_with_wrong_pinned_provenance(
    db_session, curator_user
):
    manifest, observations = _input()
    observation = observations["source-subject"][0]
    invalid = observation.model_copy(
        update={
            "source": observation.source.model_copy(
                update={"provider": "untrusted-provider"}
            )
        }
    )

    with pytest.raises(Exception, match="provenance"):
        await TypedObservationImportService(db_session, actor=curator_user).apply(
            manifest=manifest, observations_by_subject={"source-subject": [invalid]}
        )

    assert await db_session.scalar(select(func.count()).select_from(SourceDataset)) == 0


@pytest.mark.asyncio
async def test_typed_apply_rejects_individual_identity_not_matching_subject_binding(
    db_session, curator_user
):
    manifest, observations = _input()
    observation = observations["source-subject"][0]
    invalid = observation.model_copy(
        update={
            "identifiers": observation.identifiers.model_copy(
                update={"individual_id": "different-individual"}
            )
        }
    )

    with pytest.raises(Exception, match="identity"):
        await TypedObservationImportService(db_session, actor=curator_user).apply(
            manifest=manifest, observations_by_subject={"source-subject": [invalid]}
        )

    assert await db_session.scalar(select(func.count()).select_from(SourceDataset)) == 0


@pytest.mark.asyncio
async def test_changed_snapshot_refuses_to_overwrite_an_active_import_draft(
    db_session, curator_user
):
    manifest, observations = _input()
    await TypedObservationImportService(db_session, actor=curator_user).apply(
        manifest=manifest, observations_by_subject=observations
    )
    changed_manifest, changed_observations = _input(changed=True)

    with pytest.raises(RuntimeError, match="active draft"):
        await TypedObservationImportService(db_session, actor=curator_user).apply(
            manifest=changed_manifest, observations_by_subject=changed_observations
        )

    assert await db_session.scalar(select(func.count()).select_from(SourceImportRun)) == 1
    assert await db_session.scalar(select(func.count()).select_from(PhenopacketRevision)) == 1


@pytest.mark.asyncio
async def test_changed_snapshot_appends_one_revision_to_a_nonediting_record(
    db_session, curator_user
):
    manifest, observations = _input()
    service = TypedObservationImportService(db_session, actor=curator_user)
    await service.apply(manifest=manifest, observations_by_subject=observations)
    record = (await db_session.execute(select(Phenopacket))).scalar_one()
    initial_revision = (await db_session.execute(select(PhenopacketRevision))).scalar_one()
    record.state = "published"
    record.head_published_revision_id = initial_revision.id
    record.editing_revision_id = None
    await db_session.flush()

    changed_manifest, changed_observations = _input(changed=True)
    result = await service.apply(
        manifest=changed_manifest, observations_by_subject=changed_observations
    )

    assert result.applied is True
    assert await db_session.scalar(select(func.count()).select_from(Phenopacket)) == 1
    assert await db_session.scalar(select(func.count()).select_from(PhenopacketRevision)) == 2


@pytest.mark.asyncio
async def test_complete_changed_snapshot_retires_missing_report_binding(
    db_session, curator_user
):
    report_ids = ("source-report-1", "source-report-2")
    manifest, observations = _input(report_ids=report_ids)
    service = TypedObservationImportService(db_session, actor=curator_user)
    await service.apply(manifest=manifest, observations_by_subject=observations)
    record = (await db_session.execute(select(Phenopacket))).scalar_one()
    revision = (await db_session.execute(select(PhenopacketRevision))).scalar_one()
    record.state = "published"
    record.head_published_revision_id = revision.id
    record.editing_revision_id = None
    await db_session.flush()

    changed_manifest, changed_observations = _input(
        changed=True, report_ids=("source-report-1",)
    )
    await service.apply(
        manifest=changed_manifest, observations_by_subject=changed_observations
    )

    bindings = (
        await db_session.execute(
            select(SourceReportBinding).order_by(SourceReportBinding.report_id)
        )
    ).scalars().all()
    assert [(binding.report_id, binding.active) for binding in bindings] == [
        ("source-report-1", True),
        ("source-report-2", False),
    ]
    profile = (await db_session.execute(select(Phenopacket))).scalar_one().phenopacket[
        "hnf1bCuration"
    ]
    assert len(profile["observationsById"]) == 1


@pytest.mark.asyncio
async def test_complete_changed_snapshot_retires_missing_subject_binding(
    db_session, curator_user
):
    manifest, observations = _input()
    service = TypedObservationImportService(db_session, actor=curator_user)
    await service.apply(manifest=manifest, observations_by_subject=observations)

    changed_manifest, changed_observations = _input(
        changed=True,
        report_ids=("new-source-report",),
        subject_id="new-source-subject",
    )
    await service.apply(
        manifest=changed_manifest, observations_by_subject=changed_observations
    )

    subject_bindings = (
        await db_session.execute(
            select(PhenopacketSubjectBinding.source_subject_id).order_by(
                PhenopacketSubjectBinding.source_subject_id
            )
        )
    ).scalars().all()
    report_bindings = (
        await db_session.execute(
            select(SourceReportBinding.report_id, SourceReportBinding.active).order_by(
                SourceReportBinding.report_id
            )
        )
    ).all()
    assert subject_bindings == ["new-source-subject"]
    assert report_bindings == [
        ("new-source-report", True),
        ("source-report", False),
    ]


@pytest.mark.asyncio
async def test_changed_snapshot_preserves_unaffected_curator_correction(
    db_session, curator_user
):
    report_ids = ("source-report-1", "source-report-2")
    manifest, observations = _input(report_ids=report_ids)
    service = TypedObservationImportService(db_session, actor=curator_user)
    await service.apply(manifest=manifest, observations_by_subject=observations)
    record = (await db_session.execute(select(Phenopacket))).scalar_one()
    initial_revision = (await db_session.execute(select(PhenopacketRevision))).scalar_one()
    observation_id = str(observations["source-subject"][0].observation_id)
    current = Hnf1bCurationProfile.model_validate(record.phenopacket["hnf1bCuration"])
    correction = CurationCorrection(
        correction_id="correction-one",
        json_pointer=f"/observationsById/{observation_id}/case/duplicateCheck/value",
        preimage=None,
        postimage="no",
        source_manifest_sha256=manifest.sha256,
        reason="Curator reviewed source semantics.",
        actor_id=curator_user.id,
        created_at=datetime.now(timezone.utc),
    )
    updated = current.model_copy(
        update={"corrections_by_id": {correction.correction_id: correction}}
    )
    record.phenopacket = {
        **record.phenopacket,
        "hnf1bCuration": updated.model_dump(by_alias=True, mode="json"),
    }
    record.state = "published"
    record.head_published_revision_id = initial_revision.id
    record.editing_revision_id = None
    await db_session.flush()

    changed_manifest, changed_observations = _input(
        changed=True,
        report_ids=report_ids,
        changed_report="source-report-2",
    )
    await service.apply(
        manifest=changed_manifest, observations_by_subject=changed_observations
    )

    profile = (await db_session.execute(select(Phenopacket))).scalar_one().phenopacket[
        "hnf1bCuration"
    ]
    assert profile["correctionsById"]["correction-one"]["postimage"] == "no"


@pytest.mark.asyncio
async def test_changed_snapshot_preserves_a_valid_curator_resolution(
    db_session, curator_user
):
    report_ids = ("source-report-1", "source-report-2")
    manifest, observations = _input(report_ids=report_ids)
    service = TypedObservationImportService(db_session, actor=curator_user)
    await service.apply(manifest=manifest, observations_by_subject=observations)
    record = (await db_session.execute(select(Phenopacket))).scalar_one()
    initial_revision = (await db_session.execute(select(PhenopacketRevision))).scalar_one()

    conflicted = [
        observations["source-subject"][0],
        _with_renal_cyst_status(
            observations["source-subject"][1], AssessmentStatus.EXCLUDED
        ),
    ]
    conflict = project_individual(conflicted, [], algorithm_version="1.0").blocking_conflicts[0]
    resolution = ProjectionResolution(
        resolution_id="resolution-one",
        conflict_key=conflict.conflict_key,
        candidate_set_digest=conflict.candidate_set_digest,
        strategy="select_observations",
        selected_observation_ids=(str(conflicted[0].observation_id),),
        reason="Curator selected the confirmed imaging report.",
        resolved_by_user_id=curator_user.id,
        resolved_at=datetime.now(timezone.utc),
    )
    current = Hnf1bCurationProfile.model_validate(record.phenopacket["hnf1bCuration"])
    record.phenopacket = {
        **record.phenopacket,
        "hnf1bCuration": current.model_copy(
            update={
                "observations_by_id": {
                    str(observation.observation_id): observation
                    for observation in conflicted
                },
                "resolutions_by_id": {resolution.resolution_id: resolution},
            }
        ).model_dump(by_alias=True, mode="json"),
    }
    record.state = "published"
    record.head_published_revision_id = initial_revision.id
    record.editing_revision_id = None
    await db_session.flush()

    changed_manifest, changed_observations = _input(
        changed=True, report_ids=report_ids, changed_report="source-report-2"
    )
    changed_observations["source-subject"][1] = _with_renal_cyst_status(
        changed_observations["source-subject"][1], AssessmentStatus.EXCLUDED
    )
    await service.apply(
        manifest=changed_manifest, observations_by_subject=changed_observations
    )

    profile = (await db_session.execute(select(Phenopacket))).scalar_one().phenopacket[
        "hnf1bCuration"
    ]
    assert profile["resolutionsById"]["resolution-one"]["conflictKey"] == (
        "phenotype:HP:0000107:polarity"
    )


@pytest.mark.asyncio
async def test_exact_snapshot_noop_leaves_curator_overlay_untouched(
    db_session, curator_user
):
    manifest, observations = _input()
    service = TypedObservationImportService(db_session, actor=curator_user)
    await service.apply(manifest=manifest, observations_by_subject=observations)
    record = (await db_session.execute(select(Phenopacket))).scalar_one()
    observation_id = str(observations["source-subject"][0].observation_id)
    current = Hnf1bCurationProfile.model_validate(record.phenopacket["hnf1bCuration"])
    correction = CurationCorrection(
        correction_id="correction-noop",
        json_pointer=f"/observationsById/{observation_id}/case/duplicateCheck/value",
        preimage=None,
        postimage="no",
        source_manifest_sha256=manifest.sha256,
        reason="Curator reviewed source semantics.",
        actor_id=curator_user.id,
        created_at=datetime.now(timezone.utc),
    )
    record.phenopacket = {
        **record.phenopacket,
        "hnf1bCuration": current.model_copy(
            update={"corrections_by_id": {correction.correction_id: correction}}
        ).model_dump(by_alias=True, mode="json"),
    }
    await db_session.flush()

    result = await service.apply(manifest=manifest, observations_by_subject=observations)

    assert result.applied is False
    profile = (await db_session.execute(select(Phenopacket))).scalar_one().phenopacket[
        "hnf1bCuration"
    ]
    assert "correction-noop" in profile["correctionsById"]
    assert await db_session.scalar(select(func.count()).select_from(PhenopacketRevision)) == 1


@pytest.mark.asyncio
async def test_outer_cli_transaction_commits_typed_apply_for_a_separate_session(
    curator_user,
):
    manifest, observations = _input()

    async def apply(session, actor):
        return await TypedObservationImportService(session, actor=actor).apply(
            manifest=manifest, observations_by_subject=observations
        )

    async with async_session_maker() as session:
        await run_source_import_transaction(
            session, actor_id=curator_user.id, apply=apply
        )
    async with async_session_maker() as verification_session:
        assert (
            await verification_session.scalar(
                select(func.count()).select_from(SourceImportRun)
            )
            == 1
        )


@pytest.mark.asyncio
async def test_outer_cli_transaction_rolls_back_typed_apply_on_exception(
    curator_user,
):
    manifest, observations = _input()

    async def apply(session, actor):
        async def fail(stage: str) -> None:
            if stage == "record":
                raise RuntimeError("injected outer transaction failure")

        return await TypedObservationImportService(
            session, actor=actor, stage_hook=fail
        ).apply(manifest=manifest, observations_by_subject=observations)

    async with async_session_maker() as session:
        with pytest.raises(RuntimeError, match="injected outer transaction failure"):
            await run_source_import_transaction(
                session, actor_id=curator_user.id, apply=apply
            )
    async with async_session_maker() as verification_session:
        assert (
            await verification_session.scalar(
                select(func.count()).select_from(SourceImportRun)
            )
            == 0
        )

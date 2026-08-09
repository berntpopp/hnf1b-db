"""Atomic source import orchestration tests with no live database dependency."""

import pytest

from migration.import_service import (
    AtomicObservationImportService,
    ImportApplyError,
    StagedImport,
    StagedRecord,
)


@pytest.mark.asyncio
async def test_import_aborts_before_apply_when_built_counts_do_not_match_expected():
    applied: list[str] = []

    async def apply(record: StagedRecord) -> None:
        applied.append(record.source_subject_id)

    service = AtomicObservationImportService(apply_record=apply)
    staged = StagedImport(
        records=(StagedRecord("317", 1),),
        built_observations=1,
        expected_observations=2,
        expected_records=1,
    )

    with pytest.raises(ImportApplyError, match="count invariant"):
        await service.apply(staged)
    assert applied == []


@pytest.mark.asyncio
async def test_import_rolls_back_all_clinical_work_when_one_record_apply_fails():
    applied: list[str] = []
    rollbacks: list[bool] = []

    async def apply(record: StagedRecord) -> None:
        applied.append(record.source_subject_id)
        if record.source_subject_id == "318":
            raise RuntimeError("injected revision failure")

    async def rollback() -> None:
        rollbacks.append(True)

    service = AtomicObservationImportService(apply_record=apply, rollback=rollback)
    staged = StagedImport(
        records=(StagedRecord("318", 1), StagedRecord("317", 1)),
        built_observations=2,
        expected_observations=2,
        expected_records=2,
    )

    with pytest.raises(ImportApplyError, match="injected revision failure"):
        await service.apply(staged)
    assert applied == ["317", "318"]
    assert rollbacks == [True]

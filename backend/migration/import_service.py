"""All-or-nothing orchestration for staged observation imports.

This small service deliberately owns no database commit. Its ``apply_record``
callback must use the existing repository/state-service operations in the
caller-owned transaction; one exception causes a single rollback and abort.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass


class ImportApplyError(RuntimeError):
    """A staged import violated a precondition or failed during atomic apply."""


@dataclass(frozen=True)
class StagedRecord:
    """One individual-level staged application unit."""

    source_subject_id: str
    observation_count: int


@dataclass(frozen=True)
class StagedImport:
    """Validated import accounting required before any clinical mutation."""

    records: tuple[StagedRecord, ...]
    built_observations: int
    expected_observations: int
    expected_records: int


ApplyRecord = Callable[[StagedRecord], Awaitable[None]]
Rollback = Callable[[], Awaitable[None]]


class AtomicObservationImportService:
    """Apply a complete staged import deterministically or leave no partial work."""

    def __init__(
        self,
        *,
        apply_record: ApplyRecord,
        rollback: Rollback | None = None,
    ) -> None:
        """Inject transaction-bound application and rollback primitives."""
        self._apply_record = apply_record
        self._rollback = rollback

    @staticmethod
    def _validate(staged: StagedImport) -> None:
        """Reject incomplete, duplicate, or mismatched staging before apply."""
        subject_ids = [record.source_subject_id for record in staged.records]
        if (
            staged.built_observations != staged.expected_observations
            or len(staged.records) != staged.expected_records
            or sum(record.observation_count for record in staged.records)
            != staged.built_observations
            or len(subject_ids) != len(set(subject_ids))
        ):
            raise ImportApplyError("staged import count invariant failed")

    async def apply(self, staged: StagedImport) -> None:
        """Apply sorted records once; on any failure roll back and re-raise."""
        self._validate(staged)
        try:
            for record in sorted(
                staged.records, key=lambda item: item.source_subject_id
            ):
                await self._apply_record(record)
        except Exception as exc:
            if self._rollback is not None:
                await self._rollback()
            raise ImportApplyError(f"atomic import apply failed: {exc}") from exc

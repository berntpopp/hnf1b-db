"""Repository primitives for source import operational identities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.curation.import_models import (
    ImportRunStatus,
    SourceCorrectionRegistry,
    SourceDataset,
    SourceImportRun,
    SourceReportBinding,
    SourceSnapshot,
    sanitize_operational_payload,
)


class SourceBindingConflict(ValueError):
    """An import attempted to move a source report or reuse a correction ID."""


class ImportRepository:
    """Async persistence boundary for non-clinical source import state."""

    def __init__(self, db: AsyncSession) -> None:
        """Bind the repository to a caller-owned async transaction."""
        self.db = db

    async def get_or_create_dataset(
        self, *, source_system: str, dataset_key: str, subject_namespace: str
    ) -> SourceDataset:
        """Return the stable dataset identity, flushing but never committing."""
        existing = (
            await self.db.execute(
                select(SourceDataset).where(
                    SourceDataset.source_system == source_system,
                    SourceDataset.dataset_key == dataset_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        dataset = SourceDataset(
            source_system=source_system,
            dataset_key=dataset_key,
            subject_namespace=subject_namespace,
        )
        self.db.add(dataset)
        await self.db.flush()
        return dataset

    async def get_or_create_snapshot(
        self,
        *,
        dataset_id: UUID,
        manifest_sha256: str,
        source_manifest: dict[str, Any],
        expected_counts: dict[str, Any] | None = None,
    ) -> SourceSnapshot:
        """Persist a sanitized structural manifest and return its immutable identity."""
        existing = (
            await self.db.execute(
                select(SourceSnapshot).where(
                    SourceSnapshot.dataset_id == dataset_id,
                    SourceSnapshot.manifest_sha256 == manifest_sha256,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        snapshot = SourceSnapshot(
            dataset_id=dataset_id,
            manifest_sha256=manifest_sha256,
            source_manifest=sanitize_operational_payload(source_manifest),
            expected_counts=sanitize_operational_payload(expected_counts or {}),
        )
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def create_run(
        self,
        *,
        snapshot_id: UUID,
        transformer_version: str,
        projection_version: str,
        actor_id: int | None,
    ) -> SourceImportRun:
        """Create a retryable staged run in the caller-owned transaction."""
        run = SourceImportRun(
            snapshot_id=snapshot_id,
            transformer_version=transformer_version,
            projection_version=projection_version,
            status=ImportRunStatus.STAGED.value,
            actor_id=actor_id,
        )
        self.db.add(run)
        await self.db.flush()
        return run

    async def finish_run(
        self,
        run: SourceImportRun,
        *,
        status: ImportRunStatus,
        observed_counts: dict[str, Any] | None = None,
        summary: dict[str, Any] | None = None,
        error_report: dict[str, Any] | None = None,
    ) -> None:
        """Record only sanitized terminal run metadata."""
        run.status = status.value
        run.observed_counts = sanitize_operational_payload(observed_counts or {})
        run.summary_jsonb = sanitize_operational_payload(summary or {})
        run.error_report = (
            sanitize_operational_payload(error_report or {})
            if error_report is not None
            else None
        )
        run.completed_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def bind_report(
        self,
        *,
        dataset_id: UUID,
        report_id: str,
        record_id: UUID,
        observation_id: UUID,
        run_id: UUID,
    ) -> SourceReportBinding:
        """Create or refresh a report binding without allowing reassignment."""
        binding = (
            await self.db.execute(
                select(SourceReportBinding)
                .where(
                    SourceReportBinding.dataset_id == dataset_id,
                    SourceReportBinding.report_id == report_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if binding is not None:
            if (
                binding.record_id != record_id
                or binding.observation_id != observation_id
            ):
                raise SourceBindingConflict(
                    "source report cannot move to a different record"
                )
            binding.last_seen_run_id = run_id
            binding.active = True
            await self.db.flush()
            return binding
        binding = SourceReportBinding(
            dataset_id=dataset_id,
            report_id=report_id,
            record_id=record_id,
            observation_id=observation_id,
            first_seen_run_id=run_id,
            last_seen_run_id=run_id,
            active=True,
        )
        self.db.add(binding)
        await self.db.flush()
        return binding

    async def register_correction(
        self,
        *,
        correction_id: UUID,
        record_id: UUID,
        observation_id: UUID,
        canonical_sha256: str,
        created_revision_id: int,
    ) -> SourceCorrectionRegistry:
        """Register a correction once, refusing same-ID different-content reuse."""
        existing = (
            await self.db.execute(
                select(SourceCorrectionRegistry)
                .where(SourceCorrectionRegistry.correction_id == correction_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.canonical_sha256 != canonical_sha256:
                raise SourceBindingConflict(
                    "correction ID has different canonical content"
                )
            return existing
        registry = SourceCorrectionRegistry(
            correction_id=correction_id,
            record_id=record_id,
            observation_id=observation_id,
            canonical_sha256=canonical_sha256,
            created_revision_id=created_revision_id,
        )
        self.db.add(registry)
        await self.db.flush()
        return registry

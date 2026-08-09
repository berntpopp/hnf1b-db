"""Transactional persistence for fully validated typed source observations."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.phenopackets.curation.adapters import canonicalize_curation_document
from app.phenopackets.curation.import_models import ImportRunStatus, SourceImportRun
from app.phenopackets.curation.import_repository import ImportRepository
from app.phenopackets.curation.models import (
    Hnf1bCurationProfile,
    ReportObservation,
)
from app.phenopackets.curation.projection import project_individual
from app.phenopackets.models import Phenopacket
from app.phenopackets.services.state_service import PhenopacketStateService
from migration.reimport_merge import ReimportConflict, classify_reimport
from migration.source_manifest import SourceManifest

TRANSFORMER_VERSION = "hnf1b-source-import/2.0"
PROJECTION_VERSION = "1.0"


class TypedImportApplyError(RuntimeError):
    """A typed import cannot be applied atomically."""


@dataclass(frozen=True)
class TypedImportApplyResult:
    """Sanitized result of an apply or exact-snapshot no-op."""

    applied: bool
    records: int
    observations: int


class TypedObservationImportService:
    """Persist a complete typed snapshot in one caller-owned transaction."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        actor: User,
        stage_hook: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        """Bind a session and accountable actor to one import transaction."""
        self.db = db
        self.actor = actor
        self._stage_hook = stage_hook

    async def _checkpoint(self, stage: str) -> None:
        """Expose flushed persistence boundaries for deterministic failure tests."""
        if self._stage_hook is not None:
            await self._stage_hook(stage)

    @staticmethod
    def _flatten(
        observations_by_subject: Mapping[str, list[ReportObservation]],
    ) -> list[ReportObservation]:
        return [
            observation
            for subject in sorted(observations_by_subject)
            for observation in observations_by_subject[subject]
        ]

    @classmethod
    def _validate_input(
        cls,
        manifest: SourceManifest,
        observations_by_subject: Mapping[str, list[ReportObservation]],
    ) -> list[ReportObservation]:
        """Validate a complete pinned source ledger before any database write."""
        observations = cls._flatten(observations_by_subject)
        if not observations or any(
            not items for items in observations_by_subject.values()
        ):
            raise TypedImportApplyError("typed import requires complete observations")
        if manifest.sheets["Individuals"].row_count != len(observations):
            raise TypedImportApplyError("manifest observation count invariant failed")
        for subject_id, subject_observations in observations_by_subject.items():
            for observation in subject_observations:
                if observation.identifiers.source_subject_id != subject_id:
                    raise TypedImportApplyError(
                        "observation map key violates provenance"
                    )
                if observation.identifiers.individual_id != subject_id:
                    raise TypedImportApplyError(
                        "observation individual identity violates subject binding"
                    )
                if (
                    observation.source.provider != manifest.source_system
                    or observation.source.dataset_id != manifest.dataset_key
                    or observation.source.manifest_sha256 != manifest.sha256
                ):
                    raise TypedImportApplyError(
                        "observation provenance does not match manifest"
                    )
        return observations

    @staticmethod
    def _with_import_run(
        observations: list[ReportObservation], run_id: str
    ) -> list[ReportObservation]:
        """Attach the generated operational run identity to immutable evidence."""
        return [
            observation.model_copy(
                update={
                    "source": observation.source.model_copy(
                        update={"import_run_id": run_id}
                    )
                }
            )
            for observation in observations
        ]

    @staticmethod
    def _document_for_subject(
        subject_id: str,
        observations: list[ReportObservation],
        *,
        corrections_by_id: Mapping[str, Any] | None = None,
        resolutions_by_id: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Store the v2 profile ledger and its deterministic GA4GH projection."""
        profile = Hnf1bCurationProfile(
            source_subject_id=subject_id,
            observations_by_id={
                str(observation.observation_id): observation
                for observation in observations
            },
            corrections_by_id=dict(corrections_by_id or {}),
            resolutions_by_id=dict(resolutions_by_id or {}),
        )
        projection = project_individual(
            observations,
            list(profile.resolutions_by_id.values()),
            algorithm_version=PROJECTION_VERSION,
        )
        if projection.blocking_conflicts:
            raise TypedImportApplyError("source projection has unresolved conflicts")
        document: dict[str, Any] = dict(projection.phenopacket)
        document["hnf1bCuration"] = profile.model_dump(by_alias=True, mode="json")
        return canonicalize_curation_document(document)

    @staticmethod
    def _has_correction_for_observation(
        profile: Hnf1bCurationProfile, observation_id: str
    ) -> bool:
        """Return whether one changed report has a curator-owned correction."""
        prefix = f"/observationsById/{observation_id}/"
        return any(
            correction.json_pointer.startswith(prefix)
            for correction in profile.corrections_by_id.values()
        )

    async def _already_applied(self, snapshot_id: Any) -> bool:
        """Return whether this exact transform/projection snapshot is complete."""
        return (
            await self.db.execute(
                select(SourceImportRun.id).where(
                    SourceImportRun.snapshot_id == snapshot_id,
                    SourceImportRun.transformer_version == TRANSFORMER_VERSION,
                    SourceImportRun.projection_version == PROJECTION_VERSION,
                    SourceImportRun.status == ImportRunStatus.APPLIED.value,
                )
            )
        ).scalar_one_or_none() is not None

    async def apply(
        self,
        *,
        manifest: SourceManifest,
        observations_by_subject: Mapping[str, list[ReportObservation]],
    ) -> TypedImportApplyResult:
        """Create operational provenance and clinical revisions atomically."""
        observations = self._validate_input(manifest, observations_by_subject)
        transaction = (
            self.db.begin_nested() if self.db.in_transaction() else self.db.begin()
        )
        async with transaction:
            repository = ImportRepository(self.db)
            dataset = await repository.get_or_create_dataset(
                source_system=manifest.source_system,
                dataset_key=manifest.dataset_key,
                subject_namespace=manifest.dataset_key,
            )
            await self._checkpoint("dataset")
            snapshot = await repository.get_or_create_snapshot(
                dataset_id=dataset.id,
                manifest_sha256=manifest.sha256,
                source_manifest=manifest,
                expected_counts={
                    "records": len(observations_by_subject),
                    "observations": len(observations),
                },
            )
            await self._checkpoint("snapshot")
            if await self._already_applied(snapshot.id):
                return TypedImportApplyResult(
                    applied=False,
                    records=len(observations_by_subject),
                    observations=len(observations),
                )
            run = await repository.create_run(
                snapshot_id=snapshot.id,
                transformer_version=TRANSFORMER_VERSION,
                projection_version=PROJECTION_VERSION,
                actor_id=self.actor.id,
            )
            run.status = ImportRunStatus.APPLYING.value
            await self.db.flush()
            await self._checkpoint("run")
            state = PhenopacketStateService(self.db)
            for subject_id, source_observations in sorted(
                observations_by_subject.items()
            ):
                subject_observations = self._with_import_run(
                    source_observations, str(run.id)
                )
                binding = await repository.get_subject_binding(
                    dataset_id=dataset.id, source_subject_id=subject_id
                )
                if binding is None:
                    document = self._document_for_subject(
                        subject_id, subject_observations
                    )
                    record = Phenopacket(
                        phenopacket_id=document["id"],
                        phenopacket=document,
                        revision=0,
                        subject_id=subject_id,
                        subject_sex=document["subject"].get("sex", "UNKNOWN_SEX"),
                        provenance_status="source_bound",
                        created_by_id=self.actor.id,
                        draft_owner_id=self.actor.id,
                    )
                    self.db.add(record)
                    await self.db.flush()
                    await self._checkpoint("record")
                    revision = await state._append_revision(
                        record,
                        state="draft",
                        content=document,
                        change_patch=None,
                        change_reason="typed source import",
                        actor=self.actor,
                        from_state=None,
                        to_state="draft",
                        event_type="source_imported",
                        import_run_id=run.id,
                    )
                    record.editing_revision_id = revision.id
                    await repository.bind_subject(
                        dataset_id=dataset.id,
                        source_subject_id=subject_id,
                        record_id=record.id,
                    )
                else:
                    existing_record = await self.db.get(Phenopacket, binding.record_id)
                    if existing_record is None:
                        raise TypedImportApplyError(
                            "source binding points to no record"
                        )
                    record = existing_record
                    if record.editing_revision_id is not None:
                        raise ReimportConflict(
                            "changed source overlaps an active draft"
                        )
                    current = Hnf1bCurationProfile.model_validate(
                        record.phenopacket["hnf1bCuration"]
                    )
                    for observation in subject_observations:
                        prior = current.observations_by_id.get(
                            str(observation.observation_id)
                        )
                        if prior is not None:
                            classify_reimport(
                                prior_row_hmac=prior.source.row_hmac_sha256 or "",
                                incoming_row_hmac=observation.source.row_hmac_sha256
                                or "",
                                has_active_draft=False,
                                has_correction=self._has_correction_for_observation(
                                    current, str(observation.observation_id)
                                ),
                                # A persisted resolution is passed back into
                                # deterministic projection below. It remains
                                # only if its candidate digest is still valid.
                                has_resolution_dependency=False,
                            )
                    document = self._document_for_subject(
                        subject_id,
                        subject_observations,
                        corrections_by_id=current.corrections_by_id,
                        resolutions_by_id=current.resolutions_by_id,
                    )
                    await self._checkpoint("record")
                    record = await state.edit_record(
                        record.id,
                        new_content=document,
                        change_reason="typed source reimport",
                        expected_revision=record.revision,
                        actor=self.actor,
                        import_run_id=run.id,
                    )
                await self.db.flush()
                await self._checkpoint("revision")
                for observation in subject_observations:
                    await repository.bind_report(
                        dataset_id=dataset.id,
                        report_id=observation.identifiers.report_id,
                        record_id=record.id,
                        observation_id=observation.observation_id,
                        run_id=run.id,
                    )
            await repository.retire_missing_bindings(
                dataset_id=dataset.id,
                source_subject_ids=set(observations_by_subject),
                report_ids={
                    observation.identifiers.report_id for observation in observations
                },
            )
            await self._checkpoint("binding")
            await repository.finish_run(
                run,
                status=ImportRunStatus.APPLIED,
                observed_counts={
                    "records": len(observations_by_subject),
                    "observations": len(observations),
                },
                summary={"manifest": manifest.sha256},
            )
        return TypedImportApplyResult(
            applied=True,
            records=len(observations_by_subject),
            observations=len(observations),
        )

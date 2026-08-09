"""Transactional persistence for fully validated typed source observations."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.phenopackets.curation.import_models import ImportRunStatus
from app.phenopackets.curation.import_repository import ImportRepository
from app.phenopackets.curation.models import ReportObservation
from app.phenopackets.curation.projection import project_individual
from app.phenopackets.models import Phenopacket
from app.phenopackets.services.state_service import PhenopacketStateService
from migration.source_manifest import SourceManifest


class TypedImportApplyError(RuntimeError):
    """A typed import cannot be applied atomically."""


class TypedObservationImportService:
    """Persist a complete typed snapshot in one caller-owned transaction."""

    def __init__(self, db: AsyncSession, *, actor: User) -> None:
        """Bind a session and accountable actor to one import transaction."""
        self.db = db
        self.actor = actor

    async def apply(
        self,
        *,
        manifest: SourceManifest,
        observations_by_subject: Mapping[str, list[ReportObservation]],
    ) -> None:
        """Create operational provenance and clinical revisions atomically."""
        observations = [
            observation
            for subject in sorted(observations_by_subject)
            for observation in observations_by_subject[subject]
        ]
        if not observations or any(not items for items in observations_by_subject.values()):
            raise TypedImportApplyError("typed import requires complete observations")

        async with self.db.begin():
            repository = ImportRepository(self.db)
            dataset = await repository.get_or_create_dataset(
                source_system=manifest.source_system,
                dataset_key=manifest.dataset_key,
                subject_namespace=manifest.dataset_key,
            )
            snapshot = await repository.get_or_create_snapshot(
                dataset_id=dataset.id,
                manifest_sha256=manifest.sha256,
                source_manifest=manifest,
                expected_counts={
                    "records": len(observations_by_subject),
                    "observations": len(observations),
                },
            )
            run = await repository.create_run(
                snapshot_id=snapshot.id,
                transformer_version="source-import-v1",
                projection_version="source-import-v1",
                actor_id=self.actor.id,
            )
            run.status = ImportRunStatus.APPLYING.value
            await self.db.flush()
            state = PhenopacketStateService(self.db)
            for subject_id, subject_observations in sorted(observations_by_subject.items()):
                projection = project_individual(
                    subject_observations, [], algorithm_version="source-import-v1"
                )
                if projection.blocking_conflicts:
                    raise TypedImportApplyError("source projection has unresolved conflicts")
                packet = projection.phenopacket
                record = Phenopacket(
                    phenopacket_id=packet["id"],
                    phenopacket=packet,
                    subject_id=subject_id,
                    subject_sex=packet["subject"].get("sex", "UNKNOWN_SEX"),
                    provenance_status="source_bound",
                    created_by_id=self.actor.id,
                    draft_owner_id=self.actor.id,
                )
                self.db.add(record)
                await self.db.flush()
                revision = await state._append_revision(
                    record,
                    state="draft",
                    content=packet,
                    change_patch=None,
                    change_reason="typed source import",
                    actor=self.actor,
                    from_state=None,
                    to_state="draft",
                    event_type="source_imported",
                    import_run_id=run.id,
                )
                record.editing_revision_id = revision.id
                for observation in subject_observations:
                    await repository.bind_report(
                        dataset_id=dataset.id,
                        report_id=observation.identifiers.report_id,
                        record_id=record.id,
                        observation_id=observation.observation_id,
                        run_id=run.id,
                    )
            await repository.finish_run(
                run,
                status=ImportRunStatus.APPLIED,
                observed_counts={
                    "records": len(observations_by_subject),
                    "observations": len(observations),
                },
                summary={"manifest": manifest.sha256},
            )

"""Transactional source-observation curation operations.

The service is deliberately the only place the HTTP layer may assemble a new
ledger document.  It keeps raw source evidence append-only, canonicalizes on
every write, and delegates revision handling to ``PhenopacketStateService``.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.phenopackets.curation.adapters import (
    CurationProjectionError,
    _active_projection_inputs,
    _apply_active_corrections,
    canonicalize_curation_document,
)
from app.phenopackets.curation.api_models import (
    CorrectionAppendRequest,
    CurationIssue,
    ProjectionPreviewRequest,
    ReportPatchRequest,
    ResolutionAppendRequest,
)
from app.phenopackets.curation.models import Hnf1bCurationProfile
from app.phenopackets.curation.projection import project_individual
from app.phenopackets.models import Phenopacket
from app.phenopackets.services.state_service import PhenopacketStateService
from app.phenopackets.validation.domain import DomainValidator


class CurationServiceError(Exception):
    """Base exception carrying an API-safe machine code and issues."""

    def __init__(self, code: str, message: str, *issues: CurationIssue) -> None:
        """Create an error with a stable code and structured issue list."""
        super().__init__(message)
        self.code = code
        self.issues = issues or (CurationIssue(code=code, message=message),)


class CurationService:
    """Read, preview, and append source-observation curation changes."""

    def __init__(self, db: AsyncSession) -> None:
        """Bind service operations to a caller-owned async unit of work."""
        self.db = db
        self._state = PhenopacketStateService(db)

    @staticmethod
    def _source_immutability_issues(
        existing: Any, proposed: Any, path: tuple[str, ...] = ()
    ) -> tuple[CurationIssue, ...]:
        """Return changed source-evidence paths that report PATCH may not mutate."""
        protected = {
            "assessmentId",
            "correctionIds",
            "identifiers",
            "observationId",
            "origin",
            "raw",
            "rawValue",
            "source",
            "sourceReview",
            "sourceStatus",
        }
        if isinstance(existing, dict) and isinstance(proposed, dict):
            issues: list[CurationIssue] = []
            for key in sorted(set(existing) | set(proposed)):
                next_path = (*path, key)
                if key in protected and existing.get(key) != proposed.get(key):
                    issues.append(
                        CurationIssue(
                            code="immutable_source",
                            message=(
                                "source-originated evidence is immutable; append a "
                                "correction instead"
                            ),
                            path=next_path,
                        )
                    )
                elif key not in protected:
                    issues.extend(
                        CurationService._source_immutability_issues(
                            existing.get(key), proposed.get(key), next_path
                        )
                    )
            return tuple(issues)
        if isinstance(existing, list) and isinstance(proposed, list):
            issues = []
            for index, (old, new) in enumerate(zip(existing, proposed)):
                issues.extend(
                    CurationService._source_immutability_issues(
                        old, new, (*path, str(index))
                    )
                )
            if len(existing) != len(proposed):
                issues.append(
                    CurationIssue(
                        code="immutable_source",
                        message="source assessment membership is immutable",
                        path=path,
                    )
                )
            return tuple(issues)
        return ()

    @staticmethod
    def _validation_payload(block: dict[str, Any]) -> dict[str, Any]:
        """Prepare stored JSON for the profile model's source-status derivation.

        ``PhenotypeAssessment`` derives ``sourceStatus`` from immutable raw
        evidence. Its pre-validator therefore accepts an omitted value and
        materializes the canonical one. Remove the serialised value before
        revalidation so a stored, canonical API document does not provide both
        its alias and its derived field.
        """
        payload = deepcopy(block)
        observations = payload.get("observationsById")
        if not isinstance(observations, dict):
            return payload
        for observation in observations.values():
            if not isinstance(observation, dict):
                continue
            phenotypes = observation.get("phenotypes")
            if not isinstance(phenotypes, list):
                continue
            for assessment in phenotypes:
                if isinstance(assessment, dict):
                    assessment.pop("sourceStatus", None)
                    assessment.pop("source_status", None)
        return payload

    @classmethod
    def _validated_profile(cls, block: dict[str, Any]) -> Hnf1bCurationProfile:
        """Validate a stored ledger while honoring derived phenotype status."""
        return Hnf1bCurationProfile.model_validate(cls._validation_payload(block))

    @classmethod
    def _candidate_profile(cls, block: dict[str, Any]) -> Hnf1bCurationProfile:
        """Convert a proposed ledger validation failure into a structured error."""
        try:
            return cls._validated_profile(block)
        except ValidationError as exc:
            issues = tuple(
                CurationIssue(
                    code="invalid_profile",
                    message=item["msg"],
                    path=tuple(str(part) for part in item["loc"]) or ("hnf1bCuration",),
                )
                for item in exc.errors()
            )
            raise CurationServiceError(
                "invalid_profile", "invalid curation profile", *issues
            ) from exc

    @staticmethod
    def _profile(document: dict[str, Any]) -> Hnf1bCurationProfile:
        block = document.get("hnf1bCuration")
        if not isinstance(block, dict) or "observationsById" not in block:
            raise CurationServiceError(
                "curation_not_available",
                "phenopacket does not use the source-observation curation contract",
            )
        try:
            return CurationService._validated_profile(block)
        except ValidationError as exc:
            issues = tuple(
                CurationIssue(
                    code="invalid_profile",
                    message=item["msg"],
                    path=tuple(str(part) for part in item["loc"]) or ("hnf1bCuration",),
                )
                for item in exc.errors()
            )
            raise CurationServiceError(
                "invalid_profile", "invalid curation profile", *issues
            ) from exc

    @staticmethod
    def _projection(profile: Hnf1bCurationProfile) -> Any:
        try:
            observations, active_resolutions = _active_projection_inputs(profile)
            return project_individual(
                observations,
                active_resolutions,
                algorithm_version=profile.projection.algorithm_version,
            )
        except (CurationProjectionError, TypeError, ValueError) as exc:
            raise CurationServiceError(
                "projection_error",
                str(exc),
                CurationIssue(
                    code="projection_error",
                    message=str(exc),
                    path=("projection",),
                ),
            ) from exc

    @classmethod
    def _issues(cls, profile: Hnf1bCurationProfile) -> tuple[CurationIssue, ...]:
        result = cls._projection(profile)
        return tuple(
            CurationIssue(
                code="projection_conflict",
                message=f"Projection conflict: {conflict.conflict_key}",
                path=("projection", "blockingConflicts"),
                observation_id=(
                    conflict.observation_ids[0] if conflict.observation_ids else None
                ),
                conflict_key=conflict.conflict_key,
                candidate_set_digest=conflict.candidate_set_digest,
                severity="blocking",
            )
            for conflict in result.blocking_conflicts
        )

    @staticmethod
    def _document_with_profile(
        document: dict[str, Any], profile: Hnf1bCurationProfile
    ) -> dict[str, Any]:
        result = deepcopy(document)
        stored_profile = profile.model_dump(by_alias=True, mode="json")
        result["hnf1bCuration"] = stored_profile
        try:
            canonical_input = deepcopy(result)
            canonical_input["hnf1bCuration"] = CurationService._validation_payload(
                stored_profile
            )
            # ``canonicalize_curation_document`` writes the derived status
            # implicitly from raw source evidence. This keeps the state service
            # able to validate the resulting document a second time on save.
            return canonicalize_curation_document(canonical_input)
        except CurationProjectionError as exc:
            raise CurationServiceError(
                exc.code,
                str(exc),
                *(
                    CurationIssue(
                        code=exc.code,
                        message=str(exc),
                        path=("hnf1bCuration",),
                    ),
                ),
            ) from exc

    @staticmethod
    def _pointer_value(document: dict[str, Any], pointer: str) -> Any:
        if not pointer.startswith("/"):
            raise CurationServiceError(
                "invalid_correction", "jsonPointer must start with '/'"
            )
        value: Any = document
        try:
            for part in pointer[1:].split("/"):
                key = part.replace("~1", "/").replace("~0", "~")
                value = value[int(key)] if isinstance(value, list) else value[key]
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise CurationServiceError(
                "invalid_correction", "jsonPointer does not identify a source value"
            ) from exc
        return value

    async def _validate_domain(self, document: dict[str, Any]) -> None:
        """Raise path-addressable errors for database-backed domain violations."""
        domain_document = deepcopy(document)
        block = domain_document.get("hnf1bCuration")
        if isinstance(block, dict):
            try:
                domain_document["hnf1bCuration"] = _apply_active_corrections(block)
            except CurationProjectionError as exc:
                raise CurationServiceError(
                    exc.code,
                    str(exc),
                    CurationIssue(
                        code=exc.code,
                        message=str(exc),
                        path=("hnf1bCuration",),
                    ),
                ) from exc
        errors = await DomainValidator(self.db).validate(domain_document)
        if errors:
            raise CurationServiceError(
                "invalid_domain",
                "curation document violates controlled vocabulary constraints",
                *(
                    CurationIssue(
                        code="invalid_domain",
                        message=message,
                        path=tuple(message.split(":", 1)[0].split(".")),
                    )
                    for message in errors
                ),
            )

    @staticmethod
    def _correction_observation_id(pointer: str) -> str:
        parts = pointer.split("/")
        if (
            len(parts) < 5
            or parts[1] != "observationsById"
            or parts[-1] != "value"
            or any(
                forbidden in pointer
                for forbidden in (
                    "/raw",
                    "/source/",
                    "/correctionsById",
                    "/resolutionsById",
                    "/projection",
                    "/audit",
                )
            )
        ):
            raise CurationServiceError(
                "invalid_correction",
                "corrections may target only a normalized observation value",
            )
        return parts[2].replace("~1", "/").replace("~0", "~")

    def read(self, record: Phenopacket) -> dict[str, Any]:
        """Build a complete curator DTO without exposing persistence internals."""
        profile = self._profile(record.phenopacket)
        result = self._projection(profile)
        return {
            "phenopacketId": record.phenopacket_id,
            "revision": record.revision,
            "observations": [
                item.model_dump(by_alias=True, mode="json")
                for item in sorted(
                    profile.observations_by_id.values(),
                    key=lambda item: item.observation_id,
                )
            ],
            "corrections": [
                item.model_dump(by_alias=True, mode="json")
                for item in profile.corrections_by_id.values()
            ],
            "resolutions": [
                item.model_dump(by_alias=True, mode="json")
                for item in profile.resolutions_by_id.values()
            ],
            "projection": {
                "phenopacket": result.phenopacket,
                "observationsDigest": result.observations_digest,
                "outputDigest": result.output_digest,
                "issues": [
                    issue.model_dump(by_alias=True, mode="json")
                    for issue in self._issues(profile)
                ],
            },
        }

    def preview(
        self, record: Phenopacket, request: ProjectionPreviewRequest
    ) -> dict[str, Any]:
        """Return the projection for an unsaved one-observation replacement."""
        profile = self._profile(record.phenopacket)
        if request.observation.observation_id not in profile.observations_by_id:
            raise CurationServiceError(
                "observation_not_found", "observation is not part of this phenopacket"
            )
        profiles = profile.model_dump(by_alias=True, mode="json")
        profiles["observationsById"][request.observation.observation_id] = (
            request.observation.model_dump(by_alias=True, mode="json")
        )
        candidate = self._candidate_profile(profiles)
        result = self._projection(candidate)
        return {
            "revision": record.revision,
            "projection": {
                "phenopacket": result.phenopacket,
                "observationsDigest": result.observations_digest,
                "outputDigest": result.output_digest,
                "issues": [
                    issue.model_dump(by_alias=True, mode="json")
                    for issue in self._issues(candidate)
                ],
            },
        }

    async def replace_report(
        self,
        record: Phenopacket,
        request: ReportPatchRequest,
        actor: User,
        expected_revision: int,
    ) -> Phenopacket:
        """Replace one existing report and append an immutable revision."""
        profile = self._profile(record.phenopacket)
        observation_id = request.observation.observation_id
        existing = profile.observations_by_id.get(observation_id)
        if existing is None:
            raise CurationServiceError(
                "observation_not_found", "observation is not part of this phenopacket"
            )
        immutable_issues = self._source_immutability_issues(
            existing.model_dump(by_alias=True, mode="json"),
            request.observation.model_dump(by_alias=True, mode="json"),
        )
        if immutable_issues:
            raise CurationServiceError(
                "immutable_source",
                "source evidence must be changed through append-only correction APIs",
                *immutable_issues,
            )
        candidate = profile.model_dump(by_alias=True, mode="json")
        candidate["observationsById"][observation_id] = request.observation.model_dump(
            by_alias=True, mode="json"
        )
        document = self._document_with_profile(
            record.phenopacket, self._candidate_profile(candidate)
        )
        await self._validate_domain(document)
        return await self._state.edit_record(
            record.id,
            new_content=document,
            change_reason=request.change_reason,
            expected_revision=expected_revision,
            actor=actor,
        )

    async def append_correction(
        self,
        record: Phenopacket,
        request: CorrectionAppendRequest,
        actor: User,
        expected_revision: int,
    ) -> Phenopacket:
        """Append an immutable correction with server-controlled actor and time."""
        profile = self._profile(record.phenopacket)
        observation_id = self._correction_observation_id(request.json_pointer)
        observation = profile.observations_by_id.get(observation_id)
        if observation is None:
            raise CurationServiceError(
                "observation_not_found", "correction references an unknown observation"
            )
        applied = _apply_active_corrections(
            profile.model_dump(by_alias=True, mode="json")
        )
        if self._pointer_value(applied, request.json_pointer) != request.preimage:
            raise CurationServiceError(
                "correction_preimage_mismatch",
                "correction preimage does not match the active source value",
            )
        correction_id = str(uuid4())
        candidate = profile.model_dump(by_alias=True, mode="json")
        candidate["correctionsById"][correction_id] = {
            "correctionId": correction_id,
            "jsonPointer": request.json_pointer,
            "preimage": request.preimage,
            "postimage": request.postimage,
            "sourceManifestSha256": observation.source.manifest_sha256,
            "reason": request.reason,
            "actorId": actor.id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "supersedesCorrectionId": request.supersedes_correction_id,
        }
        document = self._document_with_profile(
            record.phenopacket, self._candidate_profile(candidate)
        )
        await self._validate_domain(document)
        return await self._state.edit_record(
            record.id,
            new_content=document,
            change_reason=request.reason,
            expected_revision=expected_revision,
            actor=actor,
        )

    async def append_resolution(
        self,
        record: Phenopacket,
        request: ResolutionAppendRequest,
        actor: User,
        expected_revision: int,
    ) -> Phenopacket:
        """Append a resolution only for the currently computed conflict set."""
        profile = self._profile(record.phenopacket)
        conflict = next(
            (
                item
                for item in self._projection(profile).blocking_conflicts
                if item.conflict_key == request.conflict_key
            ),
            None,
        )
        if (
            conflict is None
            or conflict.candidate_set_digest != request.candidate_set_digest
        ):
            raise CurationServiceError(
                "stale_conflict",
                "resolution candidate set no longer matches the computed projection",
                CurationIssue(
                    code="stale_conflict",
                    message="refresh the projection before resolving this conflict",
                    conflict_key=request.conflict_key,
                ),
            )
        resolution_id = str(uuid4())
        resolution = request.as_resolution_payload(
            resolution_id=resolution_id,
            actor_id=actor.id,
            resolved_at=datetime.now(timezone.utc),
        )
        candidate = profile.model_dump(by_alias=True, mode="json")
        candidate["resolutionsById"][resolution_id] = resolution.model_dump(
            by_alias=True, mode="json"
        )
        document = self._document_with_profile(
            record.phenopacket, self._candidate_profile(candidate)
        )
        await self._validate_domain(document)
        return await self._state.edit_record(
            record.id,
            new_content=document,
            change_reason=request.reason,
            expected_revision=expected_revision,
            actor=actor,
        )

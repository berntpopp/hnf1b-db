"""PhenopacketStateService — the four §6 transaction sequences.

Every public method acquires ``SELECT ... FOR UPDATE`` on the phenopacket row,
checks the optimistic lock, and stages one append-only revision. Callers own
the surrounding transaction and are solely responsible for committing.

Spec reference:
  .planning/specs/2026-04-12-wave-7-d1-state-machine-design.md §6.
"""

from __future__ import annotations

import hashlib
import json
import logging
from copy import deepcopy
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.phenopackets.models import Phenopacket, PhenopacketRevision
from app.phenopackets.services.transitions import (
    Role,
    State,
    TransitionError,
    check_transition,
)
from app.utils.audit import compute_json_patch

logger = logging.getLogger(__name__)


class PhenopacketStateService:
    """All state transitions and clone-to-draft logic for phenopackets."""

    # ------------------------------------------------------------------
    # Custom exceptions (raised instead of HTTP codes — callers translate)
    # ------------------------------------------------------------------

    class InvalidTransition(Exception):
        """Guard-matrix violation, or no approved row found at publish."""

    class RevisionMismatch(Exception):
        """Optimistic-lock failure: expected_revision != current revision."""

    class EditInProgress(Exception):
        """Record already has a clone-to-draft edit open (editing_revision_id set)."""

    class ForbiddenNotOwner(Exception):
        """Curator is not the draft owner and not admin."""

    class RecordNotFound(Exception):
        """Record does not exist anymore by the time the mutation acquires its lock."""

    # ------------------------------------------------------------------

    def __init__(self, db: AsyncSession) -> None:
        """Initialise with an async database session."""
        self.db = db

    @staticmethod
    def _canonicalize_for_persistence(
        content: dict[str, Any], *, publish: bool = False
    ) -> dict[str, Any]:
        """Apply Lane A's v2 projection adapter when it is available.

        The adapter is intentionally imported lazily: this state-machine
        branch remains independently runnable until the curation package is
        integrated, and adapter-defined legacy packets are copied unchanged.
        """
        try:
            from app.phenopackets.curation.adapters import (  # type: ignore[import-not-found]
                CurationProjectionError,
                canonicalize_curation_document,
            )
        except ModuleNotFoundError as exc:
            if exc.name in {
                "app.phenopackets.curation",
                "app.phenopackets.curation.adapters",
            }:
                return deepcopy(content)
            raise

        try:
            return canonicalize_curation_document(content, publish=publish)
        except CurationProjectionError as exc:
            raise PhenopacketStateService.InvalidTransition(
                f"invalid curation projection: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _lock_and_check(
        self, record_id: UUID, expected_revision: int
    ) -> Phenopacket:
        """Lock the phenopacket row FOR UPDATE and validate optimistic lock."""
        stmt = select(Phenopacket).where(Phenopacket.id == record_id).with_for_update()
        pp = (await self.db.execute(stmt)).scalar_one_or_none()
        if pp is None:
            raise self.RecordNotFound(f"Phenopacket {record_id!r} not found")
        if pp.revision != expected_revision:
            raise self.RevisionMismatch(
                f"expected revision {expected_revision}, current is {pp.revision}"
            )
        return pp

    def _is_owner(self, pp: Phenopacket, actor: User) -> bool:
        """True when actor's id matches draft_owner_id (and owner is set)."""
        return pp.draft_owner_id is not None and pp.draft_owner_id == actor.id

    async def _latest_revision_row(self, record_id: UUID) -> PhenopacketRevision | None:
        """Return the most-recent revision row for this record, or None."""
        result = await self.db.execute(
            select(PhenopacketRevision)
            .where(PhenopacketRevision.record_id == record_id)
            .order_by(PhenopacketRevision.revision_number.desc())
        )
        return result.scalars().first()

    async def _append_revision(
        self,
        pp: Phenopacket,
        *,
        state: str,
        content: dict[str, Any],
        change_patch: list[dict[str, Any]] | None,
        change_reason: str,
        actor: User,
        from_state: str | None,
        to_state: str,
        event_type: str,
        parent_revision_id: int | None = None,
        import_run_id: UUID | None = None,
    ) -> PhenopacketRevision:
        """Append and flush a revision; never update historical revision rows."""
        parent = parent_revision_id
        if parent is None:
            latest = await self._latest_revision_row(pp.id)
            parent = latest.id if latest is not None else None
        pp.revision += 1
        curation = content.get("hnf1bCuration", {})
        projection_payload = {
            field: content.get(field)
            for field in (
                "id",
                "subject",
                "phenotypicFeatures",
                "diseases",
                "interpretations",
                "measurements",
                "metaData",
            )
            if field in content
        }
        projection_hash = hashlib.sha256(
            json.dumps(
                projection_payload, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        ledger_payload = {
            "parent_revision_id": parent,
            "revision_number": pp.revision,
            "state": state,
            "event_type": event_type,
            "from_state": from_state,
            "to_state": to_state,
            "change_reason": change_reason,
            "change_patch": change_patch,
            "projection_hash": projection_hash,
        }
        ledger_hash = hashlib.sha256(
            json.dumps(ledger_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        revision = PhenopacketRevision(
            record_id=pp.id,
            parent_revision_id=parent,
            revision_number=pp.revision,
            state=state,
            content_jsonb=content,
            change_patch=change_patch,
            change_reason=change_reason,
            actor_id=actor.id,
            import_run_id=import_run_id,
            from_state=from_state,
            to_state=to_state,
            event_type=event_type,
            profile_schema_version=str(curation.get("schemaVersion", "legacy")),
            projection_version=str(
                curation.get("projection", {}).get("algorithmVersion", "legacy")
            ),
            ledger_hash=ledger_hash,
            projection_hash=projection_hash,
        )
        self.db.add(revision)
        await self.db.flush()
        return revision

    async def _effective_state(self, pp: Phenopacket) -> State:
        """Return the state governing edit-cycle decisions for this phenopacket.

        Spec invariant I9 — pure function of (pp.state, editing_revision_id,
        editing revision's state). If editing_revision_id is set, the
        referenced revision row's state is authoritative; otherwise pp.state.
        """
        if pp.editing_revision_id is None:
            return cast(State, pp.state)
        rev = (
            await self.db.execute(
                select(PhenopacketRevision).where(
                    PhenopacketRevision.id == pp.editing_revision_id
                )
            )
        ).scalar_one()
        return cast(State, rev.state)

    # ------------------------------------------------------------------
    # §6.1 — Clone-to-draft (published) or in-place edit (draft / changes_requested)
    # ------------------------------------------------------------------

    async def edit_record(
        self,
        record_id: UUID,
        *,
        new_content: dict[str, Any],
        change_reason: str,
        expected_revision: int,
        actor: User,
    ) -> Phenopacket:
        """Save new content to a phenopacket.

        Dispatches on the effective state (spec §4.2.1):
        - effective == 'published' (editing_revision_id IS NULL) → §6.1 clone-to-draft.
        - effective ∈ {draft, changes_requested}                 → §6.3 in-place save.
        - effective ∈ {in_review, approved}                      → 409 edit_forbidden.
        - effective == 'archived'                          → 409 invalid_transition.
        """
        pp = await self._lock_and_check(record_id, expected_revision)
        new_content = self._canonicalize_for_persistence(new_content)
        effective = await self._effective_state(pp)

        if effective == "published":
            return await self._clone_to_draft(pp, new_content, change_reason, actor)

        if effective in ("draft", "changes_requested"):
            return await self._inplace_save(pp, new_content, change_reason, actor)

        if effective in ("in_review", "approved"):
            raise self.InvalidTransition(
                f"cannot edit a record whose effective state is {effective!r};"
                " withdraw or resubmit first"
            )

        # archived
        raise self.InvalidTransition(
            f"cannot edit a record whose effective state is {effective!r}"
        )

    async def _clone_to_draft(
        self,
        pp: Phenopacket,
        new_content: dict[str, Any],
        change_reason: str,
        actor: User,
    ) -> Phenopacket:
        """§6.1 transaction: insert a draft revision row, update working copy."""
        if pp.editing_revision_id is not None:
            raise self.EditInProgress(
                f"record already has an in-progress edit "
                f"(editing_revision_id={pp.editing_revision_id})"
            )

        # Compute patch from public head content
        head_row = (
            await self.db.execute(
                select(PhenopacketRevision).where(
                    PhenopacketRevision.id == pp.head_published_revision_id
                )
            )
        ).scalar_one()
        patch = compute_json_patch(head_row.content_jsonb, new_content)

        rev = await self._append_revision(
            pp,
            state="draft",
            content=new_content,
            change_patch=patch,
            change_reason=change_reason,
            actor=actor,
            from_state="published",
            to_state="draft",
            event_type="draft_created",
        )

        pp.phenopacket = new_content
        pp.editing_revision_id = rev.id
        pp.draft_owner_id = actor.id
        # state stays 'published'; head_published_revision_id unchanged

        return pp

    async def _inplace_save(
        self,
        pp: Phenopacket,
        new_content: dict[str, Any],
        change_reason: str,
        actor: User,
    ) -> Phenopacket:
        """§6.3 transaction: bump revision + overwrite working copy, no new row."""
        # Ownership check — §6.3: actor must be owner OR admin; no NULL carve-out.
        # _is_owner() returns False when draft_owner_id is None, so NULL-owner
        # drafts are correctly rejected for non-admin curators.
        not_admin = actor.role != "admin"
        if not_admin and not self._is_owner(pp, actor):
            raise self.ForbiddenNotOwner(
                f"actor {actor.id} is not the draft owner ({pp.draft_owner_id})"
            )

        previous = await self._latest_revision_row(pp.id)
        patch = (
            compute_json_patch(previous.content_jsonb, new_content)
            if previous is not None
            else None
        )
        revision = await self._append_revision(
            pp,
            state=await self._effective_state(pp),
            content=new_content,
            change_patch=patch,
            change_reason=change_reason,
            actor=actor,
            from_state=await self._effective_state(pp),
            to_state=await self._effective_state(pp),
            event_type="draft_saved",
        )
        pp.phenopacket = new_content
        pp.editing_revision_id = revision.id
        return pp

    # ------------------------------------------------------------------
    # §6.2 + §6.4 — State transitions
    # ------------------------------------------------------------------

    async def transition(
        self,
        record_id: UUID,
        *,
        to_state: str,
        reason: str,
        expected_revision: int,
        actor: User,
    ) -> tuple[Phenopacket, PhenopacketRevision]:
        """Perform a state transition per the §4.1 guard matrix.

        Delegates to :meth:`_publish` for ``to_state='published'`` (§6.2).
        All other transitions follow the §6.4 simple-transition path.
        """
        pp = await self._lock_and_check(record_id, expected_revision)

        # §4.2.1: guard matrix reads the *effective* state (revision row if a
        # clone-to-draft edit is in flight, pp.state otherwise) so that a
        # cloned draft whose pp.state is still 'published' can advance through
        # the review cycle.
        effective = await self._effective_state(pp)
        try:
            check_transition(
                cast(State, effective),
                cast(State, to_state),
                role=cast(Role, actor.role),
                is_owner=self._is_owner(pp, actor),
            )
        except TransitionError as exc:
            if exc.code == "invalid_transition":
                raise self.InvalidTransition(str(exc)) from exc
            if exc.code == "forbidden_not_owner":
                raise self.ForbiddenNotOwner(str(exc)) from exc
            # forbidden_role
            raise PermissionError(str(exc)) from exc

        if to_state == "published":
            return await self._publish(pp, reason, actor)

        return await self._simple_transition(pp, to_state, reason, actor)

    async def _simple_transition(
        self,
        pp: Phenopacket,
        to_state: str,
        reason: str,
        actor: User,
    ) -> tuple[Phenopacket, PhenopacketRevision]:
        """§6.4: bump revision, snapshot working copy into a new row, advance state.

        Spec §4.2.1 — from_state reads effective state, not pp.state. pp.state
        advancement is gated by I8: only for never-published records OR on archive.
        """
        from_state = await self._effective_state(pp)

        # Compute the patch against the *previous transition's* content, not the
        # latest draft-in-progress row. After a clone + in-place save the latest
        # row is the draft row, whose content equals pp.phenopacket, giving an
        # empty patch. We want "content before this transition → content after."
        prev = (
            await self.db.execute(
                select(PhenopacketRevision)
                .where(
                    PhenopacketRevision.record_id == pp.id,
                    PhenopacketRevision.revision_number < pp.revision,
                )
                .order_by(PhenopacketRevision.revision_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        patch = compute_json_patch(prev.content_jsonb, pp.phenopacket) if prev else None

        rev = await self._append_revision(
            pp,
            state=to_state,
            content=pp.phenopacket,
            change_patch=patch,
            change_reason=reason,
            actor=actor,
            from_state=from_state,
            to_state=to_state,
            event_type="state_transition",
        )

        # I8: pp.state advances only for never-published records OR archive.
        if pp.head_published_revision_id is None or to_state == "archived":
            pp.state = to_state

        if to_state == "archived":
            # archive is terminal: clear both owner and edit pointer
            pp.draft_owner_id = None
            pp.editing_revision_id = None
        else:
            # Update editing_revision_id to track the in-flight snapshot.
            # draft_owner_id is preserved through submit / withdraw / resubmit
            # so the curator can continue owning through the review cycle.
            pp.editing_revision_id = rev.id

        return pp, rev

    async def _publish(
        self,
        pp: Phenopacket,
        reason: str,
        actor: User,
    ) -> tuple[Phenopacket, PhenopacketRevision]:
        """§6.2 head-swap: promote the approved revision to published + head."""
        if pp.editing_revision_id is None:
            raise self.InvalidTransition(
                "cannot publish: no active approved editing revision"
            )
        try:
            approved = (
                await self.db.execute(
                    select(PhenopacketRevision).where(
                        PhenopacketRevision.id == pp.editing_revision_id,
                        PhenopacketRevision.record_id == pp.id,
                        PhenopacketRevision.state == "approved",
                    )
                )
            ).scalar_one()
        except NoResultFound:
            raise self.InvalidTransition(
                "cannot publish: active editing revision is not an approved revision"
            )

        published_content = self._canonicalize_for_persistence(
            approved.content_jsonb, publish=True
        )
        published = await self._append_revision(
            pp,
            state="published",
            content=published_content,
            change_patch=compute_json_patch(pp.phenopacket, published_content),
            change_reason=reason,
            actor=actor,
            from_state="approved",
            to_state="published",
            event_type="published",
            parent_revision_id=approved.id,
        )
        pp.state = "published"
        pp.phenopacket = published_content
        pp.head_published_revision_id = published.id
        pp.editing_revision_id = None  # cleared on publish (§6.2 step 10)
        pp.draft_owner_id = None  # I5: cleared on publish

        return pp, published

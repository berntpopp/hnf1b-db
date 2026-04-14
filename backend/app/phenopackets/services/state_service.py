"""PhenopacketStateService — the four §6 transaction sequences.

Every public method opens a single async transaction, acquires
``SELECT ... FOR UPDATE`` on the phenopacket row, checks the optimistic lock,
runs the guard matrix, mutates pointers + revisions + state atomically, then
commits.

Spec reference:
  docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md §6.
"""

from __future__ import annotations

import logging
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
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

    # ------------------------------------------------------------------

    def __init__(self, db: AsyncSession) -> None:
        """Initialise with an async database session."""
        self.db = db

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
            raise KeyError(f"Phenopacket {record_id!r} not found")
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

        - ``state == 'published'``      → §6.1 clone-to-draft.
        - ``state ∈ {draft, changes_requested}`` → §6.3 in-place save.
        - Any other state raises :class:`InvalidTransition`.
        """
        pp = await self._lock_and_check(record_id, expected_revision)

        if pp.state == "published":
            return await self._clone_to_draft(pp, new_content, change_reason, actor)

        if pp.state in ("draft", "changes_requested"):
            return await self._inplace_save(pp, new_content, change_reason, actor)

        raise self.InvalidTransition(
            f"cannot edit a record in state {pp.state!r}; withdraw or resubmit first"
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

        pp.revision += 1
        rev = PhenopacketRevision(
            record_id=pp.id,
            revision_number=pp.revision,
            state="draft",
            content_jsonb=new_content,
            change_patch=patch,
            change_reason=change_reason,
            actor_id=actor.id,
            from_state="published",
            to_state="draft",
            is_head_published=False,
        )
        self.db.add(rev)
        await self.db.flush()  # obtain rev.id before writing the FK

        pp.phenopacket = new_content
        pp.editing_revision_id = rev.id
        pp.draft_owner_id = actor.id
        # state stays 'published'; head_published_revision_id unchanged

        await self.db.commit()
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

        pp.revision += 1
        pp.phenopacket = new_content

        # If there's an in-progress revision row, update its content in-place
        if pp.editing_revision_id:
            editing = (
                await self.db.execute(
                    select(PhenopacketRevision).where(
                        PhenopacketRevision.id == pp.editing_revision_id
                    )
                )
            ).scalar_one()
            editing.content_jsonb = new_content
            editing.change_reason = change_reason
            # revision_number on the row is intentionally NOT updated (I6: gaps)

        await self.db.commit()
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

        # Guard-matrix check — cast plain str to the narrow Literal types that
        # check_transition expects; runtime values are validated by the rule dict.
        try:
            check_transition(
                cast(State, pp.state),
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
        """§6.4: bump revision, snapshot working copy into a new row, advance state."""
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

        pp.revision += 1
        from_state = pp.state

        rev = PhenopacketRevision(
            record_id=pp.id,
            revision_number=pp.revision,
            state=to_state,
            content_jsonb=pp.phenopacket,
            change_patch=patch,
            change_reason=reason,
            actor_id=actor.id,
            from_state=from_state,
            to_state=to_state,
            is_head_published=False,
        )
        self.db.add(rev)
        await self.db.flush()  # get rev.id

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

        await self.db.commit()
        return pp, rev

    async def _publish(
        self,
        pp: Phenopacket,
        reason: str,
        actor: User,
    ) -> tuple[Phenopacket, PhenopacketRevision]:
        """§6.2 head-swap: promote the approved revision to published + head."""
        try:
            approved = (
                await self.db.execute(
                    select(PhenopacketRevision).where(
                        PhenopacketRevision.record_id == pp.id,
                        PhenopacketRevision.state == "approved",
                    )
                )
            ).scalar_one()
        except NoResultFound:
            raise self.InvalidTransition(
                "cannot publish: no revision row with state='approved' found"
            )
        except MultipleResultsFound:
            raise self.InvalidTransition(
                "cannot publish: multiple approved revisions found"
                " — data integrity violation"
            )

        # Clear any previous head-published flag for this record
        await self.db.execute(
            update(PhenopacketRevision)
            .where(
                PhenopacketRevision.record_id == pp.id,
                PhenopacketRevision.is_head_published.is_(True),
            )
            .values(is_head_published=False)
        )

        # Re-use the approved row: update its state + is_head_published
        approved.state = "published"
        approved.to_state = "published"
        approved.is_head_published = True
        approved.change_reason = reason

        pp.revision += 1
        pp.state = "published"
        pp.phenopacket = approved.content_jsonb
        pp.head_published_revision_id = approved.id
        pp.editing_revision_id = None  # cleared on publish (§6.2 step 10)
        pp.draft_owner_id = None  # I5: cleared on publish

        try:
            await self.db.commit()
        except IntegrityError as exc:
            # ux_head_published_per_record unique violation — concurrent publish
            raise self.InvalidTransition(
                "concurrent publish detected; please retry"
            ) from exc

        return pp, approved

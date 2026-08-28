"""Activate independent-review locking, audit, and final-state invariants.

Revision ID: e0f422b00006
Revises: d0f422b00005
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "e0f422b00006"
down_revision = "d0f422b00005"
branch_labels = None
depends_on = None


def assert_independent_review_downgrade_safe(bind) -> None:
    """Refuse to remove protections while any protected evidence exists."""
    evidence = (
        bind.execute(
            sa.text(
                """
                SELECT
                    (SELECT count(*) FROM comments
                     WHERE review_revision_id IS NOT NULL) AS blocking_issues,
                    (SELECT count(*) FROM comment_resolution_events)
                        AS resolution_events,
                    (SELECT count(*) FROM phenopacket_revisions
                     WHERE ledger_version = 2) AS v2_revisions,
                    (SELECT count(*) FROM phenopacket_revisions
                     WHERE decision_metadata IS NOT NULL) AS decision_metadata,
                    (SELECT count(*) FROM phenopacket_revisions
                     WHERE actor_role IS NOT NULL) AS actor_roles,
                    (SELECT count(*) FROM phenopacket_revisions
                     WHERE content_sha256 IS NOT NULL) AS content_digests
                """
            )
        )
        .mappings()
        .one()
    )
    present = [name for name, count in evidence.items() if int(count) > 0]
    if present:
        raise RuntimeError(
            "refusing independent-review downgrade; evidence present: "
            + ", ".join(present)
        )


def _preflight_and_backfill_active_owners() -> None:
    """Resolve active owners from exact immutable ancestry or fail atomically."""
    op.execute(
        """
        CREATE TEMP TABLE independent_review_owner_candidates
        ON COMMIT DROP AS
        WITH RECURSIVE ancestry AS (
            SELECT
                packet.id AS packet_id,
                packet.head_published_revision_id AS head_id,
                revision.id AS revision_id,
                revision.record_id AS revision_record_id,
                revision.parent_revision_id AS parent_id,
                revision.revision_number,
                revision.state AS revision_state,
                revision.event_type,
                revision.actor_id,
                CASE
                    WHEN revision.id IS NULL THEN ARRAY[]::BIGINT[]
                    ELSE ARRAY[revision.id]
                END AS path,
                FALSE AS cycle,
                (
                    revision.id IS NULL
                    OR revision.record_id IS DISTINCT FROM packet.id
                    OR revision.state NOT IN
                        ('draft', 'in_review', 'changes_requested', 'approved')
                ) AS invalid
            FROM phenopackets packet
            LEFT JOIN phenopacket_revisions revision
              ON revision.id = packet.editing_revision_id
            WHERE packet.editing_revision_id IS NOT NULL
              AND packet.draft_owner_id IS NULL

            UNION ALL

            SELECT
                ancestry.packet_id,
                ancestry.head_id,
                parent.id,
                parent.record_id,
                parent.parent_revision_id,
                parent.revision_number,
                parent.state,
                parent.event_type,
                parent.actor_id,
                ancestry.path || COALESCE(parent.id, -1),
                parent.id = ANY(ancestry.path),
                (
                    ancestry.invalid
                    OR parent.id IS NULL
                    OR parent.record_id IS DISTINCT FROM ancestry.packet_id
                    OR parent.revision_number >= ancestry.revision_number
                    OR parent.id = ANY(ancestry.path)
                )
            FROM ancestry
            LEFT JOIN phenopacket_revisions parent
              ON parent.id = ancestry.parent_id
            WHERE ancestry.revision_id IS NOT NULL
              AND ancestry.parent_id IS NOT NULL
              AND NOT ancestry.cycle
              AND (
                  ancestry.head_id IS NULL
                  OR ancestry.revision_id <> ancestry.head_id
              )
        ), summarized AS (
            SELECT
                packet_id,
                head_id,
                bool_or(invalid) AS has_invalid_link,
                bool_or(revision_id = head_id) FILTER (WHERE head_id IS NOT NULL)
                    AS reached_head,
                bool_or(revision_id IS NOT NULL AND parent_id IS NULL)
                    FILTER (WHERE head_id IS NULL) AS reached_root,
                count(*) FILTER (
                    WHERE head_id IS NULL AND event_type = 'created'
                ) AS created_events,
                count(*) FILTER (
                    WHERE head_id IS NULL AND event_type = 'created'
                      AND parent_id IS NULL
                ) AS created_roots,
                count(*) FILTER (
                    WHERE head_id IS NOT NULL AND event_type = 'draft_created'
                ) AS draft_created_events,
                count(*) FILTER (
                    WHERE head_id IS NOT NULL AND event_type = 'draft_created'
                      AND parent_id = head_id
                ) AS draft_created_roots,
                max(actor_id) FILTER (
                    WHERE (
                        head_id IS NULL
                        AND event_type = 'created'
                        AND parent_id IS NULL
                    ) OR (
                        head_id IS NOT NULL
                        AND event_type = 'draft_created'
                        AND parent_id = head_id
                    )
                ) AS owner_id
            FROM ancestry
            GROUP BY packet_id, head_id
        )
        SELECT
            packet_id,
            owner_id,
            (
                NOT has_invalid_link
                AND owner_id IS NOT NULL
                AND (
                    (
                        head_id IS NULL
                        AND COALESCE(reached_root, FALSE)
                        AND created_events = 1
                        AND created_roots = 1
                    ) OR (
                        head_id IS NOT NULL
                        AND COALESCE(reached_head, FALSE)
                        AND draft_created_events = 1
                        AND draft_created_roots = 1
                    )
                )
            ) AS valid
        FROM summarized;
        """
    )
    op.execute(
        """
        DO $$
        DECLARE invalid_ids TEXT;
        BEGIN
            SELECT string_agg(packet_id::TEXT, ', ' ORDER BY packet_id)
              INTO invalid_ids
              FROM independent_review_owner_candidates
             WHERE NOT valid;
            IF invalid_ids IS NOT NULL THEN
                RAISE EXCEPTION
                    'independent review owner preflight failed: %', invalid_ids;
            END IF;
        END;
        $$;
        """
    )
    op.execute(
        """
        UPDATE phenopackets packet
           SET draft_owner_id = candidate.owner_id
          FROM independent_review_owner_candidates candidate
         WHERE candidate.valid
           AND packet.id = candidate.packet_id
           AND packet.draft_owner_id IS NULL;
        """
    )
    op.execute("DROP TABLE independent_review_owner_candidates")


def _install_revision_lock_trigger() -> None:
    op.execute(
        """
        CREATE FUNCTION lock_phenopacket_for_revision_insert()
        RETURNS trigger AS $$
        DECLARE
            packet phenopackets%ROWTYPE;
            head_number INTEGER;
        BEGIN
            SELECT * INTO packet
              FROM phenopackets
             WHERE id = NEW.record_id
             FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'review_revision_mismatch';
            END IF;

            IF packet.head_published_revision_id IS NOT NULL THEN
                SELECT revision_number INTO head_number
                  FROM phenopacket_revisions
                 WHERE id = packet.head_published_revision_id
                   AND record_id = packet.id
                   AND state = 'published';
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'review_author_unknown';
                END IF;
            END IF;

            IF NEW.state = 'approved' AND EXISTS (
                SELECT 1
                  FROM comments issue
                  JOIN phenopacket_revisions reviewed
                    ON reviewed.id = issue.review_revision_id
                 WHERE issue.record_type = 'phenopacket'
                   AND issue.record_id = packet.id
                   AND issue.review_revision_id IS NOT NULL
                   AND issue.resolved_at IS NULL
                   AND issue.deleted_at IS NULL
                   AND reviewed.record_id = packet.id
                   AND (head_number IS NULL OR reviewed.revision_number > head_number)
            ) THEN
                RAISE EXCEPTION 'unresolved_review_issues';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER phenopacket_revisions_00_lock_record
        BEFORE INSERT ON phenopacket_revisions
        FOR EACH ROW EXECUTE FUNCTION lock_phenopacket_for_revision_insert();
        """
    )


def _install_comment_and_event_triggers() -> None:
    op.execute(
        """
        CREATE FUNCTION require_independent_review_actor(
            packet_id UUID,
            owner_id BIGINT,
            candidate_id BIGINT,
            head_number INTEGER,
            review_actor_id BIGINT,
            claimed_actor_role TEXT
        ) RETURNS VOID AS $$
        DECLARE
            review_actor users%ROWTYPE;
            candidate_submitter_id BIGINT;
        BEGIN
            IF owner_id IS NULL THEN
                RAISE EXCEPTION 'review_author_unknown';
            END IF;
            SELECT * INTO review_actor FROM users WHERE id = review_actor_id;
            IF NOT FOUND OR NOT review_actor.is_active
               OR review_actor.role NOT IN ('curator','admin') THEN
                RAISE EXCEPTION 'reviewer_not_eligible';
            END IF;
            IF claimed_actor_role IS NOT NULL
               AND claimed_actor_role <> review_actor.role THEN
                RAISE EXCEPTION 'reviewer_actor_role_mismatch';
            END IF;
            IF review_actor.id = owner_id THEN
                RAISE EXCEPTION 'self_review_forbidden';
            END IF;

            SELECT actor_id INTO candidate_submitter_id
              FROM phenopacket_revisions
             WHERE id = candidate_id AND record_id = packet_id
               AND state = 'in_review';
            IF NOT FOUND THEN
                RAISE EXCEPTION 'review_revision_mismatch';
            END IF;
            IF review_actor.id = candidate_submitter_id THEN
                RAISE EXCEPTION 'reviewer_submitted';
            END IF;
            IF EXISTS (
                SELECT 1 FROM phenopacket_revisions contribution
                 WHERE contribution.record_id = packet_id
                   AND contribution.actor_id = review_actor.id
                   AND contribution.event_type IN
                       ('created','draft_created','draft_saved')
                   AND (
                       head_number IS NULL
                       OR contribution.revision_number > head_number
                   )
            ) THEN
                RAISE EXCEPTION 'reviewer_contributed';
            END IF;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_review_issue_insert()
        RETURNS trigger AS $$
        DECLARE
            packet phenopackets%ROWTYPE;
            active_revision phenopacket_revisions%ROWTYPE;
            reviewed_revision phenopacket_revisions%ROWTYPE;
            head_number INTEGER;
        BEGIN
            IF NEW.review_revision_id IS NULL THEN
                RETURN NEW;
            END IF;
            IF NEW.record_type <> 'phenopacket'
               OR NEW.deleted_at IS NOT NULL
               OR NEW.resolved_at IS NOT NULL THEN
                RAISE EXCEPTION 'review_issue_mutation_forbidden';
            END IF;

            SELECT * INTO packet FROM phenopackets
             WHERE id = NEW.record_id FOR UPDATE;
            IF NOT FOUND OR packet.draft_owner_id IS NULL THEN
                RAISE EXCEPTION 'review_author_unknown';
            END IF;
            SELECT * INTO active_revision FROM phenopacket_revisions
             WHERE id = packet.editing_revision_id AND record_id = packet.id;
            IF NOT FOUND OR active_revision.state <> 'in_review' THEN
                RAISE EXCEPTION 'review_closed';
            END IF;
            IF active_revision.id <> NEW.review_revision_id THEN
                RAISE EXCEPTION 'review_revision_mismatch';
            END IF;
            SELECT * INTO reviewed_revision FROM phenopacket_revisions
             WHERE id = NEW.review_revision_id
               AND record_id = packet.id AND state = 'in_review';
            IF NOT FOUND THEN
                RAISE EXCEPTION 'review_revision_mismatch';
            END IF;
            IF packet.head_published_revision_id IS NOT NULL THEN
                SELECT revision_number INTO head_number
                  FROM phenopacket_revisions
                 WHERE id = packet.head_published_revision_id
                   AND record_id = packet.id AND state = 'published';
                IF NOT FOUND OR reviewed_revision.revision_number <= head_number THEN
                    RAISE EXCEPTION 'review_revision_mismatch';
                END IF;
            END IF;
            PERFORM require_independent_review_actor(
                packet.id,
                packet.draft_owner_id,
                reviewed_revision.id,
                head_number,
                NEW.author_id,
                NULL
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER comments_review_issue_guard
        BEFORE INSERT ON comments
        FOR EACH ROW EXECUTE FUNCTION validate_review_issue_insert();
        """
    )
    op.execute(
        """
        CREATE FUNCTION lock_phenopacket_for_resolution_event()
        RETURNS trigger AS $$
        DECLARE
            issue_probe comments%ROWTYPE;
            issue comments%ROWTYPE;
            packet phenopackets%ROWTYPE;
            active_revision phenopacket_revisions%ROWTYPE;
            reviewed_revision phenopacket_revisions%ROWTYPE;
            walk_revision phenopacket_revisions%ROWTYPE;
            parent_revision phenopacket_revisions%ROWTYPE;
            head_number INTEGER;
            candidate_in_cycle BOOLEAN := FALSE;
            visited BIGINT[] := ARRAY[]::BIGINT[];
            latest_event comment_resolution_events%ROWTYPE;
        BEGIN
            SELECT * INTO issue_probe FROM comments WHERE id = NEW.comment_id;
            IF NOT FOUND OR issue_probe.review_revision_id IS NULL
               OR issue_probe.record_type <> 'phenopacket' THEN
                RAISE EXCEPTION 'review_issue_mutation_forbidden';
            END IF;

            SELECT * INTO packet FROM phenopackets
             WHERE id = issue_probe.record_id FOR UPDATE;
            IF NOT FOUND OR packet.draft_owner_id IS NULL THEN
                RAISE EXCEPTION 'review_author_unknown';
            END IF;
            SELECT * INTO issue FROM comments
             WHERE id = NEW.comment_id FOR UPDATE;
            IF NOT FOUND OR issue.review_revision_id IS NULL
               OR issue.record_type <> 'phenopacket'
               OR issue.deleted_at IS NOT NULL
               OR issue.record_id IS DISTINCT FROM issue_probe.record_id
               OR issue.record_type IS DISTINCT FROM issue_probe.record_type
               OR issue.review_revision_id IS DISTINCT FROM
                  issue_probe.review_revision_id THEN
                RAISE EXCEPTION 'review_issue_mutation_forbidden';
            END IF;
            SELECT * INTO latest_event FROM comment_resolution_events event
             WHERE event.comment_id = issue.id
             ORDER BY event.id DESC LIMIT 1;
            IF FOUND AND NOT (
                (
                    latest_event.action = 'resolved'
                    AND issue.resolved_at IS NOT NULL
                    AND issue.resolved_by_id = latest_event.actor_id
                ) OR (
                    latest_event.action = 'reopened'
                    AND issue.resolved_at IS NULL
                    AND issue.resolved_by_id IS NULL
                )
            ) THEN
                RAISE EXCEPTION 'review_issue_resolution_projection_mismatch';
            END IF;
            SELECT * INTO active_revision FROM phenopacket_revisions
             WHERE id = packet.editing_revision_id AND record_id = packet.id;
            IF NOT FOUND OR active_revision.state NOT IN ('in_review','changes_requested') THEN
                RAISE EXCEPTION 'review_closed';
            END IF;
            SELECT * INTO reviewed_revision FROM phenopacket_revisions
             WHERE id = issue.review_revision_id
               AND record_id = packet.id AND state = 'in_review';
            IF NOT FOUND THEN
                RAISE EXCEPTION 'review_revision_mismatch';
            END IF;
            IF packet.head_published_revision_id IS NOT NULL THEN
                SELECT revision_number INTO head_number FROM phenopacket_revisions
                 WHERE id = packet.head_published_revision_id
                   AND record_id = packet.id AND state = 'published';
                IF NOT FOUND OR reviewed_revision.revision_number <= head_number THEN
                    RAISE EXCEPTION 'review_revision_mismatch';
                END IF;
            END IF;
            walk_revision := active_revision;
            LOOP
                IF walk_revision.record_id <> packet.id
                   OR walk_revision.id = ANY(visited) THEN
                    RAISE EXCEPTION 'review_revision_mismatch';
                END IF;
                visited := array_append(visited, walk_revision.id);
                IF walk_revision.id = issue.review_revision_id THEN
                    candidate_in_cycle := TRUE;
                END IF;

                IF packet.head_published_revision_id IS NOT NULL
                   AND walk_revision.id = packet.head_published_revision_id THEN
                    IF walk_revision.state <> 'published'
                       OR NOT candidate_in_cycle THEN
                        RAISE EXCEPTION 'review_revision_mismatch';
                    END IF;
                    EXIT;
                ELSIF packet.head_published_revision_id IS NULL
                      AND walk_revision.parent_revision_id IS NULL THEN
                    IF walk_revision.event_type <> 'created'
                       OR NOT candidate_in_cycle THEN
                        RAISE EXCEPTION 'review_revision_mismatch';
                    END IF;
                    EXIT;
                ELSIF walk_revision.parent_revision_id IS NULL THEN
                    RAISE EXCEPTION 'review_revision_mismatch';
                END IF;

                SELECT * INTO parent_revision FROM phenopacket_revisions
                 WHERE id = walk_revision.parent_revision_id;
                IF NOT FOUND OR parent_revision.record_id <> packet.id
                   OR parent_revision.revision_number >=
                      walk_revision.revision_number THEN
                    RAISE EXCEPTION 'review_revision_mismatch';
                END IF;
                walk_revision := parent_revision;
            END LOOP;
            PERFORM require_independent_review_actor(
                packet.id,
                packet.draft_owner_id,
                reviewed_revision.id,
                head_number,
                NEW.actor_id,
                NEW.actor_role
            );
            IF NEW.action = 'resolved' AND issue.resolved_at IS NOT NULL THEN
                RAISE EXCEPTION 'review_issue_already_resolved';
            ELSIF NEW.action = 'reopened' AND issue.resolved_at IS NULL THEN
                RAISE EXCEPTION 'review_issue_not_resolved';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER comment_resolution_events_lock_record
        BEFORE INSERT ON comment_resolution_events
        FOR EACH ROW EXECUTE FUNCTION lock_phenopacket_for_resolution_event();
        """
    )
    op.execute(
        """
        CREATE FUNCTION project_comment_resolution_event()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.action = 'resolved' THEN
                UPDATE comments
                   SET resolved_at = NEW.created_at,
                       resolved_by_id = NEW.actor_id,
                       updated_at = NEW.created_at
                 WHERE id = NEW.comment_id;
            ELSE
                UPDATE comments
                   SET resolved_at = NULL,
                       resolved_by_id = NULL,
                       updated_at = NEW.created_at
                 WHERE id = NEW.comment_id;
            END IF;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'review_issue_resolution_projection_mismatch';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER comment_resolution_events_project_comment
        AFTER INSERT ON comment_resolution_events
        FOR EACH ROW EXECUTE FUNCTION project_comment_resolution_event();
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_resolution_event_projection()
        RETURNS trigger AS $$
        DECLARE
            issue comments%ROWTYPE;
            latest_event comment_resolution_events%ROWTYPE;
        BEGIN
            SELECT * INTO issue FROM comments WHERE id = NEW.comment_id;
            SELECT * INTO latest_event FROM comment_resolution_events event
             WHERE event.comment_id = NEW.comment_id
             ORDER BY event.id DESC LIMIT 1;
            IF issue.id IS NULL OR latest_event.id IS NULL OR NOT (
                (
                    latest_event.action = 'resolved'
                    AND issue.resolved_at IS NOT NULL
                    AND issue.resolved_by_id = latest_event.actor_id
                ) OR (
                    latest_event.action = 'reopened'
                    AND issue.resolved_at IS NULL
                    AND issue.resolved_by_id IS NULL
                )
            ) THEN
                RAISE EXCEPTION 'review_issue_resolution_projection_mismatch';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER comment_resolution_events_projection_final_state
        AFTER INSERT ON comment_resolution_events
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_resolution_event_projection();
        """
    )
    op.execute(
        """
        CREATE FUNCTION reject_comment_resolution_event_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'comment resolution events are append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER comment_resolution_events_immutable
        BEFORE UPDATE OR DELETE ON comment_resolution_events
        FOR EACH ROW EXECUTE FUNCTION reject_comment_resolution_event_mutation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_review_issue_mutation()
        RETURNS trigger AS $$
        DECLARE latest_event comment_resolution_events%ROWTYPE;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.review_revision_id IS NOT NULL THEN
                    RAISE EXCEPTION 'review_issue_mutation_forbidden';
                END IF;
                RETURN OLD;
            END IF;

            IF OLD.review_revision_id IS NULL AND NEW.review_revision_id IS NULL THEN
                RETURN NEW;
            END IF;
            IF OLD.review_revision_id IS NULL
               OR NEW.review_revision_id IS NULL
               OR NEW.review_revision_id <> OLD.review_revision_id
               OR NEW.record_id <> OLD.record_id
               OR NEW.record_type <> OLD.record_type
               OR NEW.deleted_at IS DISTINCT FROM OLD.deleted_at
               OR NEW.deleted_by_id IS DISTINCT FROM OLD.deleted_by_id THEN
                RAISE EXCEPTION 'review_issue_mutation_forbidden';
            END IF;

            IF NEW.resolved_at IS DISTINCT FROM OLD.resolved_at
               OR NEW.resolved_by_id IS DISTINCT FROM OLD.resolved_by_id THEN
                IF pg_trigger_depth() < 2 THEN
                    RAISE EXCEPTION 'review_issue_resolution_event_required';
                END IF;
                SELECT * INTO latest_event FROM comment_resolution_events event
                 WHERE event.comment_id = OLD.id
                 ORDER BY event.id DESC LIMIT 1;
                IF NOT FOUND OR NOT (
                    (
                        latest_event.action = 'resolved'
                        AND NEW.resolved_at IS NOT NULL
                        AND NEW.resolved_by_id = latest_event.actor_id
                    ) OR (
                        latest_event.action = 'reopened'
                        AND NEW.resolved_at IS NULL
                        AND NEW.resolved_by_id IS NULL
                    )
                ) THEN
                    RAISE EXCEPTION 'review_issue_resolution_projection_mismatch';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER comments_review_issue_mutation_guard
        BEFORE UPDATE OR DELETE ON comments
        FOR EACH ROW EXECUTE FUNCTION guard_review_issue_mutation();
        """
    )


def _install_final_state_triggers() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_phenopacket_revision_pointer()
        RETURNS trigger AS $$
        DECLARE
            packet phenopackets%ROWTYPE;
            active_state TEXT;
            head_number INTEGER;
        BEGIN
            SELECT * INTO packet FROM phenopackets WHERE id = NEW.id;
            IF packet.head_published_revision_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM phenopacket_revisions revision
                WHERE revision.id = packet.head_published_revision_id
                  AND revision.record_id = packet.id
                  AND revision.state = 'published'
            ) THEN
                RAISE EXCEPTION 'head_published_revision_id must be a published revision of its record';
            END IF;
            IF packet.state = 'published' AND packet.head_published_revision_id IS NULL THEN
                RAISE EXCEPTION 'published phenopacket requires head_published_revision_id';
            END IF;
            IF packet.editing_revision_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM phenopacket_revisions revision
                WHERE revision.id = packet.editing_revision_id
                  AND revision.record_id = packet.id
                  AND revision.state IN ('draft', 'in_review', 'changes_requested', 'approved')
            ) THEN
                RAISE EXCEPTION 'editing_revision_id must be an editable revision of its record';
            END IF;
            IF packet.editing_revision_id IS NOT NULL AND packet.draft_owner_id IS NULL THEN
                RAISE EXCEPTION 'active editing_revision_id requires draft_owner_id';
            END IF;
            IF packet.state = 'archived' AND packet.editing_revision_id IS NOT NULL THEN
                RAISE EXCEPTION 'archived phenopacket cannot retain editing_revision_id';
            END IF;

            IF packet.editing_revision_id IS NOT NULL THEN
                SELECT state INTO active_state FROM phenopacket_revisions
                 WHERE id = packet.editing_revision_id AND record_id = packet.id;
            END IF;
            IF packet.head_published_revision_id IS NOT NULL THEN
                SELECT revision_number INTO head_number FROM phenopacket_revisions
                 WHERE id = packet.head_published_revision_id AND record_id = packet.id;
            END IF;
            IF active_state = 'approved' AND EXISTS (
                SELECT 1 FROM comments issue
                JOIN phenopacket_revisions reviewed
                  ON reviewed.id = issue.review_revision_id
                WHERE issue.record_type = 'phenopacket'
                  AND issue.record_id = packet.id
                  AND issue.review_revision_id IS NOT NULL
                  AND issue.resolved_at IS NULL
                  AND issue.deleted_at IS NULL
                  AND reviewed.record_id = packet.id
                  AND (head_number IS NULL OR reviewed.revision_number > head_number)
            ) THEN
                RAISE EXCEPTION 'unresolved_review_issues';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_review_issue_final_state()
        RETURNS trigger AS $$
        DECLARE
            packet phenopackets%ROWTYPE;
            packet_id UUID;
            active_state TEXT;
            head_number INTEGER;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.review_revision_id IS NULL THEN RETURN OLD; END IF;
                packet_id := OLD.record_id;
            ELSE
                IF NEW.review_revision_id IS NULL THEN RETURN NEW; END IF;
                packet_id := NEW.record_id;
            END IF;
            SELECT * INTO packet FROM phenopackets WHERE id = packet_id;
            IF NOT FOUND THEN RETURN COALESCE(NEW, OLD); END IF;
            SELECT state INTO active_state FROM phenopacket_revisions
             WHERE id = packet.editing_revision_id AND record_id = packet.id;
            IF packet.head_published_revision_id IS NOT NULL THEN
                SELECT revision_number INTO head_number FROM phenopacket_revisions
                 WHERE id = packet.head_published_revision_id AND record_id = packet.id;
            END IF;
            IF active_state = 'approved' AND EXISTS (
                SELECT 1 FROM comments issue
                JOIN phenopacket_revisions reviewed
                  ON reviewed.id = issue.review_revision_id
                WHERE issue.record_type = 'phenopacket'
                  AND issue.record_id = packet.id
                  AND issue.review_revision_id IS NOT NULL
                  AND issue.resolved_at IS NULL
                  AND issue.deleted_at IS NULL
                  AND reviewed.record_id = packet.id
                  AND (head_number IS NULL OR reviewed.revision_number > head_number)
            ) THEN
                RAISE EXCEPTION 'unresolved_review_issues';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER comments_review_issue_final_state
        AFTER INSERT OR UPDATE OR DELETE ON comments
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_review_issue_final_state();
        """
    )


def upgrade() -> None:
    """Backfill owners and activate lock-serialized independent review."""
    op.execute(
        """
        LOCK TABLE phenopackets, phenopacket_revisions, comments,
                   comment_resolution_events
        IN SHARE ROW EXCLUSIVE MODE;
        """
    )
    _preflight_and_backfill_active_owners()
    op.create_check_constraint(
        op.f("ck_phenopackets_active_edit_owner"),
        "phenopackets",
        "editing_revision_id IS NULL OR draft_owner_id IS NOT NULL",
    )
    _install_revision_lock_trigger()
    _install_comment_and_event_triggers()
    _install_final_state_triggers()


def _restore_b9_pointer_validator() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_phenopacket_revision_pointer()
        RETURNS trigger AS $$
        DECLARE
            packet phenopackets%ROWTYPE;
        BEGIN
            SELECT * INTO packet FROM phenopackets WHERE id = NEW.id;
            IF packet.head_published_revision_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM phenopacket_revisions revision
                WHERE revision.id = packet.head_published_revision_id
                  AND revision.record_id = packet.id
                  AND revision.state = 'published'
            ) THEN
                RAISE EXCEPTION 'head_published_revision_id must be a published revision of its record';
            END IF;
            IF packet.state = 'published' AND packet.head_published_revision_id IS NULL THEN
                RAISE EXCEPTION 'published phenopacket requires head_published_revision_id';
            END IF;
            IF packet.editing_revision_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM phenopacket_revisions revision
                WHERE revision.id = packet.editing_revision_id
                  AND revision.record_id = packet.id
                  AND revision.state IN ('draft', 'in_review', 'changes_requested', 'approved')
            ) THEN
                RAISE EXCEPTION 'editing_revision_id must be an editable revision of its record';
            END IF;
            IF packet.state = 'archived' AND packet.editing_revision_id IS NOT NULL THEN
                RAISE EXCEPTION 'archived phenopacket cannot retain editing_revision_id';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    """Remove activation only when no protected audit evidence exists."""
    assert_independent_review_downgrade_safe(op.get_bind())
    op.execute("DROP TRIGGER comments_review_issue_final_state ON comments")
    op.execute("DROP FUNCTION validate_review_issue_final_state()")
    op.execute("DROP TRIGGER comments_review_issue_mutation_guard ON comments")
    op.execute("DROP FUNCTION guard_review_issue_mutation()")
    op.execute(
        "DROP TRIGGER comment_resolution_events_immutable ON comment_resolution_events"
    )
    op.execute("DROP FUNCTION reject_comment_resolution_event_mutation()")
    op.execute(
        "DROP TRIGGER comment_resolution_events_projection_final_state "
        "ON comment_resolution_events"
    )
    op.execute("DROP FUNCTION validate_resolution_event_projection()")
    op.execute(
        "DROP TRIGGER IF EXISTS comment_resolution_events_project_comment "
        "ON comment_resolution_events"
    )
    op.execute("DROP FUNCTION IF EXISTS project_comment_resolution_event()")
    op.execute(
        "DROP TRIGGER comment_resolution_events_lock_record "
        "ON comment_resolution_events"
    )
    op.execute("DROP FUNCTION lock_phenopacket_for_resolution_event()")
    op.execute("DROP TRIGGER comments_review_issue_guard ON comments")
    op.execute("DROP FUNCTION validate_review_issue_insert()")
    op.execute(
        "DROP FUNCTION require_independent_review_actor("
        "UUID,BIGINT,BIGINT,INTEGER,BIGINT,TEXT)"
    )
    op.execute(
        "DROP TRIGGER phenopacket_revisions_00_lock_record ON phenopacket_revisions"
    )
    op.execute("DROP FUNCTION lock_phenopacket_for_revision_insert()")
    op.drop_constraint(
        op.f("ck_phenopackets_active_edit_owner"),
        "phenopackets",
        type_="check",
    )
    _restore_b9_pointer_validator()

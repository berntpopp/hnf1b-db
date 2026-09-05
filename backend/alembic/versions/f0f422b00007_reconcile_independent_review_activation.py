"""Reconcile independent-review activation trigger definitions.

Revision ID: f0f422b00007
Revises: e0f422b00006
Create Date: 2026-08-30
"""

from __future__ import annotations

from alembic import op

revision = "f0f422b00007"
down_revision = "e0f422b00006"
branch_labels = None
depends_on = None


def _drop_replaced_triggers() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS comment_resolution_events_projection_final_state "
        "ON comment_resolution_events"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS comment_resolution_events_project_comment "
        "ON comment_resolution_events"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS comments_review_issue_mutation_guard ON comments"
    )


def _install_projection_functions() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION project_comment_resolution_event()
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
        CREATE OR REPLACE FUNCTION validate_resolution_event_projection()
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
                    AND issue.resolved_at IS NOT DISTINCT FROM
                        latest_event.created_at
                    AND issue.resolved_by_id IS NOT DISTINCT FROM
                        latest_event.actor_id
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


def _reconcile_latest_resolution_events() -> None:
    op.execute(
        """
        DO $$
        DECLARE unsafe_ids TEXT;
        BEGIN
            WITH latest AS (
                SELECT DISTINCT ON (event.comment_id)
                    event.comment_id,
                    event.action,
                    event.actor_id,
                    event.created_at
                FROM comment_resolution_events event
                ORDER BY event.comment_id, event.id DESC
            )
            SELECT string_agg(latest.comment_id::TEXT, ', ' ORDER BY latest.comment_id)
              INTO unsafe_ids
              FROM latest
              LEFT JOIN comments issue ON issue.id = latest.comment_id
             WHERE issue.id IS NULL
                OR issue.review_revision_id IS NULL
                OR issue.record_type <> 'phenopacket'
                OR issue.deleted_at IS NOT NULL
                OR latest.action NOT IN ('resolved', 'reopened');

            IF unsafe_ids IS NOT NULL THEN
                RAISE EXCEPTION
                    'independent review resolution reconciliation unsafe comment_ids: %',
                    unsafe_ids;
            END IF;
        END;
        $$;
        """
    )
    op.execute(
        """
        WITH latest AS (
            SELECT DISTINCT ON (event.comment_id)
                event.comment_id,
                event.action,
                event.actor_id,
                event.created_at
            FROM comment_resolution_events event
            ORDER BY event.comment_id, event.id DESC
        )
        UPDATE comments issue
           SET resolved_at = latest.created_at,
               resolved_by_id = latest.actor_id,
               updated_at = GREATEST(issue.updated_at, latest.created_at)
          FROM latest
         WHERE issue.id = latest.comment_id
           AND latest.action = 'resolved'
           AND (
               issue.resolved_at IS NULL
               OR issue.resolved_at IS DISTINCT FROM latest.created_at
               OR issue.resolved_by_id IS DISTINCT FROM latest.actor_id
           );
        """
    )
    op.execute(
        """
        WITH latest AS (
            SELECT DISTINCT ON (event.comment_id)
                event.comment_id,
                event.action,
                event.created_at
            FROM comment_resolution_events event
            ORDER BY event.comment_id, event.id DESC
        )
        UPDATE comments issue
           SET resolved_at = NULL,
               resolved_by_id = NULL,
               updated_at = GREATEST(issue.updated_at, latest.created_at)
          FROM latest
         WHERE issue.id = latest.comment_id
           AND latest.action = 'reopened'
           AND (
               issue.resolved_at IS NOT NULL
               OR issue.resolved_by_id IS NOT NULL
           );
        """
    )
    op.execute(
        """
        DO $$
        DECLARE mismatched_ids TEXT;
        BEGIN
            WITH latest AS (
                SELECT DISTINCT ON (event.comment_id)
                    event.comment_id,
                    event.action,
                    event.actor_id,
                    event.created_at
                FROM comment_resolution_events event
                ORDER BY event.comment_id, event.id DESC
            )
            SELECT string_agg(latest.comment_id::TEXT, ', ' ORDER BY latest.comment_id)
              INTO mismatched_ids
              FROM latest
              JOIN comments issue ON issue.id = latest.comment_id
             WHERE NOT (
                (
                    latest.action = 'resolved'
                    AND issue.resolved_at IS NOT DISTINCT FROM
                        latest.created_at
                    AND issue.resolved_by_id IS NOT DISTINCT FROM
                        latest.actor_id
                ) OR (
                    latest.action = 'reopened'
                    AND issue.resolved_at IS NULL
                    AND issue.resolved_by_id IS NULL
                )
             );

            IF mismatched_ids IS NOT NULL THEN
                RAISE EXCEPTION
                    'independent review resolution reconciliation failed comment_ids: %',
                    mismatched_ids;
            END IF;
        END;
        $$;
        """
    )


def _install_projection_triggers() -> None:
    op.execute(
        """
        CREATE TRIGGER comment_resolution_events_project_comment
        AFTER INSERT ON comment_resolution_events
        FOR EACH ROW EXECUTE FUNCTION project_comment_resolution_event();
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


def _install_review_issue_mutation_guard() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION guard_review_issue_mutation()
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
               OR NEW.author_id IS DISTINCT FROM OLD.author_id
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


def upgrade() -> None:
    """Repair activation triggers and reconcile any safe projection drift."""
    op.execute(
        """
        LOCK TABLE phenopackets, phenopacket_revisions, comments,
                   comment_resolution_events
        IN SHARE ROW EXCLUSIVE MODE;
        """
    )
    _drop_replaced_triggers()
    _install_projection_functions()
    _reconcile_latest_resolution_events()
    _install_projection_triggers()
    _install_review_issue_mutation_guard()


def downgrade() -> None:
    """Keep repaired e0-compatible invariants and audit storage in place."""

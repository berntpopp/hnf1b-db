"""Enforce revision-pointer state semantics on all phenopacket writes.

Revision ID: b8f422b00002
Revises: a8f422b00001
"""

from __future__ import annotations

from alembic import op

revision = "b8f422b00002"
down_revision = "a8f422b00001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Replace the deferred pointer trigger with state-aware validation."""
    op.execute("DROP TRIGGER phenopackets_revision_pointer_owner ON phenopackets")
    op.execute("DROP FUNCTION validate_phenopacket_revision_pointer()")
    op.execute(
        """
        CREATE FUNCTION validate_phenopacket_revision_pointer()
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
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER phenopackets_revision_pointer_owner
        AFTER INSERT OR UPDATE OF head_published_revision_id, editing_revision_id, state
        ON phenopackets DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_phenopacket_revision_pointer();
        """
    )


def downgrade() -> None:
    """Keep the stricter state invariant on downgrade of this correction."""
    raise RuntimeError("revision pointer state enforcement cannot be safely downgraded")

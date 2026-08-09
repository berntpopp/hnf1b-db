"""Validate deferred revision pointers against their final transaction state.

Revision ID: b9f422b00003
Revises: b8f422b00002
"""

from __future__ import annotations

from alembic import op

revision = "b9f422b00003"
down_revision = "b8f422b00002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Make deferred pointer validation observe the committed row image."""
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
    """Prevent unsafe removal of activated clinical audit protections."""
    raise RuntimeError("revision pointer state enforcement cannot be safely downgraded")

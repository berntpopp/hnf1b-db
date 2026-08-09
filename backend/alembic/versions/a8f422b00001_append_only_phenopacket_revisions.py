"""Make phenopacket revisions append-only and pointer-authoritative.

Revision ID: a8f422b00001
Revises: e7f710e344d2
Create Date: 2026-08-09
"""

import os

import sqlalchemy as sa

from alembic import op

revision = "a8f422b00001"
down_revision = "e7f710e344d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add revision lineage metadata and database-enforced immutability."""
    op.add_column(
        "phenopacket_revisions",
        sa.Column("parent_revision_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "phenopacket_revisions",
        sa.Column(
            "event_type",
            sa.Text(),
            nullable=False,
            server_default="snapshot",
        ),
    )
    for column in (
        "profile_schema_version",
        "projection_version",
        "ledger_hash",
        "projection_hash",
    ):
        op.add_column("phenopacket_revisions", sa.Column(column, sa.String(128)))
    op.create_foreign_key(
        "fk_phenopacket_revisions_parent",
        "phenopacket_revisions",
        "phenopacket_revisions",
        ["parent_revision_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # Backfill historical published records before removing the redundant
    # flag, then refuse to install the invariant triggers over corrupt data.
    op.execute(
        """
        UPDATE phenopackets packet
        SET head_published_revision_id = (
            SELECT revision.id
            FROM phenopacket_revisions revision
            WHERE revision.record_id = packet.id
              AND revision.is_head_published = TRUE
            ORDER BY revision.revision_number DESC
            LIMIT 1
        )
        WHERE packet.state = 'published'
          AND packet.head_published_revision_id IS NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM phenopackets packet
                LEFT JOIN phenopacket_revisions head
                  ON head.id = packet.head_published_revision_id
                WHERE packet.state = 'published'
                  AND (head.id IS NULL OR head.record_id <> packet.id
                       OR head.state <> 'published')
            ) THEN
                RAISE EXCEPTION 'published phenopacket has invalid head pointer';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM phenopackets packet
                JOIN phenopacket_revisions editing
                  ON editing.id = packet.editing_revision_id
                WHERE editing.record_id <> packet.id
                   OR editing.state NOT IN ('draft', 'in_review', 'changes_requested', 'approved')
            ) THEN
                RAISE EXCEPTION 'phenopacket has invalid editing revision pointer';
            END IF;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    # The pointer is the only head authority. Drop the redundant index and
    # column before installing the immutable-row trigger.
    op.drop_index("ux_head_published_per_record", table_name="phenopacket_revisions")
    op.drop_column("phenopacket_revisions", "is_head_published")

    op.execute(
        """
        CREATE FUNCTION reject_phenopacket_revision_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'phenopacket revisions are append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_phenopacket_revision_parent()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.parent_revision_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM phenopacket_revisions parent
                WHERE parent.id = NEW.parent_revision_id
                  AND parent.record_id = NEW.record_id
            ) THEN
                RAISE EXCEPTION 'parent revision must belong to its record';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER phenopacket_revisions_parent_owner
        BEFORE INSERT ON phenopacket_revisions
        FOR EACH ROW EXECUTE FUNCTION validate_phenopacket_revision_parent();
        """
    )
    op.execute(
        """
        CREATE TRIGGER phenopacket_revisions_immutable
        BEFORE UPDATE OR DELETE ON phenopacket_revisions
        FOR EACH ROW EXECUTE FUNCTION reject_phenopacket_revision_mutation();
        """
    )
    op.execute(
        """
        CREATE FUNCTION validate_phenopacket_revision_pointer()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.head_published_revision_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM phenopacket_revisions revision
                WHERE revision.id = NEW.head_published_revision_id
                  AND revision.record_id = NEW.id
            ) THEN
                RAISE EXCEPTION 'head_published_revision_id must belong to its record';
            END IF;
            IF NEW.editing_revision_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM phenopacket_revisions revision
                WHERE revision.id = NEW.editing_revision_id
                  AND revision.record_id = NEW.id
            ) THEN
                RAISE EXCEPTION 'editing_revision_id must belong to its record';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER phenopackets_revision_pointer_owner
        AFTER INSERT OR UPDATE OF head_published_revision_id, editing_revision_id
        ON phenopackets DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_phenopacket_revision_pointer();
        """
    )


def downgrade() -> None:
    """Restore schema shape only; immutable clinical history remains untouched."""
    if os.environ.get("ALLOW_PREACTIVATION_REVISION_DOWNGRADE") != "1":
        raise RuntimeError(
            "refusing revision downgrade after activation; use head-pointer rollback/PITR"
        )
    op.execute("DROP TRIGGER phenopackets_revision_pointer_owner ON phenopackets")
    op.execute("DROP FUNCTION validate_phenopacket_revision_pointer()")
    op.execute("DROP TRIGGER phenopacket_revisions_immutable ON phenopacket_revisions")
    op.execute("DROP FUNCTION reject_phenopacket_revision_mutation()")
    op.execute(
        "DROP TRIGGER phenopacket_revisions_parent_owner ON phenopacket_revisions"
    )
    op.execute("DROP FUNCTION validate_phenopacket_revision_parent()")
    op.add_column(
        "phenopacket_revisions",
        sa.Column(
            "is_head_published", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.execute(
        """
        UPDATE phenopacket_revisions revision
        SET is_head_published = TRUE
        FROM phenopackets packet
        WHERE packet.head_published_revision_id = revision.id
        """
    )
    op.create_index(
        "ux_head_published_per_record",
        "phenopacket_revisions",
        ["record_id"],
        unique=True,
        postgresql_where=sa.text("is_head_published = TRUE"),
    )
    op.drop_constraint(
        "fk_phenopacket_revisions_parent",
        "phenopacket_revisions",
        type_="foreignkey",
    )
    for column in (
        "projection_hash",
        "ledger_hash",
        "projection_version",
        "profile_schema_version",
        "event_type",
        "parent_revision_id",
    ):
        op.drop_column("phenopacket_revisions", column)

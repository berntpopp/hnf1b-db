"""Add phenopacket_revisions table + FKs from phenopackets pointers.

Revision ID: 20260412_0002
Revises: 20260412_0001
Create Date: 2026-04-12

Part of Wave 7 D.1. See docs/superpowers/specs/2026-04-12-wave-7-d1-state-machine-design.md §5.2.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260412_0002"
down_revision = "20260412_0001"
branch_labels = None
depends_on = None


STATES = ("draft", "in_review", "changes_requested", "approved", "published", "archived")


def upgrade() -> None:
    op.create_table(
        "phenopacket_revisions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("phenopackets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("content_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("change_patch", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column(
            "actor_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("from_state", sa.Text(), nullable=True),
        sa.Column("to_state", sa.Text(), nullable=False),
        sa.Column("is_head_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("record_id", "revision_number", name="uq_record_revision_number"),
        sa.CheckConstraint("state IN " + repr(STATES), name="ck_revisions_state"),
    )
    op.create_index(
        "ux_head_published_per_record", "phenopacket_revisions", ["record_id"],
        unique=True, postgresql_where=sa.text("is_head_published = TRUE"),
    )
    op.create_index(
        "ix_revisions_record_created", "phenopacket_revisions",
        ["record_id", sa.text("created_at DESC")],
    )
    op.create_foreign_key(
        "fk_phenopackets_editing_revision",
        "phenopackets", "phenopacket_revisions",
        ["editing_revision_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_phenopackets_head_published_revision",
        "phenopackets", "phenopacket_revisions",
        ["head_published_revision_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_phenopackets_head_published_revision", "phenopackets", type_="foreignkey",
    )
    op.drop_constraint(
        "fk_phenopackets_editing_revision", "phenopackets", type_="foreignkey",
    )
    op.drop_index("ix_revisions_record_created", table_name="phenopacket_revisions")
    op.drop_index("ux_head_published_per_record", table_name="phenopacket_revisions")
    op.drop_table("phenopacket_revisions")

"""Add state + editing + head-published + draft-owner columns to phenopackets.

Revision ID: 20260412_0001
Revises: c9a55365ed1f
Create Date: 2026-04-12

Part of Wave 7 D.1. See .planning/specs/2026-04-12-wave-7-d1-state-machine-design.md §5.1.
"""

import sqlalchemy as sa

from alembic import op

revision = "20260412_0001"
down_revision = "c9a55365ed1f"
branch_labels = None
depends_on = None


STATES = (
    "draft",
    "in_review",
    "changes_requested",
    "approved",
    "published",
    "archived",
)


def upgrade() -> None:
    op.add_column(
        "phenopackets",
        sa.Column("state", sa.Text(), nullable=False, server_default="draft"),
    )
    op.create_check_constraint(
        "ck_phenopackets_state",
        "phenopackets",
        sa.text("state IN " + repr(STATES)),
    )
    op.add_column(
        "phenopackets",
        sa.Column("editing_revision_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "phenopackets",
        sa.Column("head_published_revision_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "phenopackets",
        sa.Column("draft_owner_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_phenopackets_draft_owner",
        "phenopackets",
        "users",
        ["draft_owner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_phenopackets_state", "phenopackets", ["state"])
    op.create_index(
        "ix_phenopackets_draft_owner",
        "phenopackets",
        ["draft_owner_id"],
        postgresql_where=sa.text("draft_owner_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_phenopackets_draft_owner", table_name="phenopackets")
    op.drop_index("ix_phenopackets_state", table_name="phenopackets")
    op.drop_constraint(
        "fk_phenopackets_draft_owner", "phenopackets", type_="foreignkey"
    )
    op.drop_column("phenopackets", "draft_owner_id")
    op.drop_column("phenopackets", "head_published_revision_id")
    op.drop_column("phenopackets", "editing_revision_id")
    op.drop_constraint("ck_phenopackets_state", "phenopackets", type_="check")
    op.drop_column("phenopackets", "state")

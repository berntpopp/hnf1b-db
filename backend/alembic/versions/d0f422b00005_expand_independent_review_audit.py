"""Expand storage for independent review and versioned revision audit.

Revision ID: d0f422b00005
Revises: c0f422b00004
Create Date: 2026-08-14
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "d0f422b00005"
down_revision = "c0f422b00004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable audit storage without activating workflow constraints."""
    op.add_column(
        "phenopacket_revisions", sa.Column("actor_role", sa.Text(), nullable=True)
    )
    op.add_column(
        "phenopacket_revisions",
        sa.Column("decision_metadata", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "phenopacket_revisions",
        sa.Column("content_sha256", sa.Text(), nullable=True),
    )
    op.add_column(
        "phenopacket_revisions",
        sa.Column("ledger_version", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_phenopacket_revisions_actor_role"),
        "phenopacket_revisions",
        "actor_role IS NULL OR actor_role IN ('viewer', 'curator', 'admin')",
    )
    op.create_check_constraint(
        op.f("ck_phenopacket_revisions_content_sha256"),
        "phenopacket_revisions",
        "content_sha256 IS NULL OR content_sha256 ~ '^sha256:[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        op.f("ck_phenopacket_revisions_ledger_version"),
        "phenopacket_revisions",
        "ledger_version IS NULL OR ledger_version = 2",
    )
    op.create_check_constraint(
        op.f("ck_phenopacket_revisions_decision_metadata_ledger"),
        "phenopacket_revisions",
        "decision_metadata IS NULL OR "
        "(ledger_version IS NOT NULL AND ledger_version = 2)",
    )

    op.add_column(
        "comments", sa.Column("review_revision_id", sa.BigInteger(), nullable=True)
    )
    op.create_foreign_key(
        "fk_comments_review_revision",
        "comments",
        "phenopacket_revisions",
        ["review_revision_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "comment_resolution_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("comment_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("disposition", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_role", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "(action = 'reopened' AND disposition IS NULL) OR "
            "(action = 'resolved' AND disposition IS NOT NULL AND disposition IN "
            "('addressed','accepted_with_rationale','retracted','superseded'))",
            name=op.f("ck_comment_resolution_event_action_disposition"),
        ),
        sa.CheckConstraint(
            "char_length(btrim(rationale)) BETWEEN 1 AND 500",
            name=op.f("ck_comment_resolution_event_rationale"),
        ),
        sa.CheckConstraint(
            "actor_role IN ('curator', 'admin')",
            name=op.f("ck_comment_resolution_event_actor_role"),
        ),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_comments_live_unresolved_phenopacket_review_issues",
        "comments",
        ["record_id", "review_revision_id"],
        unique=False,
        postgresql_where=sa.text(
            "record_type = 'phenopacket' AND review_revision_id IS NOT NULL "
            "AND resolved_at IS NULL AND deleted_at IS NULL"
        ),
    )


def downgrade() -> None:
    """Remove the unused nullable expansion without touching revision history."""
    op.drop_index(
        "ix_comments_live_unresolved_phenopacket_review_issues",
        table_name="comments",
    )
    op.drop_table("comment_resolution_events")
    op.drop_constraint("fk_comments_review_revision", "comments", type_="foreignkey")
    op.drop_column("comments", "review_revision_id")

    for constraint_name in (
        "ck_phenopacket_revisions_decision_metadata_ledger",
        "ck_phenopacket_revisions_ledger_version",
        "ck_phenopacket_revisions_content_sha256",
        "ck_phenopacket_revisions_actor_role",
    ):
        op.drop_constraint(
            op.f(constraint_name), "phenopacket_revisions", type_="check"
        )
    for column_name in (
        "ledger_version",
        "content_sha256",
        "decision_metadata",
        "actor_role",
    ):
        op.drop_column("phenopacket_revisions", column_name)

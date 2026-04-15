"""add refresh session persistence

Revision ID: 20260415_0005
Revises: 483990d7e28f
Create Date: 2026-04-15
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260415_0005"
down_revision: Union[str, Sequence[str], None] = "483990d7e28f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add refresh-session persistence and per-user session versioning."""
    op.add_column(
        "users",
        sa.Column(
            "session_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.create_table(
        "refresh_sessions",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_jti", sa.String(length=64), nullable=False),
        sa.Column("token_sha256", sa.String(length=64), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_from_jti", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_jti"),
        sa.UniqueConstraint("token_sha256"),
    )
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])
    op.create_index(
        "ix_refresh_sessions_rotated_from_jti",
        "refresh_sessions",
        ["rotated_from_jti"],
    )


def downgrade() -> None:
    """Remove refresh-session persistence and per-user session versioning."""
    op.drop_index("ix_refresh_sessions_rotated_from_jti", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_user_id", table_name="refresh_sessions")
    op.drop_table("refresh_sessions")
    op.drop_column("users", "session_version")

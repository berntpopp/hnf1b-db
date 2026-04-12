"""add credential_tokens table

Revision ID: 32105e02cd4b
Revises: 7ddc07dd9e1c
Create Date: 2026-04-12 11:20:48.861064

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "32105e02cd4b"
down_revision: Union[str, Sequence[str], None] = "7ddc07dd9e1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create credential_tokens table for identity lifecycle flows."""
    op.create_table(
        "credential_tokens",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("purpose", sa.String(length=10), nullable=False),
        sa.Column("token_sha256", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('reset', 'invite', 'verify')",
            name="ck_credential_tokens_purpose",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_credential_tokens_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credential_tokens")),
    )
    op.create_index(
        "ix_credential_tokens_email_purpose",
        "credential_tokens",
        ["email", "purpose"],
        unique=False,
    )
    op.create_index(
        op.f("ix_credential_tokens_id"),
        "credential_tokens",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_credential_tokens_token_sha256"),
        "credential_tokens",
        ["token_sha256"],
        unique=True,
    )


def downgrade() -> None:
    """Drop credential_tokens table."""
    op.drop_index(
        op.f("ix_credential_tokens_token_sha256"),
        table_name="credential_tokens",
    )
    op.drop_index(
        op.f("ix_credential_tokens_id"),
        table_name="credential_tokens",
    )
    op.drop_index(
        "ix_credential_tokens_email_purpose",
        table_name="credential_tokens",
    )
    op.drop_table("credential_tokens")

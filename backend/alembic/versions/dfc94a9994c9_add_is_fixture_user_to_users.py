"""add is_fixture_user to users

Revision ID: dfc94a9994c9
Revises: a7f1c2d9e5b3
Create Date: 2026-04-11 15:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dfc94a9994c9"
down_revision: Union[str, Sequence[str], None] = "a7f1c2d9e5b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_fixture_user column to users table.

    Non-nullable with server_default=FALSE so existing rows auto-migrate
    without violating the NOT NULL constraint.
    """
    op.add_column(
        "users",
        sa.Column(
            "is_fixture_user",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="True only for seeded dev-mode fixture users; must be FALSE in prod",
        ),
    )


def downgrade() -> None:
    """Drop is_fixture_user column from users table."""
    op.drop_column("users", "is_fixture_user")

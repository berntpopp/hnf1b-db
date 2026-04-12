"""fix credential_tokens purpose check constraint name

Revision ID: c9a55365ed1f
Revises: 32105e02cd4b
Create Date: 2026-04-12 13:22:27.216048

Copilot PR #235 review: the CredentialToken model uses
``name="purpose"`` which the MetaData naming convention
(``ck_%(table_name)s_%(constraint_name)s``) expands to
``ck_credential_tokens_purpose``. The initial migration used the
expanded name directly, which the convention then double-prefixed to
``ck_credential_tokens_ck_credential_tokens_purpose`` in Postgres.

This migration renames the live constraint to match what the model
produces, so Alembic autogenerate no longer shows a spurious diff.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c9a55365ed1f"
down_revision: Union[str, Sequence[str], None] = "32105e02cd4b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename check constraint to match model + convention output."""
    op.execute(
        "ALTER TABLE credential_tokens "
        "RENAME CONSTRAINT ck_credential_tokens_ck_credential_tokens_purpose "
        "TO ck_credential_tokens_purpose"
    )


def downgrade() -> None:
    """Restore the pre-fix constraint name."""
    op.execute(
        "ALTER TABLE credential_tokens "
        "RENAME CONSTRAINT ck_credential_tokens_purpose "
        "TO ck_credential_tokens_ck_credential_tokens_purpose"
    )

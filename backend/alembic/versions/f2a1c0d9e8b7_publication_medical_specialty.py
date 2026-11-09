"""Add curated medical_specialty to publication_metadata (issue #11).

Revision ID: f2a1c0d9e8b7
Revises: f1f422b00008
Create Date: 2026-11-09
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

revision = "f2a1c0d9e8b7"
down_revision = "f1f422b00008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add a nullable ordered text[] of curated specialties."""
    op.add_column(
        "publication_metadata",
        sa.Column("medical_specialty", ARRAY(sa.Text), nullable=True),
    )


def downgrade() -> None:
    """Drop the curated specialty column."""
    op.drop_column("publication_metadata", "medical_specialty")

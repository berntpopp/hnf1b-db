"""fix_feature_disease_aggregation_indexes

Revision ID: 48c7a668d614
Revises: 44ccb14dc32b
Create Date: 2025-12-09

Fixes the unique indexes on mv_feature_aggregation and mv_disease_aggregation
to use composite keys (id, label) instead of just id.

This is needed because the same HPO/disease ID can appear with different labels
in the source data, causing unique constraint violations on refresh.

Related to issues #160, #162, #165.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "48c7a668d614"
down_revision: Union[str, Sequence[str], None] = "44ccb14dc32b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update indexes to composite keys including label."""
    # Drop old single-column unique indexes
    op.execute(
        "DROP INDEX IF EXISTS ix_mv_feature_aggregation_hpo_id"
    )
    op.execute(
        "DROP INDEX IF EXISTS ix_mv_disease_aggregation_disease_id"
    )

    # Create new composite unique indexes (id + label)
    # This handles cases where same HPO ID has different labels
    # Use IF NOT EXISTS for idempotency (fresh DBs already have these from earlier migration)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_mv_feature_aggregation_hpo_id_label
        ON mv_feature_aggregation (hpo_id, label)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_mv_disease_aggregation_disease_id_label
        ON mv_disease_aggregation (disease_id, label)
        """
    )


def downgrade() -> None:
    """Restore original single-column unique indexes."""
    # Drop composite indexes
    op.execute(
        "DROP INDEX IF EXISTS ix_mv_feature_aggregation_hpo_id_label"
    )
    op.execute(
        "DROP INDEX IF EXISTS ix_mv_disease_aggregation_disease_id_label"
    )

    # Restore single-column indexes
    # Note: This may fail if there are duplicate IDs with different labels
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_feature_aggregation_hpo_id
        ON mv_feature_aggregation (hpo_id)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ix_mv_disease_aggregation_disease_id
        ON mv_disease_aggregation (disease_id)
        """
    )

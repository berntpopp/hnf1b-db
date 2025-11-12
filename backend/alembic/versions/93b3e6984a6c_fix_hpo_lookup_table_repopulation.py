"""fix_hpo_lookup_table_repopulation

Revision ID: 93b3e6984a6c
Revises: 8baf0de6a441
Create Date: 2025-11-12 21:17:05.382884

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93b3e6984a6c'
down_revision: Union[str, Sequence[str], None] = '8baf0de6a441'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fix HPO lookup table by repopulating with correct camelCase keys.

    The previous migration used snake_case 'phenotypic_features' instead of
    camelCase 'phenotypicFeatures', resulting in an empty lookup table.
    """
    # 1. Clear existing (incorrect) data
    op.execute("TRUNCATE TABLE hpo_terms_lookup")

    # 2. Repopulate with correct camelCase keys from Phenopackets v2 schema
    op.execute("""
        INSERT INTO hpo_terms_lookup (hpo_id, label, phenopacket_count)
        SELECT DISTINCT
            pf.value->'type'->>'id' AS hpo_id,
            pf.value->'type'->>'label' AS label,
            COUNT(DISTINCT p.id) AS phenopacket_count
        FROM phenopackets p,
             jsonb_array_elements(p.phenopacket->'phenotypicFeatures') AS pf
        WHERE pf.value->'type'->>'id' IS NOT NULL
          AND pf.value->'type'->>'id' LIKE 'HP:%'
        GROUP BY hpo_id, label
        ORDER BY phenopacket_count DESC
    """)


def downgrade() -> None:
    """Restore previous (incorrect) state with snake_case keys."""
    # Clear table
    op.execute("TRUNCATE TABLE hpo_terms_lookup")

    # Restore with incorrect snake_case keys (matches original migration)
    op.execute("""
        INSERT INTO hpo_terms_lookup (hpo_id, label, phenopacket_count)
        SELECT DISTINCT
            pf.value->'type'->>'id' AS hpo_id,
            pf.value->'type'->>'label' AS label,
            COUNT(DISTINCT p.id) AS phenopacket_count
        FROM phenopackets p,
             jsonb_array_elements(p.phenopacket->'phenotypic_features') AS pf
        WHERE pf.value->'type'->>'id' IS NOT NULL
          AND pf.value->'type'->>'id' LIKE 'HP:%'
        GROUP BY hpo_id, label
        ORDER BY phenopacket_count DESC
    """)

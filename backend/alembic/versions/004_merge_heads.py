"""Merge migration heads

Revision ID: 004_merge_heads
Revises: 003_variant_search_indexes, 533c020aa76d
Create Date: 2025-11-03

Merges two parallel migration branches that both originated from 002_jsonb_indexes:
- Branch 1: 002 → 8d988c04336a → 533c020aa76d (publication metadata)
- Branch 2: 002 → 003_variant_search_indexes (variant search)

This is a no-op migration that simply merges the two heads.
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "004_merge_heads"
down_revision: Union[str, Sequence[str], None] = ("003_variant_search_indexes", "533c020aa76d")


def upgrade() -> None:
    """No-op merge migration."""
    pass


def downgrade() -> None:
    """No-op merge migration."""
    pass

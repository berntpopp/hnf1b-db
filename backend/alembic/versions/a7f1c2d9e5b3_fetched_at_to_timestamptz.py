"""Convert ``fetched_at`` columns to ``TIMESTAMPTZ``.

During Wave 4 follow-up cleanup on PR #232 we kept hitting a recurring
workaround in ``backend/app/variants/service/cache_ops.py`` and the
publication list-route tests::

    if fetched_at.tzinfo is not None:
        fetched_at = fetched_at.replace(tzinfo=None)

The workaround was there because two cache tables stored ``fetched_at``
as ``TIMESTAMP WITHOUT TIME ZONE`` while the Python side works in UTC
with tz-aware datetimes. Converting the columns to ``TIMESTAMPTZ``
(preserving the stored values as UTC) lets us drop the ``.replace``
calls and keeps the Python layer coherent.

Both columns are small caches (tens of thousands of rows) so the
``ALTER COLUMN ... USING`` is safe and fast.

Revision ID: a7f1c2d9e5b3
Revises: 5c8d7e9f0a1b
Create Date: 2026-04-11
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7f1c2d9e5b3"
down_revision: Union[str, Sequence[str], None] = "5c8d7e9f0a1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert the two cache ``fetched_at`` columns to TIMESTAMPTZ."""
    # publication_metadata: stored values are implicitly UTC (the app
    # writes ``datetime.now(timezone.utc)`` after calling ``.replace``
    # to strip tzinfo). Reinterpret them as UTC during the conversion.
    op.execute(
        """
        ALTER TABLE publication_metadata
            ALTER COLUMN fetched_at TYPE TIMESTAMPTZ
            USING fetched_at AT TIME ZONE 'UTC'
        """
    )

    # variant_annotations: same rationale.
    op.execute(
        """
        ALTER TABLE variant_annotations
            ALTER COLUMN fetched_at TYPE TIMESTAMPTZ
            USING fetched_at AT TIME ZONE 'UTC'
        """
    )


def downgrade() -> None:
    """Revert the two cache ``fetched_at`` columns to TIMESTAMP.

    Reverse the ``AT TIME ZONE`` coercion so local (UTC) wall-clock
    values land back in the timestamp-without-tz column.
    """
    op.execute(
        """
        ALTER TABLE variant_annotations
            ALTER COLUMN fetched_at TYPE TIMESTAMP
            USING fetched_at AT TIME ZONE 'UTC'
        """
    )
    op.execute(
        """
        ALTER TABLE publication_metadata
            ALTER COLUMN fetched_at TYPE TIMESTAMP
            USING fetched_at AT TIME ZONE 'UTC'
        """
    )

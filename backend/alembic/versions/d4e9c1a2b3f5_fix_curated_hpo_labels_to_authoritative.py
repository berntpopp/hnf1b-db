"""fix_curated_hpo_labels_to_authoritative

Revision ID: d4e9c1a2b3f5
Revises: c8d2a3f1e0b5
Create Date: 2026-05-29 00:00:00.000000

Corrects five curated HPO labels in ``hpo_terms_lookup`` that were hand-typed in
migration ``0bd1567a483c`` and never validated against the ontology. Four had
drifted to older/looser names; HP:0033133 was recorded with the clinically
OPPOSITE finding ("Renal cortical hyperechogenicity" / "Increased echogenecity"
instead of "Renal cortical hypoechogeneity"), which could reach cited output.

Values below are the authoritative HPO term names (HPO API at ontology.jax.org,
cross-checked against EBI OLS4) as of 2026-05-29. This migration only rewrites
data — no schema change. A network-gated guard test
(``tests/test_hpo_label_integrity.py``, marker ``network``) re-validates every
curated label against the live ontology so drift can no longer slip in silently.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e9c1a2b3f5"
down_revision: Union[str, Sequence[str], None] = "c8d2a3f1e0b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (hpo_id, authoritative label) — the corrected value each row must hold.
_LABEL_FIXES: list[tuple[str, str]] = [
    ("HP:0000708", "Atypical behavior"),
    ("HP:0002910", "Elevated circulating hepatic transaminase concentration"),
    ("HP:0012443", "Abnormal brain morphology"),
    ("HP:0012622", "Chronic kidney disease"),
    ("HP:0033133", "Renal cortical hypoechogeneity"),
]

# The pre-fix labels, used to restore state on downgrade.
_LABEL_ROLLBACK: list[tuple[str, str]] = [
    ("HP:0000708", "Behavioral abnormality"),
    ("HP:0002910", "Elevated hepatic transaminase"),
    ("HP:0012443", "Abnormality of brain morphology"),
    ("HP:0012622", "chronic kidney disease, not specified"),
    ("HP:0033133", "Renal cortical hyperechogenicity"),
]

_SET_LABEL = sa.text(
    "UPDATE hpo_terms_lookup SET label = :label WHERE hpo_id = :hpo_id"
)


def _apply_labels(pairs: list[tuple[str, str]]) -> None:
    """Set ``label`` for each (hpo_id, label) pair via a parameterized UPDATE."""
    bind = op.get_bind()
    for hpo_id, label in pairs:
        bind.execute(_SET_LABEL, {"label": label, "hpo_id": hpo_id})


def upgrade() -> None:
    """Correct the five drifted/incorrect curated HPO labels.

    Rewrites the five labels to HPO-authoritative values, and additionally
    corrects HP:0033133's category, description, and synonyms (they encoded the
    opposite, "increased-echogenicity" meaning).
    """
    _apply_labels(_LABEL_FIXES)

    # HP:0033133's category/description/synonyms described the opposite finding.
    op.get_bind().execute(
        sa.text(
            """
            UPDATE hpo_terms_lookup
            SET category = 'Hypoechogenicity',
                description = 'Decreased echogenicity of the kidney cortex.',
                synonyms = 'Hypoechogenic renal cortex'
            WHERE hpo_id = 'HP:0033133'
            """
        )
    )


def downgrade() -> None:
    """Restore the pre-fix (incorrect) labels and HP:0033133 metadata."""
    _apply_labels(_LABEL_ROLLBACK)

    op.get_bind().execute(
        sa.text(
            """
            UPDATE hpo_terms_lookup
            SET category = 'Hyperechogenicity',
                description = 'Increased echogenecity of the kidney cortex.',
                synonyms = 'No synonyms found for this term.'
            WHERE hpo_id = 'HP:0033133'
            """
        )
    )

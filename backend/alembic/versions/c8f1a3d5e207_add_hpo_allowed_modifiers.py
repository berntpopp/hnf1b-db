"""Add per-term laterality policy to hpo_terms_lookup.

Which HPO modifiers a term admits is reference data rather than a constant,
because of one asymmetry: HP:0000122 Unilateral renal agenesis already asserts
unilaterality, so it must reject Bilateral as contradictory. Unilateral is
redundant there but permitted -- see the amendment note in the task body.

Revision ID: c8f1a3d5e207
Revises: a1c4e7f20b93
"""

from alembic import op

revision = "c8f1a3d5e207"
down_revision = "a1c4e7f20b93"
branch_labels = None
depends_on = None

BILATERAL = "HP:0012832"
UNILATERAL = "HP:0012833"
LEFT = "HP:0012835"
RIGHT = "HP:0012834"

FULL_LATERALITY = (BILATERAL, UNILATERAL, LEFT, RIGHT)
# HP:0000122 already asserts unilaterality, so Bilateral contradicts the term.
# Unilateral is redundant but permitted: 20 source rows state "unilateral
# unspecified" on it, and rejecting them would discard a curator's explicit
# annotation (defect report §3). See the amendment note at the top of Task 7.
NOT_BILATERAL = (UNILATERAL, LEFT, RIGHT)

POLICY = {
    "HP:0000107": FULL_LATERALITY,  # Renal cyst
    "HP:0000003": FULL_LATERALITY,  # Multicystic kidney dysplasia
    "HP:0000089": FULL_LATERALITY,  # Renal hypoplasia
    "HP:0033132": FULL_LATERALITY,  # Renal cortical hyperechogenicity
    "HP:0000079": FULL_LATERALITY,  # Abnormality of the urinary system
    "HP:0000122": NOT_BILATERAL,  # Unilateral renal agenesis
}

# These ID literals are deliberately redeclared inline rather than imported from
# migration/phenopackets/laterality.py. A migration must be a frozen snapshot:
# importing a mutable application constant would mean that editing that module
# later silently changes what this revision does on a fresh database.


def upgrade() -> None:
    op.execute(
        "ALTER TABLE hpo_terms_lookup "
        "ADD COLUMN allowed_modifiers text[] NOT NULL DEFAULT '{}'"
    )
    for hpo_id, modifiers in POLICY.items():
        literal = ",".join(f'"{m}"' for m in modifiers)
        op.execute(
            f"UPDATE hpo_terms_lookup SET allowed_modifiers = '{{{literal}}}' "  # noqa: S608
            f"WHERE hpo_id = '{hpo_id}'"
        )


def downgrade() -> None:
    op.execute("ALTER TABLE hpo_terms_lookup DROP COLUMN IF EXISTS allowed_modifiers")

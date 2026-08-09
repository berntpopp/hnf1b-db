"""Add curation controlled vocabularies.

Reference tables for the curation storage contract: cohort, detection method,
segregation and family history. Follows the sex_values pattern from
88b3a0c19a89_add_phenopacket_controlled_vocabularies -- raw SQL, no ORM model,
registered in alembic/env.py::include_object.

Values and counts are taken from HNF1B_DataCuration.xlsx (939 rows). Counts are
recorded in the description column for curator context, not enforced.

Revision ID: a1c4e7f20b93
Revises: 18cfc57307f6
"""

from alembic import op

revision = "a1c4e7f20b93"
down_revision = "18cfc57307f6"
branch_labels = None
depends_on = None

_TABLES = {
    "cohort_values": [
        ("born", "Born", "Live-born individual", 1),
        (
            "fetus",
            "Fetus",
            "Prenatal case; pregnancy termination or fetal assessment",
            2,
        ),
    ],
    "detection_method_values": [
        ("sanger", "Sanger sequencing", None, 1),
        ("ngs", "Next-generation sequencing", None, 2),
        ("cma", "Chromosomal microarray", None, 3),
        ("mlpa", "MLPA", "Multiplex ligation-dependent probe amplification", 4),
        ("qpcr", "qPCR", "Quantitative PCR", 5),
        ("fish", "FISH", "Fluorescence in situ hybridisation", 6),
        ("other", "Other", "Method stated but not one of the above", 7),
        ("not_reported", "Not reported", "Source is silent on detection method", 8),
    ],
    "segregation_values": [
        ("de_novo", "De novo", "Not present in either parent", 1),
        ("inherited_maternal", "Inherited, maternal", None, 2),
        ("inherited_paternal", "Inherited, paternal", None, 3),
        ("inherited_unspecified", "Inherited, parent unspecified", None, 4),
        ("not_reported", "Not reported", "Source is silent on segregation", 5),
    ],
    "family_history_values": [
        ("positive", "Positive", "Relatives reported with a related phenotype", 1),
        ("negative", "Negative", "Family history explicitly reported as negative", 2),
        ("not_reported", "Not reported", "Source is silent on family history", 3),
    ],
}


def _lit(value: str | None) -> str:
    """Render a SQL string literal, or NULL."""
    if value is None:
        return "NULL"
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def upgrade() -> None:
    for table, rows in _TABLES.items():
        op.execute(
            f"""
            CREATE TABLE {table} (
                value       text PRIMARY KEY,
                label       text NOT NULL,
                description text,
                sort_order  integer NOT NULL
            )
            """  # noqa: S608
        )
        for value, label, description, sort_order in rows:
            op.execute(
                f"""
                INSERT INTO {table} (value, label, description, sort_order)
                VALUES ({_lit(value)}, {_lit(label)}, {_lit(description)}, {sort_order})
                """  # noqa: S608
            )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")  # noqa: S608

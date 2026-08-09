"""Add curation console controlled vocabularies.

Reference tables for the Phase 3 curation console storage contract:
publication type and classification system. Follows the cohort_values pattern
from a1c4e7f20b93_add_curation_vocabularies -- raw SQL, no ORM model,
registered in alembic/env.py::include_object.

Values are taken from HNF1B_DataCuration.xlsx (939 rows), columns
PublicationType (6 distinct stripped values) and system_classification
(2 distinct values). Read directly from the sheet rather than assumed --
system_classification's two values are "ACMG sequence variants
interpretation guidelines" and "ClinGen CNV Interpretation Guidelines" (not
a gene-specific ClinGen HNF1B document), so the second value token is
clingen_cnv, not clingen_hnf1b.

Revision ID: e7f710e344d2
Revises: c8f1a3d5e207
"""

from alembic import op

revision = "e7f710e344d2"
down_revision = "c8f1a3d5e207"
branch_labels = None
depends_on = None

_TABLES = {
    "publication_type_values": [
        ("case_report", "Case report", "Single-patient report", 1),
        ("case_series", "Case series", "Report of multiple patients", 2),
        (
            "review_and_cases",
            "Review and cases",
            "Literature review combined with new case reports",
            3,
        ),
        ("review", "Review", "Literature review with no new cases", 4),
        (
            "research",
            "Research",
            "Original research study (cohort, functional, etc.)",
            5,
        ),
        (
            "screening_multiple",
            "Screening / multiple",
            "Screening study or other multiple-case source",
            6,
        ),
    ],
    "classification_system_values": [
        (
            "acmg",
            "ACMG",
            "ACMG sequence variants interpretation guidelines",
            1,
        ),
        (
            "clingen_cnv",
            "ClinGen CNV",
            "ClinGen CNV Interpretation Guidelines",
            2,
        ),
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

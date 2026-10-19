"""Public query builders must read immutable published-head JSON."""

from pathlib import Path

from app.phenopackets.clinical_queries import ClinicalQueries
from app.phenopackets.routers.comparisons.query import (
    build_phenotype_distribution_query,
)

BACKEND = Path(__file__).resolve().parents[1]


def test_comparison_distribution_uses_head_revision_content():
    """Variant and phenotype comparison JSON comes from the same head alias."""
    sql = build_phenotype_distribution_query("TRUE", "FALSE")
    assert "phenopacket_revisions r ON r.id = p.head_published_revision_id" in sql
    assert "r.content_jsonb->'interpretations'" in sql
    assert "r.content_jsonb->'phenotypicFeatures'" in sql
    assert "p.phenopacket->" not in sql


def test_clinical_queries_are_published_head_only():
    """Clinical discovery excludes draft, archive, and deleted working rows."""
    sql = str(ClinicalQueries.get_phenotype_features_query(["HP:0000107"]))
    assert "phenopackets.state = :state_1" in sql
    assert "phenopackets.deleted_at IS NULL" in sql
    assert "phenopackets.head_published_revision_id IS NOT NULL" in sql


def test_public_sex_filters_facets_related_and_sorts_read_head_content():
    """Public discovery must not use generated columns from a divergent draft."""
    search = (BACKEND / "app/phenopackets/routers/search.py").read_text()
    related = (BACKEND / "app/phenopackets/routers/crud_related.py").read_text()
    crud = (BACKEND / "app/phenopackets/routers/crud.py").read_text()

    assert '"p.subject_sex = :sex"' not in search
    assert "SELECT p.subject_sex AS value" not in search
    assert '" AND p.subject_sex = :sex"' not in related
    assert "parse_sort_parameter(sort, content=public_json_column)" in crud


def test_disease_cases_query_uses_parameterized_jsonb_build_object():
    """Disease case queries must parameterize terms and labels via jsonb_build_object."""
    sql = str(ClinicalQueries.get_disease_cases(["MONDO:0005147"], ["diabetes"]))
    assert "jsonb_build_object" in sql
    assert "MONDO:0005147" not in sql
    assert "diabetes" not in sql


def test_measurement_cases_query_uses_parameterized_jsonb_build_object():
    """Measurement queries must parameterize LOINC codes and interpretations."""
    sql = str(ClinicalQueries.get_measurement_cases(["1234-5"], "HP:0000107"))
    assert "jsonb_build_object" in sql
    assert "1234-5" not in sql
    assert "HP:0000107" not in sql


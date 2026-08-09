"""Permutation and stale-resolution properties of the pure projector."""

import itertools

import pytest

from app.phenopackets.curation.models import AssessmentStatus, ProjectionResolution
from app.phenopackets.curation.projection import (
    StaleResolutionError,
    project_individual,
)
from tests.curation.test_projection import observation


def test_every_input_order_has_the_same_hash_projection_and_conflict_set():
    """Volatile source metadata and input order are excluded from projection semantics."""
    reports = [
        observation("report-a", AssessmentStatus.PRESENT),
        observation("report-b", AssessmentStatus.PRESENT),
        observation("report-c", AssessmentStatus.NOT_REPORTED),
    ]
    results = [
        project_individual(list(order), [], algorithm_version="1.0")
        for order in itertools.permutations(reports)
    ]

    assert {result.observations_digest for result in results} == {
        results[0].observations_digest
    }
    assert {result.output_digest for result in results} == {results[0].output_digest}
    assert {str(result.phenopacket) for result in results} == {
        str(results[0].phenopacket)
    }
    assert {result.blocking_conflicts for result in results} == {
        results[0].blocking_conflicts
    }


def test_stale_resolution_is_rejected_when_its_candidate_set_changes():
    """A curator decision must not silently apply to a changed source ledger."""
    reports = [
        observation("report-a", AssessmentStatus.PRESENT),
        observation("report-b", AssessmentStatus.EXCLUDED),
    ]
    stale = ProjectionResolution(
        resolution_id="resolution-1",
        conflict_key="phenotype:HP:0000107:polarity",
        candidate_set_digest="sha256:outdated",
        strategy="select_observations",
        reason="Later imaging is better evidence.",
        resolved_by_user_id=1,
        resolved_at="2026-08-09T00:00:00Z",
    )

    with pytest.raises(StaleResolutionError):
        project_individual(reports, [stale], algorithm_version="1.0")

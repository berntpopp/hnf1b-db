"""Official Phenopackets protobuf parsing of generated GA4GH-only projections."""

from google.protobuf.json_format import ParseDict
from phenopackets import Phenopacket

from app.phenopackets.curation.models import AssessmentStatus
from app.phenopackets.curation.projection import project_individual
from tests.curation.test_projection import observation


def test_projection_is_accepted_by_the_pinned_official_phenopackets_parser():
    """Local JSON Schema is not an official GA4GH conformance substitute."""
    result = project_individual(
        [observation("report-a", AssessmentStatus.PRESENT)], [], algorithm_version="1.0"
    )

    parsed = ParseDict(result.phenopacket, Phenopacket())
    assert parsed.subject.id == "317"
    assert parsed.phenotypic_features[0].type.id == "HP:0000107"

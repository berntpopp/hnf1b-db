"""Public representation must be recursive default-deny and head-authoritative."""

import pytest

from app.phenopackets.privacy import PublicRepresentationError, redact_public_document


def test_public_redaction_removes_nested_private_curation_and_reviewer_values():
    """No private curation or reviewer/source identifiers survive recursive shaping."""
    document = {
        "id": "pp-1",
        "subject": {"id": "1", "sex": "FEMALE", "email": "patient@example.org"},
        "metaData": {"created": "2026-08-09T00:00:00Z", "createdBy": "system"},
        "hnf1bCuration": {"reviewer": "curator@example.org", "comments": "secret"},
        "interpretations": [
            {
                "diagnosis": {
                    "genomicInterpretations": [],
                    "sourceReportId": "report-17",
                }
            }
        ],
    }

    public = redact_public_document(document)

    assert "hnf1bCuration" not in public
    assert "email" not in public["subject"]
    assert "sourceReportId" not in public["interpretations"][0]["diagnosis"]


def test_public_redaction_rejects_unknown_top_level_keys():
    """The public serializer fails closed instead of forwarding novel fields."""
    with pytest.raises(PublicRepresentationError):
        redact_public_document({"id": "pp-1", "unrecognizedPublicField": {}})

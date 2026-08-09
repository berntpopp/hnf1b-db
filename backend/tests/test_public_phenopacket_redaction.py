"""Public representation must be recursive default-deny and head-authoritative."""

import pytest

from app.phenopackets.privacy import (
    PublicRepresentationError,
    redact_public_document,
    sanitize_profile_document,
)
from app.phenopackets.services.representation_service import ga4gh_representation


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


def test_public_redaction_drops_unknown_top_level_keys():
    """The public serializer fails closed instead of forwarding novel fields."""
    assert redact_public_document({"id": "pp-1", "unrecognizedPublicField": {}}) == {
        "id": "pp-1"
    }


def test_ga4gh_representation_preserves_official_resource_source_fields():
    """A valid GA4GH resource ``url``/``iriPrefix`` is not mistaken for source PII."""
    document = {
        "id": "pp-1",
        "subject": {"id": "1"},
        "metaData": {
            "created": "2026-08-09T00:00:00Z",
            "createdBy": "system",
            "resources": [
                {
                    "id": "hp",
                    "name": "HPO",
                    "namespacePrefix": "HP",
                    "url": "https://hpo.jax.org",
                    "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                }
            ],
        },
    }

    rendered = ga4gh_representation(document)

    assert rendered["metaData"]["resources"][0]["url"] == "https://hpo.jax.org"


def test_profile_rejects_nested_credential_and_raw_source_values():
    """Curator profile export rejects restricted nested provenance, not only email."""
    with pytest.raises(PublicRepresentationError, match="restricted"):
        sanitize_profile_document(
            {"hnf1bCuration": {"observationsById": {"x": {"raw": "secret"}}}}
        )


def test_profile_permits_sanitized_curation_but_rejects_token_variants():
    """Local curation is profile-safe after sanitization; credentials never are."""
    document = {"hnf1bCuration": {"projection": {"algorithmVersion": "1"}}}
    assert sanitize_profile_document(document) == document
    with pytest.raises(PublicRepresentationError, match="restricted"):
        sanitize_profile_document({"hnf1bCuration": {"apiKey": "secret"}})


def test_ga4gh_representation_preserves_medical_actions():
    """Parser-valid GA4GH fields are retained rather than allowlist-truncated."""
    document = {
        "id": "pp-1",
        "subject": {"id": "1"},
        "medicalActions": [{"procedure": {"code": {"id": "NCIT:C25218"}}}],
        "metaData": {"created": "2026-08-09T00:00:00Z", "createdBy": "system"},
    }
    assert "medicalActions" in ga4gh_representation(document)

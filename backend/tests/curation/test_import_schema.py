"""Operational import models preserve provenance without clinical source rows."""

import pytest

from app.phenopackets.curation.import_models import (
    ImportPayloadError,
    ImportRunStatus,
    sanitize_operational_payload,
)


def test_import_run_payload_retains_count_only_operational_metadata():
    payload = sanitize_operational_payload(
        {"built": 939, "stored": 864, "conflicts": 18, "manifest": "sha256:abc"}
    )
    assert payload == {
        "built": 939,
        "stored": 864,
        "conflicts": 18,
        "manifest": "sha256:abc",
    }
    assert ImportRunStatus.APPLIED.value == "applied"


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "reviewer@example.test"},
        {"raw_row": {"individual_id": "317"}},
        {"password": "never-store"},
        {"comment": "linkable source text"},
    ],
)
def test_import_run_payload_rejects_clinical_or_secret_content(payload):
    with pytest.raises(ImportPayloadError):
        sanitize_operational_payload(payload)

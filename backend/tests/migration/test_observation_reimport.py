"""Reimport policy tests for no-op and curator-protected source changes."""

import pytest

from migration.reimport_merge import (
    ReimportConflict,
    ReimportDisposition,
    classify_reimport,
)


def test_identical_row_hmac_is_a_noop_without_a_clinical_revision():
    decision = classify_reimport(
        prior_row_hmac="hmac-sha256:old",
        incoming_row_hmac="hmac-sha256:old",
        has_active_draft=False,
        has_correction=False,
        has_resolution_dependency=False,
    )
    assert decision is ReimportDisposition.NOOP


@pytest.mark.parametrize(
    "protection", ["has_active_draft", "has_correction", "has_resolution_dependency"]
)
def test_changed_source_row_cannot_overwrite_curator_owned_work(protection):
    arguments = {
        "prior_row_hmac": "hmac-sha256:old",
        "incoming_row_hmac": "hmac-sha256:new",
        "has_active_draft": False,
        "has_correction": False,
        "has_resolution_dependency": False,
    }
    arguments[protection] = True
    with pytest.raises(ReimportConflict):
        classify_reimport(**arguments)

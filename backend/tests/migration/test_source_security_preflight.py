"""Security boundary tests for source import preflight."""

import pytest

from migration.source_manifest import SourceManifestError, validate_sheet_headers


@pytest.mark.parametrize(
    "header",
    ["password", "Passwd", "api_secret", "access_token", "credential"],
)
def test_preflight_rejects_forbidden_credential_like_columns(header):
    """Credential-like source columns are rejected before parsing or logging."""
    with pytest.raises(SourceManifestError, match="forbidden credential-like"):
        validate_sheet_headers("Reviewers", ["reviewer", header])


def test_preflight_does_not_treat_reviewer_email_as_an_importable_column():
    """Reviewer identity must arrive through a configured pseudonymous mapping."""
    with pytest.raises(SourceManifestError, match="email"):
        validate_sheet_headers("Reviewers", ["reviewer_email", "display_name"])

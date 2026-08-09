"""Integration seam for Lane A's profile-aware curation adapter."""

from app.phenopackets.services.state_service import PhenopacketStateService


def test_canonicalization_hook_preserves_legacy_documents_before_adapter_merge():
    """Legacy packets are preserved when the optional v2 adapter is absent."""
    document = {"id": "legacy-1", "subject": {"id": "legacy-1"}}

    result = PhenopacketStateService._canonicalize_for_persistence(document)

    assert result == document
    assert result is not document

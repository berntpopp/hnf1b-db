"""Integration seam for Lane A's profile-aware curation adapter."""

import sys
from types import ModuleType

from app.phenopackets.services.state_service import PhenopacketStateService


def test_canonicalization_hook_preserves_legacy_documents_before_adapter_merge():
    """Legacy packets are preserved when the optional v2 adapter is absent."""
    document = {"id": "legacy-1", "subject": {"id": "legacy-1"}}

    result = PhenopacketStateService._canonicalize_for_persistence(document)

    assert result == document
    assert result is not document


def test_canonicalization_hook_passes_publish_policy_to_v2_adapter(monkeypatch):
    """Draft saves retain structured conflicts; publish asks the adapter to block."""
    calls = []
    adapter = ModuleType("app.phenopackets.curation.adapters")

    class CurationProjectionError(ValueError):
        pass

    def canonicalize_curation_document(document, *, publish):
        calls.append(publish)
        return {**document, "canonical": publish}

    adapter.CurationProjectionError = CurationProjectionError
    adapter.canonicalize_curation_document = canonicalize_curation_document
    monkeypatch.setitem(sys.modules, "app.phenopackets.curation.adapters", adapter)

    assert (
        PhenopacketStateService._canonicalize_for_persistence(
            {"id": "v2-1"}, publish=False
        )["canonical"]
        is False
    )
    assert (
        PhenopacketStateService._canonicalize_for_persistence(
            {"id": "v2-1"}, publish=True
        )["canonical"]
        is True
    )
    assert calls == [False, True]

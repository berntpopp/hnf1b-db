"""Regression tests for the version-two revision ledger payload."""

from __future__ import annotations

import re

from app.phenopackets.services.revision_ledger import (
    build_ledger_v2_payload,
    content_sha256,
    ledger_sha256,
)


def build_fixture_payload() -> dict[str, object]:
    """Build a complete, representative version-two ledger payload."""
    return build_ledger_v2_payload(
        parent_revision_id=41,
        revision_number=42,
        state="approved",
        event_type="approve",
        from_state="in_review",
        to_state="approved",
        change_reason="Independent review approved the candidate.",
        change_patch=[{"op": "replace", "path": "/subject/id", "value": "P-42"}],
        content_sha256="sha256:" + "a" * 64,
        projection_hash="legacy-projection-hash",
        actor_id=7,
        actor_role="curator",
        decision_metadata={
            "attestation": {"reviewer": "reviewer-7", "accepted": True},
            "independentReview": True,
        },
    )


def test_content_digest_covers_extension_fields_and_ignores_key_order() -> None:
    """Full content, including extensions, is canonicalized before hashing."""
    left = {
        "subject": {"id": "1"},
        "hnf1bCuration": {"flag": True},
        "unknownExtension": {"source": "registry"},
    }
    reordered = {
        "unknownExtension": {"source": "registry"},
        "hnf1bCuration": {"flag": True},
        "subject": {"id": "1"},
    }
    changed = {
        "subject": {"id": "1"},
        "hnf1bCuration": {"flag": False},
        "unknownExtension": {"source": "registry"},
    }
    changed_unknown_extension = {
        "subject": {"id": "1"},
        "hnf1bCuration": {"flag": True},
        "unknownExtension": {"source": "publication"},
    }

    digest = content_sha256(left)

    assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
    assert content_sha256({"label": "Müller", "subject": {"id": "1"}}) == (
        "sha256:ebbb266d0272fd333d6b903df186114ae41449fd2c5c3c25a893c5c90d859e17"
    )
    assert digest == content_sha256(reordered)
    assert digest != content_sha256(changed)
    assert digest != content_sha256(changed_unknown_extension)


def test_builder_returns_complete_v2_payload_with_explicit_optional_fields() -> None:
    """The builder fixes the complete, versioned payload contract."""
    payload = build_ledger_v2_payload(
        parent_revision_id=None,
        revision_number=1,
        state="draft",
        event_type="created",
        from_state=None,
        to_state="draft",
        change_reason="Initial creation",
        change_patch=None,
        content_sha256="sha256:" + "b" * 64,
        projection_hash=None,
        actor_id=7,
        actor_role=None,
        decision_metadata=None,
    )

    assert payload == {
        "ledger_version": 2,
        "parent_revision_id": None,
        "revision_number": 1,
        "state": "draft",
        "event_type": "created",
        "from_state": None,
        "to_state": "draft",
        "change_reason": "Initial creation",
        "change_patch": None,
        "content_sha256": "sha256:" + "b" * 64,
        "projection_hash": None,
        "actor_id": 7,
        "actor_role": None,
        "decision_metadata": None,
    }


def test_v2_ledger_hash_changes_with_role_or_decision_metadata() -> None:
    """Actor role and canonical decision metadata are ledger evidence."""
    base = build_fixture_payload()
    reordered_metadata = {
        "independentReview": True,
        "attestation": {"accepted": True, "reviewer": "reviewer-7"},
    }

    assert ledger_sha256(base) == ledger_sha256(
        {**base, "decision_metadata": reordered_metadata}
    )
    assert ledger_sha256(base) != ledger_sha256({**base, "actor_role": "admin"})
    assert ledger_sha256(base) != ledger_sha256(
        {**base, "decision_metadata": {"independentReview": True}}
    )

"""Guard: every curated HPO label matches the authoritative ontology.

The ``hpo_terms_lookup`` table is seeded by Alembic migrations with hand-authored
labels. Hand-authoring drifts: labels fall behind ontology renames and, in one
case, encoded the clinically opposite finding (HP:0033133). This test re-fetches
the authoritative HPO term name from the live HPO API for every ``HP:`` row and
fails on any mismatch, so drift can never reach cited output unnoticed again.

It is marked ``network`` and excluded from the default unit-test run; CI invokes
it in a dedicated step (``pytest -m network``). Transient API/network failures
``skip`` rather than fail — only a definitive label mismatch turns the build red.
Non-HPO identifiers (e.g. ``ORPHA:*``) are skipped: they are not HPO terms.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import text

HPO_API = "https://ontology.jax.org/api/hp/terms"

pytestmark = pytest.mark.network


async def _authoritative_label(client: httpx.AsyncClient, hpo_id: str) -> str | None:
    """Return the current HPO term name, or None on any transient API failure."""
    try:
        resp = await client.get(f"{HPO_API}/{hpo_id}", timeout=20)
    except (httpx.HTTPError, httpx.TimeoutException):
        return None
    if resp.status_code != 200:
        return None
    return resp.json().get("name")


@pytest.mark.asyncio
async def test_curated_hpo_labels_match_authoritative_ontology(db_session):
    """Each curated HP:* label equals the authoritative HPO term name."""
    rows = (
        await db_session.execute(
            text("SELECT hpo_id, label FROM hpo_terms_lookup WHERE hpo_id LIKE 'HP:%'")
        )
    ).all()
    assert rows, "hpo_terms_lookup has no HP:* rows — is the table seeded?"

    mismatches: list[str] = []
    checked = 0
    async with httpx.AsyncClient() as client:
        for hpo_id, our_label in rows:
            official = await _authoritative_label(client, hpo_id)
            if official is None:
                continue  # transient/unavailable — do not fail the build
            checked += 1
            if official != our_label:
                mismatches.append(
                    f"{hpo_id}: stored {our_label!r} != authoritative {official!r}"
                )

    if checked == 0:
        pytest.skip("HPO API unreachable for all terms; skipping integrity check")

    assert not mismatches, (
        "Curated HPO labels disagree with the ontology:\n" + "\n".join(mismatches)
    )

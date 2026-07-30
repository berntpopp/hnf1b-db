"""Whole-corpus schema conformance and REST write-path proof.

**Blocker this closes:** on 2026-07-30, 487 of 923 stored phenopackets (52%)
failed ``SchemaValidator().validate()`` — 365 on a missing
``interpretations[].id`` and 122 on ``phenotypicFeatures[].onset.age`` being a
bare ISO-8601 duration string (e.g. ``"P13Y"``) instead of the GA4GH object
shape. Both are pre-existing corpus shapes, not caused by any code change
(an agent diffed the failing-ID set before/after its change and it was
identical). Since ``PUT /api/v2/phenopackets/{id}`` validates with this same
``SchemaValidator`` and returns HTTP 400 on failure
(``app/phenopackets/routers/crud.py``), a curator could not save an edit to
more than half the corpus. Per ``docs/adr/0003-ga4gh-conformance-debt.md``
(and its Amendment 1), the fix is to widen the reader/validator to the
corpus's real shapes — never to migrate the 923 stored records. See
``app/phenopackets/validation/schema_validator.py`` (the ``interpretation``
definition's ``required`` list, and ``timeElement.age``'s ``type``) for the
two additive relaxations this test guards.

Both tests below need the real 923-record corpus, which lives only in the
**developer** database (``hnf1b_phenopackets``), never in the pytest test
database: ``backend/conftest.py`` rewrites ``DATABASE_URL`` to a dedicated,
empty test database (``hnf1b_phenopackets_test`` or an xdist-worker variant)
before any ``app.*`` module is imported — see that file's module docstring —
specifically so tests never touch the developer's working data. That test
database's own ``phenopackets`` table is truncated before every test by the
autouse fixture in ``tests/conftest.py``. So under CI, and any local run
against the standard test database, the corpus is unreachable or empty by
construction, and ``corpus_rows`` below calls ``pytest.skip()`` rather than
letting either test pass vacuously on zero rows — this codebase already has
several tests that silently pass on an empty corpus for lack of that guard;
this file is not a fifth one.

**Scope note:** ``test_previously_failing_records_round_trip_through_the_write_path``
strips ``variationDescriptor.expressions`` from its PUT payloads. This is
documented in that test's docstring — it exists to route around a separate,
larger, pre-existing defect (a variant-format validator too strict for the
corpus's real VCF/SPDI notations) discovered while writing this proof, which
blocks writes to 864/923 records and is explicitly out of scope for this fix.
"""

from __future__ import annotations

import copy
import json
import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.phenopackets.models import Phenopacket
from app.phenopackets.validation.schema_validator import SchemaValidator

# Same default as the non-secret local dev URL committed in
# backend/.env.example; overridable for anyone whose corpus database lives
# elsewhere.
_CORPUS_DATABASE_URL = os.environ.get(
    "PHENOPACKET_CORPUS_DATABASE_URL",
    "postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets",
)

# Three real records, picked 2026-07-30 to cover the two failure classes and
# their intersection, none carrying phenotypicFeatures[].modifiers (so the
# async DomainValidator's laterality/check_label logic is not exercised —
# this file is proving the *schema* relaxation, not re-litigating domain
# validation). Confirmed at the time of writing: DomainValidator(...).validate()
# returns [] for all three.
_INTERPRETATION_ID_ONLY = "phenopacket-68"  # interpretations[0] has no "id"
_ONSET_AGE_ONLY = "phenopacket-508"  # phenotypicFeatures[].onset.age == "P4Y"
_BOTH = "phenopacket-775"  # both of the above at once


# The two ``expressions[].syntax`` values whose format validators
# (app/phenopackets/validation/variant_validator/format_validators.py)
# reject the corpus's real notations — see the module docstring's "Scope
# note". "iscn" / "ga4gh" / "hgvs.*" expressions are left in place: they are
# what satisfies the separate "Structural variant missing valid CNV
# notation" check, so removing them would trade one unrelated 400 for
# another instead of isolating the fix under test.
_UNVALIDATABLE_SYNTAXES = {"vcf", "spdi"}


def _without_unvalidatable_variant_expressions(doc: dict) -> dict:
    """Deep copy of ``doc`` with the confounding ``expressions`` entries dropped.

    Routes around the separate variant-format-validator confound described in
    this module's docstring, without touching the two fields under test
    (``interpretations[].id`` presence and ``phenotypicFeatures[].onset.age``
    shape) or the CNV-notation expressions the same validator also checks.
    """
    doc = copy.deepcopy(doc)
    for interpretation in doc.get("interpretations", []):
        for gi in interpretation.get("diagnosis", {}).get("genomicInterpretations", []):
            vd = gi.get("variantInterpretation", {}).get("variationDescriptor")
            if vd and vd.get("expressions"):
                vd["expressions"] = [
                    e
                    for e in vd["expressions"]
                    if e.get("syntax") not in _UNVALIDATABLE_SYNTAXES
                ]
    return doc


@pytest_asyncio.fixture
async def corpus_rows():
    """All ``(phenopacket_id, phenopacket_dict)`` rows from the dev corpus DB.

    Opens its own engine directly against ``_CORPUS_DATABASE_URL``,
    independent of ``app.core.config.settings`` (which by the time this runs
    already points at the empty pytest test database). Skips the requesting
    test if that database cannot be reached, or is reachable but empty —
    both are the expected CI state.
    """
    engine = create_async_engine(_CORPUS_DATABASE_URL)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT phenopacket_id, phenopacket FROM phenopackets ORDER BY phenopacket_id"
                )
            )
            rows = result.fetchall()
    except Exception as exc:  # pragma: no cover - environment dependent
        await engine.dispose()
        pytest.skip(
            f"corpus database unreachable at {_CORPUS_DATABASE_URL!r} ({exc!r}); "
            "this test only runs where the real 923-record corpus is loaded."
        )
        return
    await engine.dispose()

    if not rows:
        pytest.skip(
            "corpus database has zero phenopacket rows; this test only runs "
            "where the real 923-record corpus is loaded, never against the "
            "truncated pytest test database."
        )
        return

    return [
        (pid, json.loads(doc) if isinstance(doc, str) else doc) for pid, doc in rows
    ]


def test_every_stored_phenopacket_passes_schema_validation(corpus_rows):
    """The real thing, not a fixture: every row currently in the corpus DB.

    Measured 2026-07-30 before the fix: 487/923 failed. After widening
    ``interpretation.required`` (drop ``id``) and ``timeElement.age``'s
    ``type`` (accept a bare string alongside the wrapped object), this must
    be 0/923 (or whatever the corpus has grown to since).
    """
    validator = SchemaValidator()
    failures = {pid: validator.validate(doc) for pid, doc in corpus_rows}
    failures = {pid: errs for pid, errs in failures.items() if errs}

    assert failures == {}, (
        f"{len(failures)} of {len(corpus_rows)} stored phenopackets fail "
        f"schema validation, e.g. {next(iter(failures.items()))}"
    )


@pytest.mark.asyncio
async def test_previously_failing_records_round_trip_through_the_write_path(
    async_client, curator_headers, curator_user, db_session, corpus_rows
):
    """GET, then PUT unchanged, three real records that used to 400.

    This is the actual blocker for Phase 3: the console loads a record, a
    curator makes no (or an unrelated) edit, and saves. Before the schema
    widen this returned HTTP 400 for the three records below (and 487/923 of
    the corpus generally) because ``PUT`` re-validates with the exact same
    ``SchemaValidator`` used by ``test_every_stored_phenopacket_...`` above
    (``app/phenopackets/routers/crud.py::update_phenopacket``). Uses
    ``curator_headers``, not ``auth_headers`` — the latter is a viewer and
    gets 403 before validation ever runs, which would make this test pass
    for the wrong reason.

    **Newly discovered, out-of-scope confound (not fixed here):** the same
    ``PUT`` handler also runs ``PhenopacketValidator`` (crud.py's
    ``validator.validate()``), a facade that chains variant-format checks
    (``app/phenopackets/validation/variant_validator/format_validators.py``)
    on top of ``SchemaValidator``. Measured 2026-07-30: of the 923 corpus
    records, 100% of those exhibiting either failure class under test here
    also carry a ``variationDescriptor`` whose VCF/SPDI expressions this
    separate, pre-existing regex rejects — CNV entries encode
    ``chrom-start-end-ref-alt`` (5 fields; ``_VCF_PATTERN`` only accepts
    ``chrom-pos-ref-alt``) and SPDI entries use the standard numeric
    deletion-length form (e.g. ``NC_000017.11:37710609:1:C``;
    ``_SPDI_PATTERN`` only accepts literal ``[ATCG]`` there). That bug blocks
    writes to 864/923 corpus records — far more than the 487 this task was
    scoped to — and is untouched by this commit: fixing it is unrelated
    format-validator work, not a schema widen, and doing it here would
    silently balloon a one-issue blocker fix into a second one. So the
    ``expressions`` this confound reacts to are stripped from the PUT
    payload below (documented, not hidden) to isolate what this test can
    actually prove: that the schema-level fix unblocks these two failure
    classes specifically. See the report's "concerns" section.
    """
    by_id = dict(corpus_rows)
    for phenopacket_id in (_INTERPRETATION_ID_ONLY, _ONSET_AGE_ONLY, _BOTH):
        if phenopacket_id not in by_id:
            pytest.skip(
                f"corpus no longer contains {phenopacket_id!r}; the three "
                "hardcoded example ids were picked from a 2026-07-30 "
                "snapshot and may have been renumbered since."
            )

    content_by_id = {
        pid: by_id[pid] for pid in (_INTERPRETATION_ID_ONLY, _ONSET_AGE_ONLY, _BOTH)
    }

    # Sanity-check the failure signature this test claims to exercise, so a
    # future corpus edit that accidentally "fixes" one of these records
    # doesn't silently turn this into a test of nothing.
    assert any(
        "id" not in i
        for i in content_by_id[_INTERPRETATION_ID_ONLY].get("interpretations", [])
    ), f"{_INTERPRETATION_ID_ONLY} no longer lacks an interpretation id"
    assert any(
        isinstance(f.get("onset", {}).get("age"), str)
        for f in content_by_id[_ONSET_AGE_ONLY].get("phenotypicFeatures", [])
    ), f"{_ONSET_AGE_ONLY} no longer has a bare-string onset.age"
    both = content_by_id[_BOTH]
    assert any("id" not in i for i in both.get("interpretations", [])) and any(
        isinstance(f.get("onset", {}).get("age"), str)
        for f in both.get("phenotypicFeatures", [])
    ), f"{_BOTH} no longer exhibits both failure classes"

    statuses: dict[str, tuple[int, int]] = {}
    for phenopacket_id, content in content_by_id.items():
        # metaData.resources must stay non-empty through sanitize_phenopacket
        # (app/phenopackets/validation/sanitizer.py strips empty arrays), or
        # the corpus record would fail on a *different*, unrelated required
        # field and mask what this test is actually proving.
        assert content["metaData"]["resources"], (
            f"{phenopacket_id} has empty metaData.resources; the round trip "
            "would fail on a masking error, not the one under test"
        )

        db_session.add(
            Phenopacket(
                phenopacket_id=phenopacket_id,
                phenopacket=content,
                state="draft",
                revision=1,
                draft_owner_id=curator_user.id,
                created_by_id=curator_user.id,
            )
        )
    await db_session.commit()

    put_bodies: dict[str, str] = {}
    for phenopacket_id in content_by_id:
        get_resp = await async_client.get(
            f"/api/v2/phenopackets/{phenopacket_id}", headers=curator_headers
        )
        assert get_resp.status_code == 200, get_resp.text
        body = get_resp.json()

        # See the module and test docstrings: expressions are stripped here,
        # not because the schema fix needs it, but to route around a
        # separate, unrelated, larger variant-format-validator defect that
        # would otherwise 400 every one of these records regardless of the
        # fix under test.
        put_payload = _without_unvalidatable_variant_expressions(body["phenopacket"])
        put_resp = await async_client.put(
            f"/api/v2/phenopackets/{phenopacket_id}",
            json={
                "phenopacket": put_payload,
                "revision": body["revision"],
                "change_reason": "round-trip verification, no content change",
            },
            headers=curator_headers,
        )
        # Collect all three before asserting, so a failure report shows every
        # record's outcome rather than stopping at the first.
        statuses[phenopacket_id] = (get_resp.status_code, put_resp.status_code)
        put_bodies[phenopacket_id] = put_resp.text

    print("GET/PUT status codes:", statuses)
    failures = {
        pid: (code, put_bodies[pid])
        for pid, (_, code) in statuses.items()
        if not (200 <= code < 300)
    }
    assert failures == {}, f"PUT of unchanged record(s) did not return 2xx: {failures}"

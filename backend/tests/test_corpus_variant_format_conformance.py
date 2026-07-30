"""Whole-corpus variant-format conformance and REST write-path proof.

**Blocker this closes:** on 2026-07-31, 864 of 923 stored phenopackets (94%)
failed ``PhenopacketValidator().validate()`` — the facade
``app/phenopackets/validator.py`` composes ``SchemaValidator`` (fixed
separately, see ``tests/test_corpus_schema_conformance.py``) with
``VariantValidator.validate_variants_in_phenopacket``
(``app/phenopackets/validation/variant_validator/format_validators.py``).
The dominant failure classes, measured against the live corpus:

- 440 instances — 5-field structural VCF with a symbolic ALT, e.g.
  ``17-36459258-37832869-C-<DEL>`` (``chrom-start-END-ref-<SYMBOLIC>``). The
  old ``_VCF_PATTERN`` only accepted the 4-field ``chrom-pos-ref-alt`` form.
- 424 instances — SPDI with a numeric deleted-*length* third field, e.g.
  ``NC_000017.11:37739585:1:C``. SPDI permits the third field to be either
  the deleted *sequence* or the deleted *length*; the old ``_SPDI_PATTERN``
  only accepted the sequence form.
- 83 instances — HGVS p. frameshift with an explicit new-stop-codon
  position, e.g. ``NP_000449.3:p.Pro328LeufsTer48`` (old pattern accepted
  bare ``fs`` only).
- 79 + 43 instances — HGVS g. range and single-position deletion/insertion
  with no ref/alt bases, e.g. ``NC_000017.11:g.37731657del`` (old pattern
  only accepted the substitution form ``g.\\d+[ATCG]>[ATCG]``).
- 18 + 6 instances — HGVS c. intronic deletion/duplication, single position
  or range, e.g. ``NM_000458.4:c.544+3_544+6del`` (old patterns supported
  intronic *substitutions* but not intronic indels).
- 5 + 1 + 1 instances — HGVS p. in-frame deletion/delins, single residue or
  range, e.g. ``NP_000449.3:p.Arg137_Lys161del``,
  ``NP_000449.3:p.Ala373_Gln383delinsGlu``.
- 2 instances — HGVS c. delins with literal sequences on both sides, e.g.
  ``NM_000458.4:c.499_504delGCTCTGinsCCCCT``.

Since ``PUT /api/v2/phenopackets/{id}`` validates with this same
``PhenopacketValidator`` and returns HTTP 400 on failure
(``app/phenopackets/routers/crud.py::update_phenopacket``), a curator could
not save an edit to 94% of the corpus. Per
``docs/adr/0003-ga4gh-conformance-debt.md`` (the same relief already used for
D4, "correct the reader, not the corpus"), the fix widens
``format_validators.py``'s regexes to the corpus's measured real shapes —
it never migrates the 923 stored records. See that module for the additive
regex changes this test guards.

Both tests below need the real 923-record corpus, which lives only in the
**developer** database (``hnf1b_phenopackets``), never in the pytest test
database — see ``tests/test_corpus_schema_conformance.py``'s module
docstring for the full explanation of why ``corpus_rows`` below calls
``pytest.skip()`` rather than letting either test pass vacuously on an
empty/unreachable corpus.

**Unlike** ``test_corpus_schema_conformance.py``'s round-trip test, the one
below does **not** strip ``vcf``/``spdi`` expressions from the PUT payload —
those notations are exactly what this fix makes valid, so stripping them
would prove nothing about the fix under test.
"""

from __future__ import annotations

import json
import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.phenopackets.models import Phenopacket
from app.phenopackets.validator import PhenopacketValidator

# Same default as the non-secret local dev URL committed in
# backend/.env.example; overridable for anyone whose corpus database lives
# elsewhere.
_CORPUS_DATABASE_URL = os.environ.get(
    "PHENOPACKET_CORPUS_DATABASE_URL",
    "postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets",
)

# Three real records, picked 2026-07-31 to cover the two shapes named
# explicitly in the blocker report plus a third, independent failure class.
# None carries hnf1bCuration/segregation content that would fail
# DomainValidator, and all three keep metaData.resources non-empty through
# the sanitizer — confirmed at the time of writing:
# DomainValidator(...).validate() returns [] for all three.
_CNV_5FIELD_VCF = "phenopacket-524"  # vcf expression: 17-36459258-37832869-C-<DEL>
_SPDI_NUMERIC_LENGTH = "phenopacket-100"  # spdi expression: NC_...:pos:<int>:<seq>
_MIXED_HGVS_SPDI = "phenopacket-115"  # hgvs.g del + hgvs.p fsTer## + spdi, together

_ROUND_TRIP_IDS = (_CNV_5FIELD_VCF, _SPDI_NUMERIC_LENGTH, _MIXED_HGVS_SPDI)


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


def test_every_stored_phenopacket_passes_variant_format_validation(corpus_rows):
    """The real thing, not a fixture: every row currently in the corpus DB.

    Measured 2026-07-31 before the fix: 864/923 (94%) failed
    ``PhenopacketValidator().validate()`` on a variant-format error (schema
    validation alone was already 0/923 after the sibling fix). After
    widening the five ``format_validators.py`` regex families to the
    corpus's measured real shapes, this must be 0/923 (or whatever the
    corpus has grown to since).
    """
    validator = PhenopacketValidator()
    failures = {pid: validator.validate(doc) for pid, doc in corpus_rows}
    failures = {pid: errs for pid, errs in failures.items() if errs}

    assert failures == {}, (
        f"{len(failures)} of {len(corpus_rows)} stored phenopackets fail "
        f"variant-format validation, e.g. {next(iter(failures.items()))}"
    )


def _vcf_values(doc):
    for interpretation in doc.get("interpretations", []):
        for gi in interpretation.get("diagnosis", {}).get("genomicInterpretations", []):
            vd = gi.get("variantInterpretation", {}).get("variationDescriptor", {})
            for expr in vd.get("expressions", []):
                yield expr.get("syntax"), expr.get("value", "")


@pytest.mark.asyncio
async def test_cnv_spdi_and_mixed_hgvs_records_round_trip_through_the_write_path(
    async_client, curator_headers, curator_user, db_session, corpus_rows
):
    """GET, then PUT unchanged, three real records that used to 400.

    This is the actual blocker for Phase 3: the console loads a record with
    variant data, a curator makes no (or an unrelated) edit, and saves.
    Before this fix, ``PUT`` re-validated with
    ``PhenopacketValidator().validate()``
    (``app/phenopackets/routers/crud.py::update_phenopacket``) and returned
    HTTP 400 for all three records below (and 864/923 of the corpus
    generally). Uses ``curator_headers``, not ``auth_headers`` — the latter
    is a viewer and gets 403 before validation ever runs, which would make
    this test pass for the wrong reason.

    Deliberately does **not** strip ``vcf``/``spdi`` expressions from the PUT
    payload the way ``test_corpus_schema_conformance.py``'s round trip does
    — that stripping existed there specifically to route around *this*
    defect while it was still unfixed. Proving the fix means proving the
    unstripped payload round-trips.
    """
    by_id = dict(corpus_rows)
    for phenopacket_id in _ROUND_TRIP_IDS:
        if phenopacket_id not in by_id:
            pytest.skip(
                f"corpus no longer contains {phenopacket_id!r}; the three "
                "hardcoded example ids were picked from a 2026-07-31 "
                "snapshot and may have been renumbered since."
            )

    content_by_id = {pid: by_id[pid] for pid in _ROUND_TRIP_IDS}

    # Sanity-check the failure signature this test claims to exercise, so a
    # future corpus edit that accidentally "fixes" one of these records
    # doesn't silently turn this into a test of nothing.
    cnv_syntaxes = dict(_vcf_values(content_by_id[_CNV_5FIELD_VCF]))
    assert any(
        syn == "vcf" and len(val.split("-")) == 5
        for syn, val in _vcf_values(content_by_id[_CNV_5FIELD_VCF])
    ), f"{_CNV_5FIELD_VCF} no longer carries a 5-field structural VCF expression"
    del cnv_syntaxes

    assert any(
        syn == "spdi" and len(val.split(":")) == 4 and val.split(":")[2].isdigit()
        for syn, val in _vcf_values(content_by_id[_SPDI_NUMERIC_LENGTH])
    ), (
        f"{_SPDI_NUMERIC_LENGTH} no longer carries a numeric-deleted-length SPDI expression"
    )

    mixed_syntaxes = {syn for syn, _ in _vcf_values(content_by_id[_MIXED_HGVS_SPDI])}
    assert {"hgvs.g", "hgvs.p", "spdi"} & mixed_syntaxes, (
        f"{_MIXED_HGVS_SPDI} no longer carries any of the hgvs.g/hgvs.p/spdi "
        "expressions this record was picked to exercise"
    )

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
    statuses: dict[str, tuple[int, int]] = {}
    for phenopacket_id in content_by_id:
        get_resp = await async_client.get(
            f"/api/v2/phenopackets/{phenopacket_id}", headers=curator_headers
        )
        assert get_resp.status_code == 200, get_resp.text
        body = get_resp.json()

        # No expression stripping here — see the module and test docstrings.
        put_resp = await async_client.put(
            f"/api/v2/phenopackets/{phenopacket_id}",
            json={
                "phenopacket": body["phenopacket"],
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

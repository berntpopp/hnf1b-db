"""Tests for variant search endpoint.

This module tests the /aggregate/all-variants endpoint with search and filter
capabilities, including security validation, HGVS notation search, and molecular
consequence filtering.
"""

import logging

import pytest
from fastapi import HTTPException

from app.phenopackets.molecular_consequence import (
    compute_molecular_consequence,
    filter_by_consequence,
)
from app.phenopackets.variant_search_validation import (
    validate_classification,
    validate_gene,
    validate_hg38_coordinate,
    validate_hgvs_notation,
    validate_molecular_consequence,
    validate_search_query,
    validate_variant_type,
)


class TestHGVSValidation:
    """Test HGVS notation format validation."""

    def test_valid_c_notation(self):
        """Test valid c. notations."""
        assert validate_hgvs_notation("c.1654-2A>T") is True
        assert validate_hgvs_notation("c.544+1G>T") is True
        assert validate_hgvs_notation("c.1621C>T") is True
        assert validate_hgvs_notation("c.1654_1656del") is True

    def test_valid_p_notation(self):
        """Test valid p. notations."""
        assert validate_hgvs_notation("p.Arg177Ter") is True
        assert validate_hgvs_notation("p.(Ser546Phe)") is True
        assert validate_hgvs_notation("p.Gly319del") is True

    def test_valid_g_notation(self):
        """Test valid g. notations."""
        assert validate_hgvs_notation("g.36098063A>T") is True
        assert validate_hgvs_notation("g.36459258_37832869del") is True

    def test_invalid_hgvs(self):
        """Test invalid HGVS formats."""
        assert validate_hgvs_notation("invalid") is False
        assert validate_hgvs_notation("c.invalid") is False
        assert validate_hgvs_notation("x.123A>T") is False


class TestHG38Validation:
    """Test HG38 genomic coordinate validation."""

    def test_valid_coordinates(self):
        """Test valid HG38 coordinate formats."""
        assert validate_hg38_coordinate("chr17:36098063") is True
        assert validate_hg38_coordinate("chr17-36098063-A-T") is True
        assert validate_hg38_coordinate("17:36459258-37832869") is True
        assert validate_hg38_coordinate("17:36459258-37832869:DEL") is True
        assert validate_hg38_coordinate("chrX:12345") is True
        assert validate_hg38_coordinate("chrY:67890") is True

    def test_invalid_coordinates(self):
        """Test invalid coordinate formats."""
        assert validate_hg38_coordinate("invalid:format") is False
        assert validate_hg38_coordinate("chr:123") is False
        assert validate_hg38_coordinate("abc:123") is False


class TestSearchQueryValidation:
    """Test search query validation and sanitization."""

    def test_valid_search_queries(self):
        """Test valid search queries."""
        assert validate_search_query("c.1654-2A>T") == "c.1654-2A>T"
        assert validate_search_query("chr17:36098063") == "chr17:36098063"
        assert validate_search_query("HNF1B") == "HNF1B"
        assert validate_search_query("Var1") == "Var1"

    def test_query_too_long(self):
        """Test length limit enforcement."""
        long_query = "A" * 201
        with pytest.raises(HTTPException) as exc:
            validate_search_query(long_query)
        assert exc.value.status_code == 400
        assert "too long" in exc.value.detail

    def test_query_invalid_characters(self):
        """Test character whitelist enforcement (SQL injection prevention)."""
        with pytest.raises(HTTPException) as exc:
            validate_search_query("'; DROP TABLE phenopackets;--")
        assert exc.value.status_code == 400
        assert "invalid characters" in exc.value.detail

    def test_query_special_characters_allowed(self):
        """Test that allowed special characters work."""
        assert validate_search_query("c.123+1G>T") is not None
        assert validate_search_query("p.(Arg177*)") is not None

    def test_partial_hgvs_allowed_for_search(self):
        """Test that partial/incomplete HGVS notation is allowed for search queries.

        Unlike data entry, search queries intentionally allow partial HGVS to
        enable flexible searching (e.g., "c.826" should match "c.826C>G").
        """
        # These partial patterns should NOT raise an exception for search
        assert validate_search_query("c.invalid") == "c.invalid"
        assert validate_search_query("c.826") == "c.826"
        assert validate_search_query("p.Arg") == "p.Arg"


class TestVariantTypeValidation:
    """Test variant type filter validation."""

    def test_valid_variant_types(self):
        """Test valid variant types."""
        assert validate_variant_type("SNV") == "SNV"
        assert validate_variant_type("deletion") == "deletion"
        assert validate_variant_type("duplication") == "duplication"
        assert validate_variant_type("insertion") == "insertion"
        assert validate_variant_type("inversion") == "inversion"
        assert validate_variant_type("CNV") == "CNV"

    def test_invalid_variant_type(self):
        """Test invalid variant type."""
        with pytest.raises(HTTPException) as exc:
            validate_variant_type("invalid_type")
        assert exc.value.status_code == 400
        assert "Invalid variant type" in exc.value.detail

    def test_none_variant_type(self):
        """Test None returns None."""
        assert validate_variant_type(None) is None


class TestClassificationValidation:
    """Test ACMG classification filter validation."""

    def test_valid_classifications(self):
        """Test valid classifications."""
        assert validate_classification("PATHOGENIC") == "PATHOGENIC"
        assert validate_classification("LIKELY_PATHOGENIC") == "LIKELY_PATHOGENIC"
        assert (
            validate_classification("UNCERTAIN_SIGNIFICANCE")
            == "UNCERTAIN_SIGNIFICANCE"
        )
        assert validate_classification("LIKELY_BENIGN") == "LIKELY_BENIGN"
        assert validate_classification("BENIGN") == "BENIGN"

    def test_invalid_classification(self):
        """Test invalid classification."""
        with pytest.raises(HTTPException) as exc:
            validate_classification("INVALID")
        assert exc.value.status_code == 400
        assert "Invalid classification" in exc.value.detail


class TestGeneValidation:
    """Test gene symbol filter validation."""

    def test_valid_gene(self):
        """Test valid gene symbol."""
        assert validate_gene("HNF1B") == "HNF1B"

    def test_invalid_gene(self):
        """Test invalid gene symbol."""
        with pytest.raises(HTTPException) as exc:
            validate_gene("INVALID_GENE")
        assert exc.value.status_code == 400
        assert "Invalid gene" in exc.value.detail


class TestMolecularConsequenceValidation:
    """Test molecular consequence filter validation."""

    def test_valid_consequences(self):
        """Test valid molecular consequences."""
        assert validate_molecular_consequence("Frameshift") == "Frameshift"
        assert validate_molecular_consequence("Nonsense") == "Nonsense"
        assert validate_molecular_consequence("Missense") == "Missense"
        assert validate_molecular_consequence("Splice Donor") == "Splice Donor"

    def test_invalid_consequence(self):
        """Test invalid molecular consequence."""
        with pytest.raises(HTTPException) as exc:
            validate_molecular_consequence("Invalid Consequence")
        assert exc.value.status_code == 400
        assert "Invalid molecular consequence" in exc.value.detail


class TestMolecularConsequenceComputation:
    """Test molecular consequence computation from HGVS notations."""

    def test_frameshift(self):
        """Test frameshift detection."""
        result = compute_molecular_consequence(
            transcript=None, protein="NP_000449.3:p.Arg177fs", variant_type=None
        )
        assert result == "Frameshift"

    def test_nonsense(self):
        """Test nonsense/stop-gained detection."""
        result = compute_molecular_consequence(
            transcript=None, protein="NP_000449.3:p.Arg177Ter", variant_type=None
        )
        assert result == "Nonsense"

        result = compute_molecular_consequence(
            transcript=None, protein="NP_000449.3:p.Arg177*", variant_type=None
        )
        assert result == "Nonsense"

    def test_missense(self):
        """Test missense detection."""
        result = compute_molecular_consequence(
            transcript=None, protein="NP_000449.3:p.Arg177Cys", variant_type=None
        )
        assert result == "Missense"

    def test_inframe_deletion(self):
        """Test in-frame deletion detection."""
        result = compute_molecular_consequence(
            transcript=None, protein="NP_000449.3:p.Gly319del", variant_type=None
        )
        assert result == "In-frame Deletion"

    def test_splice_donor(self):
        """Test splice donor detection."""
        result = compute_molecular_consequence(
            transcript="NM_000458.4:c.544+1G>T", protein=None, variant_type=None
        )
        assert result == "Splice Donor"

    def test_splice_acceptor(self):
        """Test splice acceptor detection."""
        result = compute_molecular_consequence(
            transcript="NM_000458.4:c.1654-2A>T", protein=None, variant_type=None
        )
        assert result == "Splice Acceptor"

    def test_intronic_variant(self):
        """Test intronic variant detection."""
        result = compute_molecular_consequence(
            transcript="NM_000458.4:c.544+15G>T", protein=None, variant_type=None
        )
        assert result == "Intronic Variant"

    def test_copy_number_loss(self):
        """Test copy number loss (deletion) detection."""
        result = compute_molecular_consequence(
            transcript=None, protein=None, variant_type="deletion"
        )
        assert result == "Copy Number Loss"

    def test_copy_number_gain(self):
        """Test copy number gain (duplication) detection."""
        result = compute_molecular_consequence(
            transcript=None, protein=None, variant_type="duplication"
        )
        assert result == "Copy Number Gain"

    def test_synonymous(self):
        """Test synonymous variant detection."""
        result = compute_molecular_consequence(
            transcript=None, protein="NP_000449.3:p.Arg177=", variant_type=None
        )
        assert result == "Synonymous"


class TestConsequenceFiltering:
    """Test molecular consequence filtering."""

    def test_filter_by_consequence(self):
        """Test filtering variants by molecular consequence."""
        variants = [
            {
                "variant_id": "var1",
                "transcript": "NM_000458.4:c.544+1G>T",
                "protein": None,
                "structural_type": "SNV",
            },
            {
                "variant_id": "var2",
                "transcript": None,
                "protein": "NP_000449.3:p.Arg177Ter",
                "structural_type": "SNV",
            },
            {
                "variant_id": "var3",
                "transcript": "NM_000458.4:c.1654-2A>T",
                "protein": None,
                "structural_type": "SNV",
            },
        ]

        # Filter for splice donors
        filtered = filter_by_consequence(variants, "Splice Donor")
        assert len(filtered) == 1
        assert filtered[0]["variant_id"] == "var1"

        # Filter for nonsense
        filtered = filter_by_consequence(variants, "Nonsense")
        assert len(filtered) == 1
        assert filtered[0]["variant_id"] == "var2"

        # Filter for splice acceptor
        filtered = filter_by_consequence(variants, "Splice Acceptor")
        assert len(filtered) == 1
        assert filtered[0]["variant_id"] == "var3"

    def test_no_filter(self):
        """Test that None filter returns all variants."""
        variants = [{"variant_id": "var1"}, {"variant_id": "var2"}]
        filtered = filter_by_consequence(variants, None)
        assert len(filtered) == 2


ALL_VARIANTS_PATH = "/api/v2/phenopackets/aggregate/all-variants"


def _transitions_url(phenopacket_id: str) -> str:
    return f"/api/v2/phenopackets/{phenopacket_id}/transitions"


def _variant_phenopacket_payload(
    pid: str,
    var_id: str,
    *,
    hgvs_c: str,
    hgvs_p: str | None,
    pos: str,
) -> dict:
    """Build a minimal published-able phenopacket carrying one variant.

    The expressions drive ``compute_molecular_consequence`` (HGVS fallback),
    which is the value the all-variants endpoint renders and now filters on.
    """
    expressions = [{"syntax": "hgvs.c", "value": hgvs_c}]
    if hgvs_p is not None:
        expressions.append({"syntax": "hgvs.p", "value": hgvs_p})
    return {
        "phenopacket": {
            "id": pid,
            "subject": {"id": "s", "sex": "MALE"},
            "phenotypicFeatures": [],
            "interpretations": [
                {
                    "id": "interp-1",
                    "progressStatus": "SOLVED",
                    "diagnosis": {
                        "disease": {"id": "MONDO:0000001", "label": "test"},
                        "genomicInterpretations": [
                            {
                                "subjectOrBiosampleId": "s",
                                "interpretationStatus": "PATHOGENIC",
                                "variantInterpretation": {
                                    "acmgPathogenicityClassification": "PATHOGENIC",
                                    "variationDescriptor": {
                                        "id": var_id,
                                        "label": var_id,
                                        "geneContext": {
                                            "valueId": "HGNC:11621",
                                            "symbol": "HNF1B",
                                        },
                                        "expressions": expressions,
                                        "vcfRecord": {
                                            "chrom": "17",
                                            "pos": pos,
                                            "ref": "A",
                                            "alt": "G",
                                        },
                                    },
                                },
                            }
                        ],
                    },
                }
            ],
            "metaData": {
                "created": "2026-04-11T00:00:00Z",
                "createdBy": "pytest",
                "resources": [
                    {
                        "id": "hp",
                        "name": "Human Phenotype Ontology",
                        "url": "http://purl.obolibrary.org/obo/hp.owl",
                        "version": "2024-01-01",
                        "namespacePrefix": "HP",
                        "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                    }
                ],
            },
        }
    }


async def _create_and_publish(async_client, admin_headers, payload, pid) -> None:
    resp = await async_client.post(
        "/api/v2/phenopackets/", json=payload, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    rev = resp.json()["revision"]
    for to_state in ("in_review", "approved", "published"):
        r = await async_client.post(
            _transitions_url(pid),
            json={"to_state": to_state, "reason": f"test: {to_state}", "revision": rev},
            headers=admin_headers,
        )
        assert r.status_code == 200, f"transition to {to_state} failed: {r.text}"
        rev = r.json()["phenopacket"]["revision"]


@pytest.mark.asyncio
class TestAllVariantsConsequenceFilter:
    """Regression: the ``consequence`` filter must honor the displayed value.

    Previously ``consequence=Missense`` was silently ignored because the SQL
    builder keyed on coarse categories (missense/lof/...) that never matched the
    enum display values (``Missense``/``Splice Donor``/...). The endpoint now
    post-filters on the computed ``molecular_consequence`` so every returned row
    matches the request and ``totalRecords`` reflects the filtered count.
    """

    async def _seed(self, async_client, admin_headers) -> None:
        # Missense: p.Arg177Cys
        await _create_and_publish(
            async_client,
            admin_headers,
            _variant_phenopacket_payload(
                "consq-missense-001",
                "consq-var-missense",
                hgvs_c="NM_000458.4:c.529C>T",
                hgvs_p="NP_000449.3:p.Arg177Cys",
                pos="36000001",
            ),
            "consq-missense-001",
        )
        # Nonsense: p.Arg177Ter
        await _create_and_publish(
            async_client,
            admin_headers,
            _variant_phenopacket_payload(
                "consq-nonsense-001",
                "consq-var-nonsense",
                hgvs_c="NM_000458.4:c.529C>T",
                hgvs_p="NP_000449.3:p.Arg177Ter",
                pos="36000002",
            ),
            "consq-nonsense-001",
        )
        # Splice Donor: c.544+1G>T (no protein notation)
        await _create_and_publish(
            async_client,
            admin_headers,
            _variant_phenopacket_payload(
                "consq-splice-001",
                "consq-var-splice",
                hgvs_c="NM_000458.4:c.544+1G>T",
                hgvs_p=None,
                pos="36000003",
            ),
            "consq-splice-001",
        )

    async def test_missense_returns_only_missense_rows(
        self, async_client, admin_headers
    ):
        """consequence=Missense returns ONLY rows whose computed value is Missense."""
        await self._seed(async_client, admin_headers)

        resp = await async_client.get(
            ALL_VARIANTS_PATH,
            params={"consequence": "Missense", "page[size]": 100},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        rows = body["data"]

        # Core invariant: every returned row matches the requested consequence.
        assert len(rows) >= 1, "expected at least the seeded Missense variant"
        assert all(r["molecular_consequence"] == "Missense" for r in rows), [
            r["molecular_consequence"] for r in rows
        ]
        # The seeded missense variant must be present...
        ids = {r["variant_id"] for r in rows}
        assert "consq-var-missense" in ids
        # ...and the non-missense seeds must NOT leak through.
        assert "consq-var-nonsense" not in ids
        assert "consq-var-splice" not in ids

        # totalRecords reflects the filtered count (== number of matching rows
        # when they fit on one page).
        assert body["meta"]["page"]["totalRecords"] == len(rows)

    async def test_unmatched_consequence_returns_zero_rows(
        self, async_client, admin_headers
    ):
        """A consequence with no matching data returns 0 rows (not all rows).

        This is the heart of the bug: before the fix the filter was ignored, so
        an unmatched consequence returned the entire unfiltered dataset.
        """
        await self._seed(async_client, admin_headers)

        # None of the seeded variants are in-frame deletions.
        resp = await async_client.get(
            ALL_VARIANTS_PATH,
            params={"consequence": "In-frame Deletion", "page[size]": 100},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["data"] == []
        assert body["meta"]["page"]["totalRecords"] == 0

    async def test_splice_donor_filter_isolates_splice_rows(
        self, async_client, admin_headers
    ):
        """consequence=Splice Donor returns only the splice-donor variant."""
        await self._seed(async_client, admin_headers)

        resp = await async_client.get(
            ALL_VARIANTS_PATH,
            params={"consequence": "Splice Donor", "page[size]": 100},
            headers=admin_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        rows = body["data"]
        assert all(r["molecular_consequence"] == "Splice Donor" for r in rows)
        ids = {r["variant_id"] for r in rows}
        assert "consq-var-splice" in ids
        assert "consq-var-missense" not in ids
        assert "consq-var-nonsense" not in ids
        assert body["meta"]["page"]["totalRecords"] == len(rows)


def _variant_search_records(caplog) -> list:
    """Audit records emitted by the all-variants endpoint."""
    return [r for r in caplog.records if r.getMessage() == "VARIANT_SEARCH"]


@pytest.mark.asyncio
class TestAllVariantsAuditUser:
    """Issue #140: the /all-variants audit log records the authenticated user.

    Previously ``user_id`` was hardcoded to ``None`` (always ``"anonymous"``).
    The endpoint now resolves the optional user and logs their email, while
    unauthenticated requests still log ``"anonymous"``.
    """

    async def test_authenticated_request_logs_user_email(
        self, async_client, admin_headers, caplog
    ):
        """An authenticated request records the caller's email in the audit log."""
        with caplog.at_level(logging.INFO, logger="audit"):
            resp = await async_client.get(ALL_VARIANTS_PATH, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        records = _variant_search_records(caplog)
        assert records, "expected a VARIANT_SEARCH audit record"
        assert records[-1].user_id == "testadmin@example.com"

    async def test_anonymous_request_logs_anonymous(self, async_client, caplog):
        """An unauthenticated request still records ``anonymous`` (no PII leak)."""
        with caplog.at_level(logging.INFO, logger="audit"):
            resp = await async_client.get(ALL_VARIANTS_PATH)
        assert resp.status_code == 200, resp.text
        records = _variant_search_records(caplog)
        assert records, "expected a VARIANT_SEARCH audit record"
        assert records[-1].user_id == "anonymous"

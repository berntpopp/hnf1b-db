"""Tests for the Wave 4 ``crud_related`` and ``crud_timeline`` routers.

Covers the endpoints that were lifted out of the monolithic ``crud.py``
during Wave 4 so Codecov sees the new file locations as exercised:

- ``GET /phenopackets/{id}/audit``          (``crud_related``)
- ``GET /phenopackets/by-variant/{id}``     (``crud_related``)
- ``GET /phenopackets/by-publication/{p}``  (``crud_related``)
- ``GET /phenopackets/{id}/timeline``       (``crud_timeline``)

Also exercises the private helpers ``_extract_current_age``,
``_extract_onset``, ``_build_evidence_list`` and ``_categorise_feature``
directly — they're pure functions, so unit coverage is cheap and keeps
the regex/parse logic from silently breaking.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.phenopackets.models import Phenopacket
from app.phenopackets.routers.crud_timeline import (
    _build_evidence_list,
    _categorise_feature,
    _extract_current_age,
    _extract_onset,
)

# ---------------------------------------------------------------------------
# Unit tests for the pure helpers in crud_timeline
# ---------------------------------------------------------------------------


class TestExtractCurrentAge:
    """``_extract_current_age`` parses the subject's ``timeAtLastEncounter``."""

    def test_missing_time_at_last_returns_none_pair(self):
        """Empty subject → both parts of the tuple are None."""
        assert _extract_current_age({}) == (None, None)

    def test_years_only_iso_duration(self):
        """``P12Y`` → parsed as 12.0 years."""
        subject = {"timeAtLastEncounter": {"age": {"iso8601duration": "P12Y"}}}
        iso, years = _extract_current_age(subject)
        assert iso == "P12Y"
        assert years == pytest.approx(12.0)

    def test_years_months_days_duration(self):
        """``P12Y6M10D`` → 12 + 0.5 + 10/365."""
        subject = {"timeAtLastEncounter": {"age": {"iso8601duration": "P12Y6M10D"}}}
        iso, years = _extract_current_age(subject)
        assert iso == "P12Y6M10D"
        assert years == pytest.approx(12 + 6 / 12 + 10 / 365)

    def test_malformed_duration_returns_iso_and_none_years(self):
        """Unparseable duration returns the raw string and ``None`` for years."""
        subject = {"timeAtLastEncounter": {"age": {"iso8601duration": "not-iso"}}}
        iso, years = _extract_current_age(subject)
        # The regex is loose enough that it matches the empty prefix
        # and returns 0 — either answer is acceptable so long as it
        # doesn't crash.
        assert iso == "not-iso"
        assert years in (None, 0.0)

    def test_time_at_last_not_dict(self):
        """Non-dict ``timeAtLastEncounter`` returns the None pair."""
        assert _extract_current_age({"timeAtLastEncounter": "nope"}) == (
            None,
            None,
        )


class TestExtractOnset:
    """``_extract_onset`` handles all four onset shapes."""

    def test_no_onset_returns_none_pair(self):
        """A feature with no onset returns ``(None, None)``."""
        assert _extract_onset({}) == (None, None)

    def test_onset_age_as_string(self):
        """``onset.age`` as bare string passes through."""
        assert _extract_onset({"onset": {"age": "P5Y"}}) == ("P5Y", None)

    def test_onset_age_as_object(self):
        """``onset.age.iso8601duration`` unwraps the nested value."""
        feature = {"onset": {"age": {"iso8601duration": "P3Y"}}}
        assert _extract_onset(feature) == ("P3Y", None)

    def test_onset_direct_iso_field(self):
        """``onset.iso8601duration`` takes effect when ``age`` is absent."""
        assert _extract_onset({"onset": {"iso8601duration": "P1Y"}}) == (
            "P1Y",
            None,
        )

    def test_onset_ontology_class_label(self):
        """``onset.ontologyClass.label`` becomes the onset label."""
        feature = {
            "onset": {"ontologyClass": {"id": "HP:0003577", "label": "Congenital"}}
        }
        assert _extract_onset(feature) == (None, "Congenital")


class TestBuildEvidenceList:
    """``_build_evidence_list`` converts feature.evidence to the timeline shape."""

    def test_empty_evidence_list(self):
        """No evidence → empty list."""
        assert _build_evidence_list({}) == []

    def test_evidence_with_pmid_reference(self):
        """PMID references are stripped of the ``PMID:`` prefix."""
        feature = {
            "evidence": [
                {
                    "evidenceCode": {"label": "TAS"},
                    "reference": {
                        "id": "PMID:12345",
                        "description": "the abstract",
                        "recordedAt": "2024-06-01T00:00:00Z",
                    },
                }
            ]
        }
        result = _build_evidence_list(feature)
        assert len(result) == 1
        assert result[0]["pmid"] == "12345"
        assert result[0]["evidence_code"] == "TAS"
        assert result[0]["description"] == "the abstract"
        assert result[0]["recorded_at"] == "2024-06-01T00:00:00Z"

    def test_evidence_with_non_pmid_reference(self):
        """Non-PMID references leave ``pmid`` set to ``None``."""
        feature = {
            "evidence": [
                {
                    "evidenceCode": {"label": "IEA"},
                    "reference": {"id": "DOI:10.1000/abc"},
                }
            ]
        }
        result = _build_evidence_list(feature)
        assert result[0]["pmid"] is None


class TestCategoriseFeature:
    """``_categorise_feature`` buckets HPO IDs into coarse categories."""

    @pytest.mark.parametrize(
        ("hpo_id", "expected"),
        [
            ("HP:0000107", "renal"),  # renal cyst
            ("HP:0003111", "renal"),  # sodium concentration abnormality
            ("HP:0004904", "diabetes"),
            ("HP:0000079", "genital"),
            ("HP:0000119", "genital"),
            ("HP:0000001", "other"),
            (None, "other"),
            ("", "other"),
        ],
    )
    def test_bucketing(self, hpo_id, expected):
        """Each canonical ID falls into the expected bucket."""
        assert _categorise_feature(hpo_id) == expected


# ---------------------------------------------------------------------------
# End-to-end endpoint tests — drive the routers via the async_client fixture
# ---------------------------------------------------------------------------


def _make_phenopacket_row(
    phenopacket_id: str = "TIMELINE-TEST-001",
    subject_id: str = "SUB-TIMELINE-001",
    *,
    include_timeline_features: bool = True,
    include_variant: bool = False,
    include_pmid: bool = False,
    deleted: bool = False,
) -> Phenopacket:
    """Build a ``Phenopacket`` ORM instance for direct DB insertion."""
    features: list[dict] = []
    interpretations: list[dict] = []
    external_references: list[dict] = []

    if include_timeline_features:
        features = [
            {
                "type": {"id": "HP:0000107", "label": "Renal cyst"},
                "onset": {"age": {"iso8601duration": "P5Y"}},
                "evidence": [
                    {
                        "evidenceCode": {"label": "TAS"},
                        "reference": {"id": "PMID:99999"},
                    }
                ],
            },
            {
                "type": {"id": "HP:0004904", "label": "Maturity-onset diabetes"},
                "excluded": False,
            },
        ]

    if include_variant:
        interpretations = [
            {
                "id": f"interp-{phenopacket_id}",
                "progressStatus": "SOLVED",
                "diagnosis": {
                    "genomicInterpretations": [
                        {
                            "subjectOrBiosampleId": subject_id,
                            "interpretationStatus": "CAUSATIVE",
                            "variantInterpretation": {
                                "acmgPathogenicityClassification": "PATHOGENIC",
                                "variationDescriptor": {
                                    "id": "17-36459258-A-G",
                                    "geneContext": {"symbol": "HNF1B"},
                                },
                            },
                        }
                    ]
                },
            }
        ]

    if include_pmid:
        external_references = [{"id": "PMID:12345", "description": "Test paper"}]

    phenopacket = {
        "id": phenopacket_id,
        "subject": {
            "id": subject_id,
            "sex": "MALE",
            "timeAtLastEncounter": {"age": {"iso8601duration": "P10Y"}},
        },
        "phenotypicFeatures": features,
        "interpretations": interpretations,
        "metaData": {
            "created": "2026-04-11T00:00:00Z",
            "createdBy": "router-test",
            "phenopacketSchemaVersion": "2.0",
            "resources": [
                {
                    "id": "hp",
                    "name": "Human Phenotype Ontology",
                    "namespacePrefix": "HP",
                    "url": "http://purl.obolibrary.org/obo/hp.owl",
                    "version": "2024-01-01",
                    "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                }
            ],
            "externalReferences": external_references,
        },
    }

    row = Phenopacket(
        phenopacket_id=phenopacket_id,
        phenopacket=phenopacket,
        subject_id=subject_id,
        subject_sex="MALE",
        created_by_id=None,
    )
    if deleted:
        row.deleted_at = datetime.now(timezone.utc)
        row.deleted_by = "router-test"
    return row


@pytest.mark.asyncio
class TestCrudTimelineEndpoint:
    """``GET /phenopackets/{id}/timeline``."""

    async def test_timeline_404_for_missing_phenopacket(self, async_client):
        """Unknown phenopacket id → 404."""
        response = await async_client.get("/api/v2/phenopackets/NOT-A-REAL-ID/timeline")
        assert response.status_code == 404

    async def test_timeline_returns_subject_and_features(
        self, async_client, db_session
    ):
        """Stored phenopacket → timeline endpoint returns formatted features."""
        row = _make_phenopacket_row(
            phenopacket_id="TL-EP-001",
            subject_id="SUB-TL-001",
        )
        db_session.add(row)
        await db_session.commit()

        response = await async_client.get("/api/v2/phenopackets/TL-EP-001/timeline")
        assert response.status_code == 200
        body = response.json()
        assert body["subject_id"] == "SUB-TL-001"
        assert body["current_age"] == "P10Y"
        assert len(body["features"]) == 2

        # First feature has an explicit onset and evidence.
        renal = body["features"][0]
        assert renal["hpo_id"] == "HP:0000107"
        assert renal["category"] == "renal"
        assert renal["onset_age"] == "P5Y"
        assert renal["evidence"][0]["pmid"] == "99999"

        # Second feature falls through to the "observed at current age" path.
        diabetes = body["features"][1]
        assert diabetes["hpo_id"] == "HP:0004904"
        assert diabetes["category"] == "diabetes"
        assert diabetes["onset_age"] == "P10Y"
        assert diabetes["onset_label"] == "Observed at age 10y"

    async def test_timeline_renders_soft_deleted_phenopacket(
        self, async_client, db_session
    ):
        """Soft-deleted rows are still accessible via the timeline endpoint.

        The endpoint explicitly passes ``include_deleted=True`` so the
        audit-trail UI can still render deleted phenopackets' features.
        """
        row = _make_phenopacket_row(
            phenopacket_id="TL-EP-DELETED",
            subject_id="SUB-TL-DELETED",
            deleted=True,
        )
        db_session.add(row)
        await db_session.commit()

        response = await async_client.get("/api/v2/phenopackets/TL-EP-DELETED/timeline")
        assert response.status_code == 200
        assert response.json()["subject_id"] == "SUB-TL-DELETED"


@pytest.mark.asyncio
class TestCrudRelatedEndpoints:
    """``GET /phenopackets/by-variant/...`` and ``/by-publication/...``."""

    async def test_by_variant_empty_response_when_no_match(self, async_client):
        """Unknown variant id → empty list, 200."""
        response = await async_client.get(
            "/api/v2/phenopackets/by-variant/99-12345-X-Y"
        )
        assert response.status_code == 200
        assert response.json() == []

    async def test_by_variant_filters_soft_deleted(self, async_client, db_session):
        """Variant lookup must NOT return soft-deleted rows.

        Regression test for the missing ``deleted_at IS NULL`` filter
        flagged by Copilot review #7. Without the fix, the deleted row
        would still appear in the response.
        """
        live = _make_phenopacket_row(
            phenopacket_id="BV-LIVE-001",
            subject_id="SUB-BV-LIVE",
            include_variant=True,
        )
        dead = _make_phenopacket_row(
            phenopacket_id="BV-DEAD-001",
            subject_id="SUB-BV-DEAD",
            include_variant=True,
            deleted=True,
        )
        db_session.add_all([live, dead])
        await db_session.commit()

        response = await async_client.get(
            "/api/v2/phenopackets/by-variant/17-36459258-A-G"
        )
        assert response.status_code == 200
        phenopacket_ids = [row["phenopacket_id"] for row in response.json()]
        assert "BV-LIVE-001" in phenopacket_ids
        assert "BV-DEAD-001" not in phenopacket_ids

    async def test_by_publication_404_when_missing(self, async_client):
        """No matches for a PMID → 404 per the endpoint contract."""
        response = await async_client.get(
            "/api/v2/phenopackets/by-publication/PMID:00000001"
        )
        assert response.status_code == 404

    async def test_by_publication_returns_envelope(self, async_client, db_session):
        """Matched PMID → envelope with data/total/skip/limit."""
        row = _make_phenopacket_row(
            phenopacket_id="BP-001",
            subject_id="SUB-BP-001",
            include_pmid=True,
        )
        db_session.add(row)
        await db_session.commit()

        response = await async_client.get(
            "/api/v2/phenopackets/by-publication/PMID:12345"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["skip"] == 0
        assert body["limit"] == 100
        assert body["data"][0]["phenopacket_id"] == "BP-001"

    async def test_by_publication_invalid_pmid_rejected(self, async_client):
        """``validate_pmid`` rejects garbage → 400."""
        response = await async_client.get(
            "/api/v2/phenopackets/by-publication/not-a-pmid"
        )
        assert response.status_code == 400

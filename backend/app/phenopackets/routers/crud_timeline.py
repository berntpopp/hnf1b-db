"""Phenotype timeline endpoint for a single phenopacket.

Exposes ``GET /{phenopacket_id}/timeline``, returning a
visualisation-ready dict of the phenotypic features with their onset
ages and evidence links.

Extracted during Wave 4 from the monolithic ``crud.py`` — the feature
extraction logic dominates the old file and is self-contained, so
pulling it into its own module drops crud.py well under 500 LOC.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_optional_user, is_curator_or_admin
from app.database import get_db
from app.models.user import User
from app.phenopackets.models import Phenopacket
from app.phenopackets.repositories.visibility import (
    curator_filter,
    public_filter,
    resolve_curator_content,
    resolve_public_content,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["phenopackets-crud"])


def _extract_current_age(
    subject: Dict[str, Any],
) -> tuple[Optional[str], Optional[float]]:
    """Pull out the subject's current age string + parsed year count.

    Returns ``(iso8601_duration, age_in_years)``. Either may be
    ``None`` if the phenopacket omits ``timeAtLastEncounter.age``.
    """
    time_at_last = subject.get("timeAtLastEncounter")
    if not isinstance(time_at_last, dict):
        return None, None
    age_obj = time_at_last.get("age")
    if not isinstance(age_obj, dict):
        return None, None

    current_age = age_obj.get("iso8601duration")
    if not current_age:
        return None, None

    try:
        match = re.match(r"P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?", current_age)
        if match:
            years = int(match.group(1) or 0)
            months = int(match.group(2) or 0)
            days = int(match.group(3) or 0)
            return current_age, years + (months / 12) + (days / 365)
    except (ValueError, AttributeError):
        pass
    return current_age, None


def _extract_onset(
    feature: Dict[str, Any],
) -> tuple[Optional[str], Optional[str]]:
    """Pull out ``(onset_age_iso8601, onset_label)`` from one feature."""
    onset = feature.get("onset")
    if not onset:
        return None, None

    onset_age: Optional[str] = None
    onset_label: Optional[str] = None

    # Handle age field — can be string or object
    if "age" in onset:
        age_value = onset["age"]
        if isinstance(age_value, str):
            onset_age = age_value
        elif isinstance(age_value, dict):
            onset_age = age_value.get("iso8601duration")

    # Handle direct iso8601duration field (alternative format)
    if not onset_age and "iso8601duration" in onset:
        onset_age = onset["iso8601duration"]

    # Handle ontology class for categorical onset
    if "ontologyClass" in onset:
        onset_class = onset["ontologyClass"]
        if isinstance(onset_class, dict):
            onset_label = onset_class.get("label")

    return onset_age, onset_label


def _build_evidence_list(feature: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert a feature's ``evidence`` array into the timeline format."""
    evidence_list: List[Dict[str, Any]] = []
    for ev in feature.get("evidence", []):
        evidence_code = ev.get("evidenceCode", {})
        reference = ev.get("reference", {})

        evidence_item = {
            "evidence_code": evidence_code.get("label"),
            "pmid": None,
            "description": None,
            "recorded_at": None,
        }
        if reference:
            ref_id = reference.get("id", "")
            if ref_id.startswith("PMID:"):
                evidence_item["pmid"] = ref_id.replace("PMID:", "")
            evidence_item["description"] = reference.get("description")
            evidence_item["recorded_at"] = reference.get("recordedAt")

        evidence_list.append(evidence_item)
    return evidence_list


# Category membership, by exact HPO id -- not substring matching. Every id
# below was resolved live against https://ontology.jax.org/api/hp/terms/{id}
# (field ``name``) before being assigned; none were carried over from a
# previous comment or inferred from numeric proximity. The full id -> name
# resolution log lives in
# .superpowers/sdd/2026-07-30-ontology-data-quality/task-timeline-report.md.
#
# Built from a frequency count of every distinct stored
# ``phenotypicFeatures[].type.id`` in the dev corpus (36 distinct ids), so
# every recurring term gets a deliberate bucket instead of falling through
# to "other". A handful of ids below (HP:0000077, HP:0000080, HP:0000119,
# HP:0003111) have zero stored occurrences today but are kept for parity
# with the frontend's ``getOrganSystem`` (frontend/src/utils/ageParser.js)
# and because the previous test suite already pinned them.

_RENAL_IDS = frozenset(
    {
        "HP:0000107",  # Renal cyst
        "HP:0000003",  # Multicystic kidney dysplasia
        "HP:0000122",  # Unilateral renal agenesis
        "HP:0000089",  # Renal hypoplasia
        "HP:0033132",  # Renal cortical hyperechogenicity
        # Abnormality of the urinary system -- urinary tract, not genital.
        # The substring match this replaces mis-bucketed it as "genital"
        # (329 stored occurrences); the frontend made and then corrected the
        # identical mistake in ageParser.js (commits be491ca, dd80641), so
        # this keeps backend and frontend agreeing on the same id.
        "HP:0000079",
        "HP:0012210",  # Abnormal renal morphology
        "HP:0012622",  # Chronic kidney disease
        "HP:0012623",  # Stage 1 chronic kidney disease
        "HP:0012624",  # Stage 2 chronic kidney disease
        "HP:0012625",  # Stage 3 chronic kidney disease
        "HP:0003774",  # Stage 5 chronic kidney disease
        "HP:0012626",  # Stage 4 chronic kidney disease
        "HP:0100611",  # Multiple glomerular cysts
        "HP:0000077",  # Abnormality of the kidney (not in current corpus)
        # Abnormality of the genitourinary system -- genuinely ambiguous,
        # spans both renal and genital tracts. Bucketed as renal to agree
        # with the frontend's getOrganSystem, which classifies it renal via
        # its 77-140 numeric range (it is not carved out the way HP:0000078
        # / HP:0000080 are). Not in the current corpus.
        "HP:0000119",
    }
)

_GENITAL_IDS = frozenset(
    {
        "HP:0000078",  # Abnormality of the genital system
        "HP:0000080",  # Abnormality of reproductive system physiology
        #                 (not in current corpus)
    }
)

_DIABETES_IDS = frozenset(
    {
        "HP:0004904",  # Maturity-onset diabetes of the young
        # Pancreatic hypoplasia / exocrine pancreatic insufficiency are
        # grouped into the same bucket as MODY: in HNF1B disease biology all
        # three are manifestations of one underlying pancreatic
        # developmental defect, not independent findings.
        "HP:0002594",  # Pancreatic hypoplasia
        "HP:0001738",  # Exocrine pancreatic insufficiency
    }
)

_METABOLIC_IDS = frozenset(
    {
        # Abnormal circulating electrolyte concentration -- an
        # electrolyte/metabolic lab finding, not itself a renal structural
        # or functional diagnosis. The substring match this replaces put it
        # in "renal"; not in the current corpus.
        "HP:0003111",
        "HP:0002149",  # Hyperuricemia
        "HP:0002917",  # Hypomagnesemia
        "HP:0002900",  # Hypokalemia
        "HP:0000843",  # Hyperparathyroidism (calcium/phosphate metabolism)
        "HP:0001997",  # Gout (urate metabolism/deposition disorder)
    }
)

_NEURO_IDS = frozenset(
    {
        "HP:0012758",  # Neurodevelopmental delay
        "HP:0000708",  # Atypical behavior
        "HP:0001250",  # Seizure
        "HP:0012443",  # Abnormal brain morphology
    }
)

_HEPATIC_IDS = frozenset(
    {
        "HP:0002910",  # Elevated circulating hepatic transaminase
        #                 concentration
        "HP:0031865",  # Abnormal liver physiology
    }
)


def _categorise_feature(hpo_id: Optional[str]) -> str:
    """Bucket a feature into a coarse category for the timeline UI.

    Uses exact set membership, not substring matching -- ``"HP:0000079" in
    hpo_id`` is a fragile test on the id *string* and a latent source of
    false positives/negatives. See the module-level comment above the
    category sets for how each id was resolved and why it landed where it
    did.
    """
    if not hpo_id:
        return "other"
    if hpo_id in _RENAL_IDS:
        return "renal"
    if hpo_id in _GENITAL_IDS:
        return "genital"
    if hpo_id in _DIABETES_IDS:
        return "diabetes"
    if hpo_id in _METABOLIC_IDS:
        return "metabolic"
    if hpo_id in _NEURO_IDS:
        return "neuro"
    if hpo_id in _HEPATIC_IDS:
        return "hepatic"
    return "other"


@router.get("/{phenopacket_id}/timeline", response_model=Dict[str, Any])
async def get_phenotype_timeline(
    phenopacket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Return a timeline-ready view of a phenopacket's phenotypic features.

    The response shape is unchanged from the pre-Wave-4 flat router:
    ``{"subject_id": ..., "current_age": ..., "features": [...]}``.

    Public callers only see published head content. Curators/admins can
    inspect the working copy allowed by the standard curator visibility
    filter, but soft-deleted rows are hidden here just like they are on the
    detail and list endpoints.
    """
    is_curator = is_curator_or_admin(current_user)
    stmt = (
        select(Phenopacket)
        .where(Phenopacket.phenopacket_id == phenopacket_id)
        .options(
            selectinload(Phenopacket.created_by_user),
            selectinload(Phenopacket.updated_by_user),
            selectinload(Phenopacket.deleted_by_user),
            selectinload(Phenopacket.draft_owner),
            selectinload(Phenopacket.editing_revision),
        )
    )
    if is_curator:
        stmt = curator_filter(stmt)
    else:
        stmt = public_filter(stmt)

    result = await db.execute(stmt)
    phenopacket_record = result.scalar_one_or_none()
    if phenopacket_record is None:
        raise HTTPException(
            status_code=404, detail=f"Phenopacket '{phenopacket_id}' not found"
        )

    phenopacket_data: Dict[str, Any]
    if is_curator:
        phenopacket_data = resolve_curator_content(phenopacket_record)
    else:
        public_content = await resolve_public_content(db, phenopacket_record)
        if public_content is None:
            raise HTTPException(
                status_code=404,
                detail=f"Phenopacket '{phenopacket_id}' not found",
            )
        phenopacket_data = public_content

    subject = phenopacket_data.get("subject", {})
    subject_id = subject.get("id")

    current_age, current_age_years = _extract_current_age(subject)

    features: List[Dict[str, Any]] = []
    for feature in phenopacket_data.get("phenotypicFeatures", []):
        feature_type = feature.get("type", {})
        hpo_id = feature_type.get("id")
        label = feature_type.get("label", "Unknown")

        onset_age, onset_label = _extract_onset(feature)

        # If no onset specified but feature is not excluded, use the
        # subject's current age as the observation/report age. This
        # represents when the feature was observed, not necessarily
        # when it began.
        if not onset_age and not onset_label and not feature.get("excluded", False):
            if current_age:
                onset_age = current_age
                if current_age_years:
                    onset_label = f"Observed at age {int(current_age_years)}y"
                else:
                    onset_label = "Observed"

        severity: Optional[str] = None
        severity_obj = feature.get("severity")
        if isinstance(severity_obj, dict):
            severity = severity_obj.get("label")

        features.append(
            {
                "hpo_id": hpo_id,
                "label": label,
                "onset_age": onset_age,
                "onset_label": onset_label,
                "category": _categorise_feature(hpo_id),
                "severity": severity,
                "excluded": feature.get("excluded", False),
                "evidence": _build_evidence_list(feature),
            }
        )

    return {
        "subject_id": subject_id,
        "current_age": current_age,
        "features": features,
    }

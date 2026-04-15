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
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_optional_user, is_curator_or_admin
from app.database import get_db
from app.models.user import User
from app.phenopackets.repositories import PhenopacketRepository
from app.phenopackets.repositories.visibility import (
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


def _categorise_feature(hpo_id: Optional[str]) -> str:
    """Bucket a feature into a coarse category for the timeline UI."""
    if not hpo_id:
        return "other"
    if any(x in hpo_id for x in ["HP:0000107", "HP:0003111"]):
        return "renal"
    if "HP:0004904" in hpo_id:
        return "diabetes"
    if "HP:0000079" in hpo_id or "HP:0000119" in hpo_id:
        return "genital"
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
    inspect the working copy, including soft-deleted rows, so the timeline
    remains usable for audit and review flows.
    """
    repo = PhenopacketRepository(db)
    is_curator = is_curator_or_admin(current_user)
    phenopacket_record = await repo.get_by_id(
        phenopacket_id, include_deleted=is_curator
    )
    if phenopacket_record is None:
        raise HTTPException(
            status_code=404, detail=f"Phenopacket '{phenopacket_id}' not found"
        )

    phenopacket_data: Optional[Dict[str, Any]]
    if is_curator:
        phenopacket_data = resolve_curator_content(phenopacket_record)
    else:
        # Public / viewer callers must obey the published-only visibility
        # model used by the main detail and list routes.
        if (
            phenopacket_record.state != "published"
            or phenopacket_record.head_published_revision_id is None
        ):
            raise HTTPException(
                status_code=404,
                detail=f"Phenopacket '{phenopacket_id}' not found",
            )
        phenopacket_data = await resolve_public_content(db, phenopacket_record)
        if phenopacket_data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Phenopacket '{phenopacket_id}' not found",
            )

    if phenopacket_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Phenopacket '{phenopacket_id}' not found",
        )

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

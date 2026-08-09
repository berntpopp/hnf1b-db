"""Database-backed validation for curated fields.

Reference-table membership and per-term laterality both require lookups, so
they cannot live in the synchronous ``Draft7Validator`` in ``schema_validator``.
This validator runs on the REST write path only (spec §4.5): of the four
writers, the two maintenance scripts cannot produce these fields, and bulk
import is a documented trusted caller.

Also folds in the ontology data-quality plan's Task 7 Step 1 requirement: the
laterality check alone only asks "is this modifier permitted for this term?"
— it would happily accept ``HP:0033133`` mislabeled "hyperechogenicity",
which is the original defect this codebase shipped with
(docs/ontology-defect-report-2026-07-30.md). ``check_label`` (A3,
``app/ontology/conformance.py``) closes that gap by rejecting a stored
``(id, label)`` pair whose label disagrees with the id's pinned canonical
name/synonyms.

Deliberately scoped to the same features ``_validate_laterality`` already
looks at (those carrying ``modifiers``), not every ``phenotypicFeatures``
entry in the document. ``check_label``'s pinned snapshot
(``app/ontology/data/ontology_snapshot.json``) is a narrow, curated
vocabulary built for the migration importer's provenance check — not the
full HPO — so applying it to every phenotype a curator submits would reject
legitimate curation of any HPO term outside that fixed list. Restricting it
to laterality-bearing features keeps it inside the vocabulary the snapshot
was actually built to cover while still closing the exact gap described
above. It is intentionally insufficient on its own even there — a wrong id
paired with *its own* canonical label still passes — but it is real, cheap
protection against typos and copy-paste id/label mismatches on the terms
this validator already touches.
"""

from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ontology.conformance import check_label

# These are the stable ontology identifiers enforced for curator-authored
# documents. They are deliberately separate from the importer's source-owned
# ``Phenotype_modifier`` vocabulary, which has no hardcoded fallback.
BILATERAL = "HP:0012832"
UNILATERAL = "HP:0012833"
LEFT = "HP:0012835"
RIGHT = "HP:0012834"
_SIDED = {UNILATERAL, LEFT, RIGHT}


def _as_list(value: Any) -> List[Any]:
    """Return ``value`` if it is a list, else an empty list.

    Curated JSONB reaches this module before the schema constrains these
    sub-structures, so a scalar where a list belongs must degrade to "nothing to
    check" rather than raising.
    """
    return value if isinstance(value, list) else []


# hnf1bCuration field -> reference table backing it.
_CURATION_FIELDS = {
    "cohort": "cohort_values",
    "familyHistory": "family_history_values",
    "detectionMethod": "detection_method_values",
}


class DomainValidator:
    """Validate curated values against reference data."""

    def __init__(self, db: AsyncSession) -> None:
        """Wire the validator to the async session used for reference lookups."""
        self._db = db

    async def validate(self, phenopacket: Dict[str, Any]) -> List[str]:
        """Return human-readable problems; empty list means valid."""
        errors: List[str] = []
        errors.extend(await self._validate_curation(phenopacket))
        errors.extend(await self._validate_segregation(phenopacket))
        errors.extend(await self._validate_laterality(phenopacket))
        return errors

    async def _allowed(self, table: str) -> List[str]:
        result = await self._db.execute(
            text(f"SELECT value FROM {table} ORDER BY sort_order")  # noqa: S608
        )
        return [row[0] for row in result.fetchall()]

    async def _validate_curation(self, phenopacket: Dict[str, Any]) -> List[str]:
        block = phenopacket.get("hnf1bCuration") or {}
        errors = []
        for field, table in _CURATION_FIELDS.items():
            value = block.get(field)
            if value is None:
                continue
            allowed = await self._allowed(table)
            if value not in allowed:
                errors.append(
                    f"hnf1bCuration.{field}: {value!r} is not a valid value. "
                    f"Allowed: {', '.join(allowed)}"
                )
        return errors

    async def _validate_segregation(self, phenopacket: Dict[str, Any]) -> List[str]:
        """Collect segregation origins, tolerating malformed input.

        The JSON schema does not declare ``variationDescriptor.extensions`` or its
        value shape, so a string, a list, or a missing ``origin`` all reach this
        method. Every access is type-checked: an ``AttributeError`` here would
        surface as HTTP 500 instead of the 400 the contract promises.
        """
        errors: List[str] = []
        origins: List[Any] = []

        for interp in _as_list(phenopacket.get("interpretations")):
            diagnosis = interp.get("diagnosis") if isinstance(interp, dict) else None
            genomic = _as_list((diagnosis or {}).get("genomicInterpretations"))
            for gi in genomic:
                if not isinstance(gi, dict):
                    continue
                vi = gi.get("variantInterpretation")
                descriptor = (
                    (vi or {}).get("variationDescriptor")
                    if isinstance(vi, dict)
                    else None
                )
                for ext in _as_list((descriptor or {}).get("extensions")):
                    if not isinstance(ext, dict) or ext.get("name") != "segregation":
                        continue
                    value = ext.get("value")
                    if not isinstance(value, dict):
                        errors.append(
                            "segregation: extension value must be an object with an "
                            f"'origin' key, got {type(value).__name__}"
                        )
                        continue
                    origins.append(value.get("origin"))

        stated = [o for o in origins if o is not None]
        if not stated:
            return errors

        allowed = await self._allowed("segregation_values")
        errors.extend(
            f"segregation.origin: {origin!r} is not a valid value. "
            f"Allowed: {', '.join(allowed)}"
            for origin in stated
            if origin not in allowed
        )
        return errors

    async def _validate_laterality(self, phenopacket: Dict[str, Any]) -> List[str]:
        features = _as_list(phenopacket.get("phenotypicFeatures"))
        with_modifiers = [
            f for f in features if isinstance(f, dict) and f.get("modifiers")
        ]
        if not with_modifiers:
            return []

        errors = self._check_labels(with_modifiers)

        annotated = [
            (
                f.get("type", {}).get("id"),
                [m.get("id") for m in (f.get("modifiers") or [])],
            )
            for f in with_modifiers
        ]

        result = await self._db.execute(
            text(
                "SELECT hpo_id, allowed_modifiers FROM hpo_terms_lookup "
                "WHERE hpo_id = ANY(:ids)"
            ),
            {"ids": [hpo_id for hpo_id, _ in annotated]},
        )
        policy = {row[0]: set(row[1] or []) for row in result.fetchall()}

        for hpo_id, modifiers in annotated:
            allowed = policy.get(hpo_id, set())
            applied = set(modifiers)

            if BILATERAL in applied and applied & _SIDED:
                conflicting = ", ".join(sorted(applied & _SIDED))
                errors.append(
                    f"{hpo_id}: {BILATERAL} (Bilateral) cannot be combined with "
                    f"{conflicting}"
                )
                continue

            outside = applied - allowed
            if outside:
                allowed_text = ", ".join(sorted(allowed)) if allowed else "none"
                outside_text = ", ".join(sorted(outside))
                errors.append(
                    f"{hpo_id}: modifier(s) {outside_text} not permitted. "
                    f"Allowed: {allowed_text}"
                )
        return errors

    def _check_labels(self, features_with_modifiers: List[Dict[str, Any]]) -> List[str]:
        """Reject a laterality-bearing phenotype whose label disagrees with its id.

        Ontology data-quality plan, Task 7 Step 1: the modifier-permission
        check above only asks "is this modifier permitted for this term?" —
        it would happily accept ``HP:0033133`` mislabeled
        "hyperechogenicity", which is the original T1 defect. This walks
        each already-selected feature's ``type`` and ``modifiers[]`` ontology
        classes and runs ``check_label`` (A3) on any that carry a label, so a
        wrong identifier cannot enter through the curation form for the
        laterality-bearing terms this validator already covers.

        A term with no ``label`` key is not flagged — ``label`` is optional
        per the schema, and an id-only submission states nothing A3 can
        check. Synchronous: ``check_label`` only consults the pinned
        ontology snapshot, not the database.
        """
        errors: List[str] = []
        for feature in features_with_modifiers:
            classes: List[Any] = []
            type_ = feature.get("type")
            if isinstance(type_, dict):
                classes.append(type_)
            classes.extend(
                m for m in _as_list(feature.get("modifiers")) if isinstance(m, dict)
            )
            for ontology_class in classes:
                term_id = ontology_class.get("id")
                label = ontology_class.get("label")
                if not term_id or not label:
                    continue
                violation = check_label(term_id, label)
                if violation:
                    errors.append(violation)
        return errors

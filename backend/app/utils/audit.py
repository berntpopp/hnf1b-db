"""Audit trail utilities for phenopacket change tracking.

Provides centralized functions for creating audit entries with JSON Patch
support and human-readable change summaries.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import jsonpatch  # type: ignore[import-untyped]
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.phenopackets.models import PhenopacketAudit


async def create_audit_entry(
    db: AsyncSession,
    phenopacket_id: str,
    action: str,
    old_value: Optional[Dict[str, Any]],
    new_value: Optional[Dict[str, Any]],
    changed_by: str,
    change_reason: str,
) -> PhenopacketAudit:
    """Create audit trail entry for phenopacket change.

    Args:
        db: Database session
        phenopacket_id: ID of the phenopacket being changed
        action: Action type (CREATE, UPDATE, DELETE)
        old_value: Previous phenopacket state (None for CREATE)
        new_value: New phenopacket state (None for DELETE)
        changed_by: Username who made the change
        change_reason: Human-readable reason for the change

    Returns:
        Created PhenopacketAudit instance

    Raises:
        ValueError: If action is invalid or required fields missing
    """
    # Validate action
    valid_actions = {"CREATE", "UPDATE", "DELETE"}
    if action not in valid_actions:
        raise ValueError(f"Invalid action '{action}'. Must be one of {valid_actions}")

    # Generate JSON Patch for UPDATE actions
    change_patch = None
    if action == "UPDATE" and old_value and new_value:
        change_patch = generate_json_patch(old_value, new_value)

    # Generate human-readable summary
    change_summary = generate_change_summary(action, old_value, new_value)

    # Create audit entry using raw SQL for consistency
    query = text("""
        INSERT INTO phenopacket_audit
        (id, phenopacket_id, action, old_value, new_value, changed_by,
         change_reason, change_patch, change_summary, changed_at)
        VALUES (gen_random_uuid(), :phenopacket_id, :action, :old_value,
                :new_value, :changed_by, :change_reason, :change_patch,
                :change_summary, :changed_at)
        RETURNING id
    """)

    result = await db.execute(
        query,
        {
            "phenopacket_id": phenopacket_id,
            "action": action,
            "old_value": json.dumps(old_value) if old_value else None,
            "new_value": json.dumps(new_value) if new_value else None,
            "changed_by": changed_by,
            "change_reason": change_reason,
            "change_patch": json.dumps(change_patch) if change_patch else None,
            "change_summary": change_summary,
            "changed_at": datetime.now(timezone.utc),
        },
    )

    audit_id = result.scalar_one()

    # Fetch and return the created audit entry
    fetch_query = text("""
        SELECT * FROM phenopacket_audit WHERE id = :audit_id
    """)
    audit_result = await db.execute(fetch_query, {"audit_id": audit_id})
    audit_row = audit_result.fetchone()

    assert audit_row is not None, "Failed to create audit entry"

    # Map to PhenopacketAudit model
    return PhenopacketAudit(
        id=audit_row.id,
        phenopacket_id=audit_row.phenopacket_id,
        action=audit_row.action,
        old_value=audit_row.old_value,
        new_value=audit_row.new_value,
        changed_by=audit_row.changed_by,
        changed_at=audit_row.changed_at,
        change_reason=audit_row.change_reason,
        change_patch=audit_row.change_patch,
        change_summary=audit_row.change_summary,
    )


def generate_json_patch(
    old: Dict[str, Any], new: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Generate RFC 6902 JSON Patch between two phenopackets.

    Args:
        old: Original phenopacket dictionary
        new: Updated phenopacket dictionary

    Returns:
        List of JSON Patch operations

    Example:
        >>> old = {"subject": {"id": "1", "sex": "MALE"}}
        >>> new = {"subject": {"id": "1", "sex": "FEMALE"}}
        >>> generate_json_patch(old, new)
        [{'op': 'replace', 'path': '/subject/sex', 'value': 'FEMALE'}]
    """
    patch = jsonpatch.make_patch(old, new)
    return list(patch)  # Convert to list of dicts


def generate_change_summary(
    action: str,
    old_value: Optional[Dict[str, Any]],
    new_value: Optional[Dict[str, Any]],
) -> str:
    """Generate human-readable summary of changes.

    Args:
        action: Action type (CREATE, UPDATE, DELETE)
        old_value: Previous phenopacket state
        new_value: New phenopacket state

    Returns:
        Human-readable summary string

    Examples:
        CREATE: "Initial import: 8 phenotype(s), 1 variant(s)"
        UPDATE: "Updated 3 phenotype(s), added 1 variant, changed sex to FEMALE"
        DELETE: "Soft deleted phenopacket"
    """
    if action == "CREATE":
        return _generate_create_summary(new_value)
    elif action == "UPDATE":
        return _generate_update_summary(old_value, new_value)
    elif action == "DELETE":
        return "Soft deleted phenopacket"
    else:
        return f"Unknown action: {action}"


def _generate_create_summary(phenopacket: Optional[Dict[str, Any]]) -> str:
    """Generate summary for CREATE action."""
    if not phenopacket:
        return "Created phenopacket"

    phenotypes_count = len(phenopacket.get("phenotypicFeatures", []))
    variants_count = len(phenopacket.get("interpretations", []))

    return (
        f"Initial import: {phenotypes_count} phenotype(s), {variants_count} variant(s)"
    )


def _generate_update_summary(
    old: Optional[Dict[str, Any]], new: Optional[Dict[str, Any]]
) -> str:
    """Generate summary for UPDATE action."""
    if not old or not new:
        return "Updated phenopacket"

    changes = []

    # Check phenotypic features
    old_phenotypes = old.get("phenotypicFeatures", [])
    new_phenotypes = new.get("phenotypicFeatures", [])
    if len(new_phenotypes) != len(old_phenotypes):
        delta = len(new_phenotypes) - len(old_phenotypes)
        if delta > 0:
            changes.append(f"added {delta} phenotype(s)")
        else:
            changes.append(f"removed {abs(delta)} phenotype(s)")

    # Check interpretations (variants)
    old_variants = old.get("interpretations", [])
    new_variants = new.get("interpretations", [])
    if len(new_variants) != len(old_variants):
        delta = len(new_variants) - len(old_variants)
        if delta > 0:
            changes.append(f"added {delta} variant(s)")
        else:
            changes.append(f"removed {abs(delta)} variant(s)")

    # Check subject sex change
    old_sex = old.get("subject", {}).get("sex")
    new_sex = new.get("subject", {}).get("sex")
    if old_sex != new_sex:
        changes.append(f"changed sex to {new_sex}")

    # Check diseases
    old_diseases = old.get("diseases", [])
    new_diseases = new.get("diseases", [])
    if len(new_diseases) != len(old_diseases):
        delta = len(new_diseases) - len(old_diseases)
        if delta > 0:
            changes.append(f"added {delta} disease(s)")
        else:
            changes.append(f"removed {abs(delta)} disease(s)")

    if changes:
        return "Updated: " + ", ".join(changes)
    else:
        return "Updated phenopacket metadata"


def compare_phenopackets(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Deep comparison of two phenopackets for conflict detection.

    Args:
        old: Original phenopacket
        new: Updated phenopacket

    Returns:
        Dictionary with comparison results:
        - has_conflicts: Boolean
        - conflicts: List of conflict descriptions
        - patch: JSON Patch operations

    Example:
        >>> result = compare_phenopackets(old_pp, new_pp)
        >>> if result["has_conflicts"]:
        ...     print(f"Conflicts detected: {result['conflicts']}")
    """
    patch = generate_json_patch(old, new)

    # Detect structural conflicts
    conflicts = []

    # Check for conflicting field updates
    paths_modified = {
        op["path"] for op in patch if op.get("op") in ["replace", "remove"]
    }

    # Critical fields that indicate conflicts
    critical_paths = {
        "/subject/sex",
        "/subject/id",
        "/metaData/phenopacketSchemaVersion",
    }

    critical_conflicts = paths_modified & critical_paths
    if critical_conflicts:
        conflicts.extend(
            [f"Modified critical field: {path}" for path in critical_conflicts]
        )

    return {
        "has_conflicts": len(conflicts) > 0,
        "conflicts": conflicts,
        "patch": patch,
        "patch_count": len(patch),
    }

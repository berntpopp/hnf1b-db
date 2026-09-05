"""Pure review-context transformations independent of database access."""

from __future__ import annotations

from typing import Any, cast

from app.phenopackets.review.schemas import SemanticChange, SemanticSection

_MISSING = object()
_SECTION_ROOTS: tuple[tuple[SemanticSection, tuple[str, ...]], ...] = (
    ("Subject", ("subject",)),
    ("Phenotypes", ("phenotypicFeatures", "phenotypic_features")),
    ("Diseases", ("diseases",)),
    (
        "Variants/Interpretations",
        ("interpretations", "variants", "variantInterpretations"),
    ),
    ("Measurements", ("measurements",)),
)


def _escape_pointer(value: str) -> str:
    """Escape one RFC 6901 path segment."""
    return value.replace("~", "~0").replace("/", "~1")


def _identity(value: Any) -> str | None:
    """Return a stable clinical identity for common Phenopacket list items."""
    if not isinstance(value, dict):
        return None
    direct = value.get("id")
    if isinstance(direct, str):
        return direct
    # For genomicInterpretations or variantInterpretations with variationDescriptor:
    var_desc = value.get("variationDescriptor")
    if isinstance(var_desc, dict) and isinstance(var_desc.get("id"), str):
        return cast(str, var_desc["id"])
    var_interp = value.get("variantInterpretation")
    if isinstance(var_interp, dict):
        if isinstance(var_interp.get("id"), str):
            return cast(str, var_interp["id"])
        nested_desc = var_interp.get("variationDescriptor")
        if isinstance(nested_desc, dict) and isinstance(nested_desc.get("id"), str):
            return cast(str, nested_desc["id"])
    for key in ("type", "term", "measurement"):
        nested = value.get(key)
        if isinstance(nested, dict) and isinstance(nested.get("id"), str):
            return cast(str, nested["id"])
    return None


class ReviewService:
    """Build deterministic, clinically grouped candidate comparisons."""

    @classmethod
    def semantic_changes(
        cls,
        baseline: dict[str, Any] | None,
        candidate: dict[str, Any],
    ) -> list[SemanticChange]:
        """Compare an immutable public head with an exact candidate snapshot."""
        if baseline is None:
            return cls._new_record_changes(candidate)

        changes: list[SemanticChange] = []
        handled: set[str] = set()
        for section, roots in _SECTION_ROOTS:
            for root in roots:
                if root not in baseline and root not in candidate:
                    continue
                handled.add(root)
                changes.extend(
                    cls._diff(
                        baseline.get(root, _MISSING),
                        candidate.get(root, _MISSING),
                        f"/{_escape_pointer(root)}",
                        section,
                    )
                )

        metadata_keys = sorted((set(baseline) | set(candidate)) - handled)
        for key in metadata_keys:
            changes.extend(
                cls._diff(
                    baseline.get(key, _MISSING),
                    candidate.get(key, _MISSING),
                    f"/{_escape_pointer(key)}",
                    "Metadata",
                )
            )
        return changes

    @staticmethod
    def _new_record_changes(candidate: dict[str, Any]) -> list[SemanticChange]:
        """Render every candidate section as added when no public head exists."""
        changes: list[SemanticChange] = []
        handled: set[str] = set()
        for section, roots in _SECTION_ROOTS:
            for root in roots:
                if root not in candidate:
                    continue
                handled.add(root)
                changes.append(
                    SemanticChange(
                        section=section,
                        operation="added",
                        path=f"/{_escape_pointer(root)}",
                        before=None,
                        after=candidate[root],
                    )
                )
        for key in sorted(set(candidate) - handled):
            changes.append(
                SemanticChange(
                    section="Metadata",
                    operation="added",
                    path=f"/{_escape_pointer(key)}",
                    before=None,
                    after=candidate[key],
                )
            )
        return changes

    @classmethod
    def _diff(
        cls,
        before: Any,
        after: Any,
        path: str,
        section: SemanticSection,
    ) -> list[SemanticChange]:
        """Recursively emit literal add/remove/change operations."""
        if before is _MISSING:
            if isinstance(after, list):
                return [
                    SemanticChange(
                        section=section,
                        operation="added",
                        path=f"{path}/{index}",
                        before=None,
                        after=value,
                    )
                    for index, value in enumerate(after)
                ]
            return [
                SemanticChange(
                    section=section,
                    operation="added",
                    path=path,
                    before=None,
                    after=after,
                )
            ]
        if after is _MISSING:
            if isinstance(before, list):
                return [
                    SemanticChange(
                        section=section,
                        operation="removed",
                        path=f"{path}/{index}",
                        before=value,
                        after=None,
                    )
                    for index, value in enumerate(before)
                ]
            return [
                SemanticChange(
                    section=section,
                    operation="removed",
                    path=path,
                    before=before,
                    after=None,
                )
            ]
        if before == after:
            return []
        if isinstance(before, dict) and isinstance(after, dict):
            changes: list[SemanticChange] = []
            for key in sorted(set(before) | set(after)):
                changes.extend(
                    cls._diff(
                        before.get(key, _MISSING),
                        after.get(key, _MISSING),
                        f"{path}/{_escape_pointer(key)}",
                        section,
                    )
                )
            return changes
        if isinstance(before, list) and isinstance(after, list):
            return cls._diff_list(before, after, path, section)
        return [
            SemanticChange(
                section=section,
                operation="changed",
                path=path,
                before=before,
                after=after,
            )
        ]

    @classmethod
    def _diff_list(
        cls,
        before: list[Any],
        after: list[Any],
        path: str,
        section: SemanticSection,
    ) -> list[SemanticChange]:
        """Compare identity-bearing arrays without treating reordering as edits."""
        before_ids = [_identity(item) for item in before]
        after_ids = [_identity(item) for item in after]
        identity_aware = (
            all(item is not None for item in before_ids + after_ids)
            and len(set(before_ids)) == len(before_ids)
            and len(set(after_ids)) == len(after_ids)
        )
        if not identity_aware:
            changes: list[SemanticChange] = []
            for index in range(max(len(before), len(after))):
                changes.extend(
                    cls._diff(
                        before[index] if index < len(before) else _MISSING,
                        after[index] if index < len(after) else _MISSING,
                        f"{path}/{index}",
                        section,
                    )
                )
            return changes

        typed_before_ids = cast(list[str], before_ids)
        typed_after_ids = cast(list[str], after_ids)
        before_by_id = dict(zip(typed_before_ids, before))
        after_by_id = dict(zip(typed_after_ids, after))
        after_index = {
            identity: index for index, identity in enumerate(typed_after_ids)
        }
        before_index = {
            identity: index for index, identity in enumerate(typed_before_ids)
        }
        changes = []
        for identity in typed_before_ids:
            if identity in after_by_id:
                changes.extend(
                    cls._diff(
                        before_by_id[identity],
                        after_by_id[identity],
                        f"{path}/{after_index[identity]}",
                        section,
                    )
                )
        for identity in typed_before_ids:
            if identity not in after_by_id:
                changes.append(
                    SemanticChange(
                        section=section,
                        operation="removed",
                        path=f"{path}/{before_index[identity]}",
                        before=before_by_id[identity],
                        after=None,
                    )
                )
        for identity in typed_after_ids:
            if identity not in before_by_id:
                changes.append(
                    SemanticChange(
                        section=section,
                        operation="added",
                        path=f"{path}/{after_index[identity]}",
                        before=None,
                        after=after_by_id[identity],
                    )
                )
        return changes

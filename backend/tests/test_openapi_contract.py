"""Contract tests pinning the OpenAPI schema and variant vocabulary enums.

These tests prove the coupling between the FastAPI source of truth and the
committed OpenAPI snapshot consumed by the sibling ``mcp/`` package:

* :func:`test_openapi_snapshot_matches_live` fails if the live schema drifts
  from the committed snapshot — forcing a refresh via ``scripts/dump_openapi.py``
  whenever any vocabulary (or any other part of the API) changes.
* :func:`test_variant_vocab_params_are_enums` fails if the four variant filter
  params on ``/all-variants`` stop being enums or expose unexpected values,
  guarding the DRY single-source-of-truth pattern.

No database is required: ``app.openapi()`` is computed purely from route
definitions.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.main import app
from app.phenopackets.variant_vocab import (
    MolecularConsequence,
    ProteinDomain,
    VariantClassification,
    VariantType,
)

# tests/ -> backend/ -> repo root -> mcp/contract/openapi.snapshot.json
SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "mcp"
    / "contract"
    / "openapi.snapshot.json"
)

ALL_VARIANTS_PATH = "/api/v2/phenopackets/aggregate/all-variants"
COMMENT_RESOLVE_PATH = "/api/v2/comments/{comment_id}/resolve"
COMMENT_UNRESOLVE_PATH = "/api/v2/comments/{comment_id}/unresolve"
REVIEW_QUEUE_PATH = "/api/v2/phenopackets/review-queue"
REVIEW_CONTEXT_PATH = "/api/v2/phenopackets/{record_id}/review-context"


def _live_openapi() -> Dict[str, Any]:
    """Return the live OpenAPI schema as deterministic round-tripped JSON.

    Round-tripping through ``json.dumps(..., sort_keys=True)`` mirrors exactly
    what ``scripts/dump_openapi.py`` writes, so equality comparison is stable.
    """
    return json.loads(json.dumps(app.openapi(), sort_keys=True))


def test_openapi_snapshot_matches_live() -> None:
    """The committed snapshot must equal the live ``app.openapi()`` schema."""
    assert SNAPSHOT_PATH.exists(), (
        f"Missing OpenAPI snapshot at {SNAPSHOT_PATH}. "
        "Run scripts/dump_openapi.py to refresh "
        "mcp/contract/openapi.snapshot.json"
    )
    committed = json.loads(SNAPSHOT_PATH.read_text())
    live = _live_openapi()
    assert committed == live, (
        "OpenAPI schema drifted from the committed snapshot. "
        "Run scripts/dump_openapi.py to refresh "
        "mcp/contract/openapi.snapshot.json"
    )


def _resolve_enum(
    schema: Dict[str, Any], components: Dict[str, Any]
) -> Optional[List[Any]]:
    """Resolve a param schema (incl. Optional / $ref) to its enum list, if any."""
    if "enum" in schema:
        return schema["enum"]
    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        return components.get(ref_name, {}).get("enum")
    for combinator in ("anyOf", "allOf", "oneOf"):
        for sub in schema.get(combinator, []):
            resolved = _resolve_enum(sub, components)
            if resolved is not None:
                return resolved
    return None


def test_variant_vocab_params_are_enums() -> None:
    """The four variant filter params expose enums with the expected values."""
    spec = app.openapi()
    operation = spec["paths"][ALL_VARIANTS_PATH]["get"]
    components = spec.get("components", {}).get("schemas", {})

    params_by_name = {p["name"]: p for p in operation["parameters"]}

    expected = {
        "classification": [e.value for e in VariantClassification],
        "consequence": [e.value for e in MolecularConsequence],
        "variant_type": [e.value for e in VariantType],
        "domain": [e.value for e in ProteinDomain],
    }

    for name, expected_values in expected.items():
        assert name in params_by_name, (
            f"Missing query param {name!r} on {ALL_VARIANTS_PATH}"
        )
        enum_values = _resolve_enum(params_by_name[name]["schema"], components)
        assert enum_values is not None, (
            f"Param {name!r} is no longer an enum in the OpenAPI schema; "
            "it must stay enum-typed for the DRY vocabulary contract."
        )
        assert enum_values == expected_values, (
            f"Enum values for {name!r} drifted: {enum_values!r} != {expected_values!r}"
        )


def _schema_refs(schema: Dict[str, Any]) -> set[str]:
    refs = set()
    if "$ref" in schema:
        refs.add(schema["$ref"].split("/")[-1])
    for value in schema.values():
        if isinstance(value, dict):
            refs.update(_schema_refs(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    refs.update(_schema_refs(item))
    return refs


def _json_request_schema(operation: Dict[str, Any]) -> Dict[str, Any]:
    request_body = operation["requestBody"]
    assert not request_body.get("required", False)
    return request_body["content"]["application/json"]["schema"]


def test_comment_resolution_request_bodies_document_conditional_issue_inputs() -> None:
    """Resolve routes advertise blocking-issue schemas without requiring a body."""
    spec = app.openapi()

    resolve_schema = _json_request_schema(spec["paths"][COMMENT_RESOLVE_PATH]["post"])
    unresolve_schema = _json_request_schema(
        spec["paths"][COMMENT_UNRESOLVE_PATH]["post"]
    )

    assert "ReviewIssueResolveRequest" in _schema_refs(resolve_schema)
    assert "ReviewIssueReopenRequest" in _schema_refs(unresolve_schema)


def test_review_routes_and_comment_issue_fields_are_typed() -> None:
    """Review transport is explicit in OpenAPI rather than an ad hoc dict surface."""
    spec = app.openapi()
    schemas = spec["components"]["schemas"]

    assert spec["paths"][REVIEW_QUEUE_PATH]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/ReviewQueueResponse"}
    assert spec["paths"][REVIEW_CONTEXT_PATH]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/ReviewContext"}
    comment_properties = schemas["CommentResponse"]["properties"]
    assert "review_revision_id" in comment_properties
    assert "is_blocking_issue" in comment_properties
    assert "resolution_events" in comment_properties


def test_semantic_change_before_and_after_are_required_typed_json_values() -> None:
    """Semantic diffs distinguish explicit JSON null from an omitted field."""
    schemas = app.openapi()["components"]["schemas"]
    semantic_change = schemas["SemanticChange"]

    assert {"before", "after"}.issubset(semantic_change["required"])
    assert semantic_change["properties"]["before"] == {
        "$ref": "#/components/schemas/SemanticJsonValue"
    }
    assert semantic_change["properties"]["after"] == {
        "$ref": "#/components/schemas/SemanticJsonValue"
    }
    assert schemas["SemanticJsonValue"] == {
        "anyOf": [
            {
                "items": {"$ref": "#/components/schemas/SemanticJsonValue"},
                "type": "array",
            },
            {
                "additionalProperties": {
                    "$ref": "#/components/schemas/SemanticJsonValue"
                },
                "type": "object",
            },
            {"type": "string"},
            {"type": "integer"},
            {"type": "number"},
            {"type": "boolean"},
            {"type": "null"},
        ]
    }

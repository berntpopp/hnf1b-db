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
TRANSITION_PATH = "/api/v2/phenopackets/{phenopacket_id}/transitions"
PHENOPACKET_DETAIL_PATH = "/api/v2/phenopackets/{phenopacket_id}"


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
    assert "withdraw" in schemas["ActionCapability"]["properties"]["action"]["enum"]
    assert {
        "submit",
        "resubmit",
        "archive",
    }.issubset(schemas["ActionCapability"]["properties"]["action"]["enum"])
    assert "transition_capabilities" in schemas["PhenopacketResponse"]["properties"]
    revision_summary = schemas["ReviewRevisionSummary"]
    assert "actor_role" in revision_summary["properties"]
    assert "actor_role_at_decision_recorded" in revision_summary["properties"]
    assert {
        "actor_role",
        "actor_role_at_decision_recorded",
    }.issubset(revision_summary["required"])


def test_review_queue_and_context_document_complete_typed_dtos() -> None:
    """Queue/context consumers receive identities, audit, and capabilities."""
    schemas = app.openapi()["components"]["schemas"]

    queue = schemas["ReviewQueueResponse"]
    assert queue["required"] == ["data", "meta"]
    assert queue["properties"]["data"]["items"] == {
        "$ref": "#/components/schemas/ReviewQueueRow"
    }
    queue_row = schemas["ReviewQueueRow"]
    assert {
        "record_id",
        "phenopacket_id",
        "effective_state",
        "record_revision",
        "candidate_revision_id",
        "candidate_content_sha256",
        "approved_revision_id",
        "approved_content_sha256",
        "capabilities",
    }.issubset(queue_row["properties"])
    assert queue_row["properties"]["capabilities"]["items"] == {
        "$ref": "#/components/schemas/ActionCapability"
    }
    assert set(queue_row["properties"]) == {
        "record_id",
        "phenopacket_id",
        "subject_label",
        "physical_state",
        "effective_state",
        "owner",
        "submitted_by",
        "submitted_at",
        "record_revision",
        "candidate_revision_id",
        "candidate_content_sha256",
        "approved_revision_id",
        "approved_content_sha256",
        "active_cycle_change_count",
        "open_issue_count",
        "has_published_head",
        "capabilities",
    }
    assert set(queue_row["required"]) == set(queue_row["properties"]) - {"capabilities"}

    context = schemas["ReviewContext"]
    assert {
        "record_id",
        "record_revision",
        "candidate",
        "baseline",
        "approved",
        "audit",
        "discussion_summary",
        "issues",
        "capabilities",
    }.issubset(context["properties"])
    assert context["properties"]["issues"]["items"] == {
        "$ref": "#/components/schemas/ReviewIssue"
    }
    assert set(context["properties"]) == {
        "record_id",
        "phenopacket_id",
        "subject_label",
        "physical_state",
        "effective_state",
        "record_revision",
        "has_published_head",
        "owner",
        "candidate",
        "baseline",
        "approved",
        "semantic_changes",
        "audit",
        "discussion_summary",
        "issues",
        "capabilities",
    }
    assert set(context["required"]) == set(context["properties"]) - {
        "semantic_changes",
        "issues",
        "capabilities",
    }


def test_comment_mutations_document_bodyless_discussion_and_typed_blocking_inputs() -> (
    None
):
    """One optional body supports legacy discussion and exact issue evidence."""
    spec = app.openapi()
    schemas = spec["components"]["schemas"]

    for path, request_schema_name in (
        (COMMENT_RESOLVE_PATH, "ReviewIssueResolveRequest"),
        (COMMENT_UNRESOLVE_PATH, "ReviewIssueReopenRequest"),
    ):
        operation = spec["paths"][path]["post"]
        assert operation["requestBody"].get("required", False) is False
        request_schema = operation["requestBody"]["content"]["application/json"][
            "schema"
        ]
        assert {"type": "null"} in request_schema["anyOf"]
        assert {"type": "object", "additionalProperties": True} in request_schema[
            "anyOf"
        ]
        assert {"$ref": f"#/components/schemas/{request_schema_name}"} in (
            request_schema["anyOf"]
        )
        assert operation["responses"]["200"]["content"]["application/json"][
            "schema"
        ] == {"$ref": "#/components/schemas/CommentResponse"}
        assert operation["responses"]["422"]["content"]["application/json"][
            "schema"
        ] == {"$ref": "#/components/schemas/ApiErrorEnvelope"}

    resolve = schemas["ReviewIssueResolveRequest"]
    assert resolve["additionalProperties"] is False
    assert set(resolve["required"]) == {"record_revision", "rationale", "disposition"}
    assert resolve["properties"]["disposition"]["enum"] == [
        "addressed",
        "accepted_with_rationale",
        "retracted",
        "superseded",
    ]
    assert resolve["properties"]["rationale"]["maxLength"] == 500
    reopen = schemas["ReviewIssueReopenRequest"]
    assert reopen["additionalProperties"] is False
    assert set(reopen["required"]) == {"record_revision", "rationale"}


def test_transition_and_actor_capability_contracts_are_structural_and_exact() -> None:
    """Exact decision evidence and actor-specific action DTOs remain explicit."""
    spec = app.openapi()
    schemas = spec["components"]["schemas"]
    operation = spec["paths"][TRANSITION_PATH]["post"]

    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/TransitionRequest"
    }
    transition = schemas["TransitionRequest"]
    assert set(transition["required"]) == {"to_state", "reason", "revision"}
    assert set(transition["properties"]) == {
        "to_state",
        "reason",
        "revision",
        "candidate_revision_id",
        "candidate_content_sha256",
        "approved_revision_id",
        "approved_content_sha256",
        "attestation",
    }
    for identity_field in ("candidate_revision_id", "approved_revision_id"):
        assert transition["properties"][identity_field]["anyOf"] == [
            {"type": "integer", "exclusiveMinimum": 0.0},
            {"type": "null"},
        ]
    assert (
        transition["properties"]["candidate_content_sha256"]["anyOf"][0]["pattern"]
        == r"^sha256:[0-9a-f]{64}$"
    )
    assert (
        transition["properties"]["approved_content_sha256"]["anyOf"][0]["pattern"]
        == r"^sha256:[0-9a-f]{64}$"
    )
    assert transition["properties"]["attestation"]["anyOf"][0] == {
        "$ref": "#/components/schemas/ApprovalAttestation"
    }
    attestation = schemas["ApprovalAttestation"]
    assert set(attestation["required"]) == {
        "independent_review",
        "no_unmanaged_conflict",
    }
    assert attestation["properties"]["independent_review"]["const"] is True
    assert attestation["properties"]["no_unmanaged_conflict"]["const"] is True

    capability = schemas["ActionCapability"]
    assert set(capability["required"]) == {"action", "allowed"}
    assert capability["properties"]["blocked_by"]["items"]["enum"] == [
        "forbidden_role",
        "forbidden_not_owner",
        "self_review_forbidden",
        "reviewer_submitted",
        "reviewer_contributed",
        "review_author_unknown",
        "unresolved_review_issues",
        "review_closed",
    ]
    detail_schema = spec["paths"][PHENOPACKET_DETAIL_PATH]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    assert detail_schema == {"$ref": "#/components/schemas/PhenopacketResponse"}
    assert schemas["PhenopacketResponse"]["properties"]["transition_capabilities"][
        "items"
    ] == {"$ref": "#/components/schemas/ActionCapability"}


def test_workflow_routes_document_runtime_error_envelope_and_actual_statuses() -> None:
    """Workflow operations expose the shared handler envelope at real statuses."""
    spec = app.openapi()
    schemas = spec["components"]["schemas"]
    error_envelope = schemas["ApiErrorEnvelope"]
    assert set(error_envelope["required"]) == {
        "detail",
        "error_code",
        "request_id",
    }
    assert error_envelope["properties"]["detail"] == {
        "$ref": "#/components/schemas/ApiJsonValue"
    }
    assert set(error_envelope["properties"]) == {
        "detail",
        "error_code",
        "request_id",
    }
    json_value = schemas["ApiJsonValue"]
    assert {item.get("type") for item in json_value["anyOf"]} == {
        "array",
        "object",
        "string",
        "integer",
        "number",
        "boolean",
        "null",
    }

    expected_statuses = {
        (REVIEW_QUEUE_PATH, "get"): {"200", "400", "401", "404", "422"},
        # FastAPI retains its framework-generated 422 for the string path
        # parameter; it uses the same runtime envelope as deliberate errors.
        (REVIEW_CONTEXT_PATH, "get"): {"200", "401", "404", "422"},
        (TRANSITION_PATH, "post"): {
            "200",
            "401",
            "403",
            "404",
            "409",
            "422",
            "500",
        },
        (COMMENT_RESOLVE_PATH, "post"): {
            "200",
            "401",
            "403",
            "404",
            "409",
            "422",
            "500",
        },
        (COMMENT_UNRESOLVE_PATH, "post"): {
            "200",
            "401",
            "403",
            "404",
            "409",
            "422",
            "500",
        },
    }
    error_ref = {"$ref": "#/components/schemas/ApiErrorEnvelope"}
    for (path, method), statuses in expected_statuses.items():
        responses = spec["paths"][path][method]["responses"]
        assert set(responses) == statuses
        for status in statuses - {"200"}:
            assert responses[status]["content"]["application/json"]["schema"] == (
                error_ref
            )


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

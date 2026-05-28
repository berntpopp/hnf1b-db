"""Anti-drift contract tests for the generated API contract package.

These verify that the curated MCP surface (allowlist + variant vocabularies +
key response models) stays in lockstep with the generated contract, which is in
turn generated from the committed backend OpenAPI snapshot. Any drift fails here.
"""
from __future__ import annotations

import re

import pytest

from hnf1b_mcp.client.allowlist import _RULES, is_allowed, is_denied
from hnf1b_mcp.contract import (
    MOLECULAR_CONSEQUENCE_VALUES,
    PROTEIN_DOMAIN_VALUES,
    VARIANT_CLASSIFICATION_VALUES,
    VARIANT_TYPE_VALUES,
)
from hnf1b_mcp.contract._generated_models import (
    GeneDetailSchema,
    ProteinDomainsResponse,
)
from hnf1b_mcp.contract._generated_paths import ALL_PATHS
from hnf1b_mcp.services import variants as variants_service


def _probe(template: str) -> str:
    """Turn a ``{param}`` path template into a concrete probe path."""
    return re.sub(r"\{[^}]+\}", "X", template)


# ---------------------------------------------------------------------------
# (a) every allowlisted path corresponds to a real generated path
# ---------------------------------------------------------------------------


def test_every_allow_rule_matches_a_generated_path() -> None:
    """Each allow regex must match at least one real generated backend path."""
    probes = [_probe(t) for t in ALL_PATHS]
    for rule, _disc in _RULES:
        matched = [p for p in probes if rule.match(p) and not is_denied(p)]
        assert matched, (
            f"allow rule {rule.pattern!r} matches no generated (non-denied) "
            f"path — it is stale or the backend route was removed/renamed"
        )


# ---------------------------------------------------------------------------
# (b) every generated path is allowlisted-or-denied (no silent gaps)
# ---------------------------------------------------------------------------


def test_no_silent_gaps_every_generated_path_decided() -> None:
    """Every backend route must be explicitly allowed or explicitly denied."""
    gaps: list[str] = []
    for template in ALL_PATHS:
        probe = _probe(template)
        if not is_allowed(probe) and not is_denied(probe):
            gaps.append(template)
    assert not gaps, (
        "these generated paths are neither allowed nor explicitly denied "
        f"(forces an explicit security decision): {gaps}"
    )


def test_allowed_and_denied_are_mutually_exclusive() -> None:
    """No generated path may be simultaneously allowed and denied."""
    overlap = [
        t
        for t in ALL_PATHS
        if is_allowed(_probe(t)) and is_denied(_probe(t))
    ]
    assert not overlap, f"paths both allowed and denied: {overlap}"


# ---------------------------------------------------------------------------
# (c) the variant vocab values used in services equal the generated values
# ---------------------------------------------------------------------------


def test_variant_classification_matches_contract() -> None:
    assert variants_service._VALID_CLASSIFICATION == frozenset(
        VARIANT_CLASSIFICATION_VALUES
    )
    assert set(VARIANT_CLASSIFICATION_VALUES) == {
        "PATHOGENIC",
        "LIKELY_PATHOGENIC",
        "UNCERTAIN_SIGNIFICANCE",
        "LIKELY_BENIGN",
        "BENIGN",
    }


def test_molecular_consequence_matches_contract() -> None:
    """Catches the historical consequence drift bug (lof/missense/... was wrong)."""
    assert variants_service._VALID_CONSEQUENCE == frozenset(
        MOLECULAR_CONSEQUENCE_VALUES
    )
    # The real backend vocabulary — NOT the old {lof, missense, splicing, ...}.
    assert "Missense" in MOLECULAR_CONSEQUENCE_VALUES
    assert "Frameshift" in MOLECULAR_CONSEQUENCE_VALUES
    assert "Splice Donor" in MOLECULAR_CONSEQUENCE_VALUES
    assert "lof" not in MOLECULAR_CONSEQUENCE_VALUES


def test_variant_type_matches_contract() -> None:
    assert variants_service._VALID_VARIANT_TYPE == frozenset(VARIANT_TYPE_VALUES)


def test_protein_domain_matches_contract() -> None:
    assert variants_service._VALID_DOMAIN == frozenset(PROTEIN_DOMAIN_VALUES)


# ---------------------------------------------------------------------------
# (d) key response models exist with expected fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "expected_fields"),
    [
        (GeneDetailSchema, {"symbol"}),
        (ProteinDomainsResponse, {"domains", "gene", "genome_build"}),
    ],
)
def test_response_models_have_expected_fields(
    model: type, expected_fields: set[str]
) -> None:
    fields = set(model.model_fields)
    missing = expected_fields - fields
    assert not missing, f"{model.__name__} missing fields: {missing}"

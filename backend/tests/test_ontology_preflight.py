"""Unit tests for ``scripts/ontology_preflight.py``'s pure path-walking logic.

The script's five report sections are DB-driven and were verified manually
against the live database (see the migration commit messages and
tasks-3-6-report.md); this file covers ``_iter_path_values``, the one piece
of logic that is meaningfully testable without a corpus.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ontology_preflight.py"


def _load_module():
    # scripts/ imports `app.*`, which needs backend/ on sys.path -- already
    # true under pytest, but be defensive since this loads by file path.
    backend_root = str(Path(__file__).resolve().parents[1])
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)
    spec = importlib.util.spec_from_file_location("ontology_preflight", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PREFLIGHT = _load_module()


def test_single_object_path():
    doc = {"subject": {"timeAtLastEncounter": {"ontologyClass": {"id": "HP:0003577"}}}}
    values = list(
        PREFLIGHT._iter_path_values(doc, "subject.timeAtLastEncounter.ontologyClass")
    )
    assert values == [{"id": "HP:0003577"}]


def test_array_then_object_path():
    doc = {
        "diseases": [
            {"term": {"id": "MONDO:0007669"}},
            {"term": {"id": "MONDO:0007669"}},
        ]
    }
    values = list(PREFLIGHT._iter_path_values(doc, "diseases[].term"))
    assert values == [{"id": "MONDO:0007669"}, {"id": "MONDO:0007669"}]


def test_array_terminal_path_yields_elements_not_a_sub_key():
    doc = {
        "phenotypicFeatures": [
            {"modifiers": [{"id": "HP:0012832"}, {"id": "HP:0012833"}]},
            {"modifiers": [{"id": "HP:0012834"}]},
        ]
    }
    values = list(PREFLIGHT._iter_path_values(doc, "phenotypicFeatures[].modifiers[]"))
    assert values == [{"id": "HP:0012832"}, {"id": "HP:0012833"}, {"id": "HP:0012834"}]


def test_missing_intermediate_key_yields_nothing():
    doc = {"phenotypicFeatures": [{"type": {"id": "HP:0000107"}}]}  # no "onset"
    values = list(
        PREFLIGHT._iter_path_values(doc, "phenotypicFeatures[].onset.ontologyClass")
    )
    assert values == []


def test_non_list_value_at_an_array_segment_yields_nothing():
    doc = {"diseases": "not-a-list"}
    values = list(PREFLIGHT._iter_path_values(doc, "diseases[].term"))
    assert values == []


def test_empty_array_yields_nothing():
    doc = {"diseases": []}
    values = list(PREFLIGHT._iter_path_values(doc, "diseases[].term"))
    assert values == []


def test_nested_array_path_two_levels_deep():
    doc = {
        "phenotypicFeatures": [
            {"evidence": [{"evidenceCode": {"id": "ECO:0000033"}}]},
        ]
    }
    values = list(
        PREFLIGHT._iter_path_values(doc, "phenotypicFeatures[].evidence[].evidenceCode")
    )
    assert values == [{"id": "ECO:0000033"}]


def test_every_ontology_paths_entry_is_walkable_without_error():
    """A minimal smoke test: every real ONTOLOGY_PATHS entry parses and runs."""
    doc: dict = {}
    for path in PREFLIGHT.ONTOLOGY_PATHS:
        if path == PREFLIGHT._HPO_LOOKUP_PATH:
            continue
        assert list(PREFLIGHT._iter_path_values(doc, path)) == []


def test_onset_report_covers_all_four_required_paths():
    """Onset ids live in four independent paths; a corrupted feature-onset
    must not go unseen.

    Enumerated explicitly here rather than merely iterating whatever
    ``PREFLIGHT.ONTOLOGY_PATHS`` happens to contain: if this test derived its
    expectation from ``ONTOLOGY_PATHS`` instead, it could not fail when an
    onset path is silently dropped from that list (the exact class of
    regression this test exists to catch), because both sides of the
    assertion would move together.
    """
    required_onset_paths = {
        "diseases[].onset.ontologyClass",
        "subject.timeAtLastEncounter.ontologyClass",
        "phenotypicFeatures[].onset.ontologyClass",
        "phenotypicFeatures[].onset.age.ontologyClass",
    }
    assert required_onset_paths == set(PREFLIGHT._ONSET_PATHS)


def test_onset_paths_independently_surface_disagreeing_outer_and_nested_values():
    """The whole point of the nested onset path: it can disagree with its
    sibling, and both must be visible, not merged into one count.

    Mirrors the real corpus shape found while proving the Task 3 term
    correction migration: 10 features carried a
    ``phenotypicFeatures[].onset.ontologyClass`` value that disagreed with
    their own ``phenotypicFeatures[].onset.age.ontologyClass`` sibling.
    """
    doc = {
        "phenotypicFeatures": [
            {
                "onset": {
                    "ontologyClass": {"id": "HP:0003581", "label": "Adult onset"},
                    "age": {
                        "ontologyClass": {
                            "id": "HP:0011463",
                            "label": "Childhood onset",
                        }
                    },
                }
            }
        ]
    }
    outer = list(
        PREFLIGHT._iter_path_values(doc, "phenotypicFeatures[].onset.ontologyClass")
    )
    nested = list(
        PREFLIGHT._iter_path_values(doc, "phenotypicFeatures[].onset.age.ontologyClass")
    )
    assert outer == [{"id": "HP:0003581", "label": "Adult onset"}]
    assert nested == [{"id": "HP:0011463", "label": "Childhood onset"}]
    assert outer != nested, "a disagreeing pair must not collapse into one value"

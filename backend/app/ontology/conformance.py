"""Ontology conformance checks (spec §3.3).

Production module — imported by the migration importer (A1, at import time)
and by the curation program's `DomainValidator` (§6.2), not just by tests.

Two independent assertions guard against a stored `(id, label)` pair meaning
something other than what it claims:

- **A1** `check_source_row` is the discriminator. It anchors on the
  curator's *description*, a field label-normalisation never touches. For
  every source row it evaluates, in order: does the description match
  `term_id`'s canonical definition? If not, does the name match `term_id`'s
  canonical name or a synonym — a genuine fallback, not just a no-description
  path, because most curated descriptions are a paraphrase rather than a
  verbatim copy and a name match is still real corroboration? If neither,
  the row fails, and — because a wrong identifier's description usually
  still matches *some* term — the violation names that term, turning "this
  row is wrong" into "you meant `HP:0033132`". This is exactly the check
  that would have failed the import that produced `HP:0033133`.

- **A3** `check_label` is the naive label-vs-identifier check, retained and
  labelled as insufficient on its own. It is satisfiable by editing the
  label to agree with whatever identifier is already stored, which is
  precisely how `HP:0033133` survived every audit before this one: its label
  had already been normalised to its own (wrong) canonical name. A3 still
  catches real drift — typos, upstream renames, terms retired upstream — so
  it stays, but `check_source_row` is the check that actually catches a
  wrong identifier. `test_cannot_catch_a_normalized_wrong_id` documents this
  limitation directly, so nobody mistakes A3 for the guard.

Neither function repairs a disagreement. Both only report it — the decision
belongs to a human curator, not to code. See
docs/superpowers/specs/2026-07-30-ontology-data-quality-design.md §3.3 and
docs/ontology-defect-report-2026-07-30.md.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).resolve().parent / "data"
_SNAPSHOT_PATH = _DATA_DIR / "ontology_snapshot.json"


class OntologySourceError(Exception):
    """A curation-sheet row's identifier disagrees with its own description.

    Raised by the importer (`migration.phenopackets.hpo_mapper`) after
    collecting every offending row via `check_source_row`, so one failed
    import reports every bad row a curator needs to fix — not just the
    first one encountered.
    """


# The JSONB paths A3 walks, across both authoritative copies
# (`phenopackets.phenopacket` and `phenopacket_revisions.content_jsonb` at
# `head_published_revision_id`) plus the flat lookup table. Spec §3.3.
ONTOLOGY_PATHS: list[str] = [
    "subject.timeAtLastEncounter.ontologyClass",
    "phenotypicFeatures[].type",
    "phenotypicFeatures[].modifiers[]",
    "phenotypicFeatures[].onset.ontologyClass",
    # A second, independent copy of the same onset id, nested under the
    # feature's own `onset.age` key. Found while proving the Task 3 term
    # correction migration against the live database (efa98cccfa51): 275
    # features carry this path, 10 of which *disagree* with their sibling
    # `phenotypicFeatures[].onset.ontologyClass` value, so each is corrected
    # independently rather than derived from the other.
    "phenotypicFeatures[].onset.age.ontologyClass",
    "phenotypicFeatures[].evidence[].evidenceCode",
    "diseases[].term",
    "diseases[].onset.ontologyClass",
    "interpretations[].diagnosis.disease",
    "interpretations[].diagnosis.genomicInterpretations[]"
    ".variantInterpretation.variationDescriptor.structuralType",
    "interpretations[].diagnosis.genomicInterpretations[]"
    ".variantInterpretation.variationDescriptor.allelicState",
    "hpo_terms_lookup.hpo_id",
]

# Known, deliberate label deviations from the pinned snapshot's canonical
# name/synonyms — an allowlist, not a blanket tolerance: a *new* deviation
# still fails A3 loudly, and every accepted one is written down with a
# reason a reviewer can check, not silently swallowed.
ALLOWED_DEVIATIONS: dict[tuple[str, str], str] = {
    ("HP:0012622", "chronic kidney disease, not specified"): (
        "Deliberate local qualifier distinguishing unstaged CKD from the "
        "staged HP:0012623-26 / HP:0003774 terms; the curation sheet's own "
        "definition for this row matches HP:0012622's canonical definition "
        "verbatim, so check_source_row (A1) accepts it independently."
    ),
    ("HP:0002910", "Elevated hepatic transaminase"): (
        "HPO renamed this term to 'Elevated circulating hepatic transaminase "
        "concentration'; the sheet's pre-rename label is not a listed "
        "synonym, but the sheet's definition matches the canonical "
        "definition verbatim."
    ),
    ("HP:0000708", "Behavioral abnormality"): (
        "HPO renamed this term to 'Atypical behavior'. The sheet still uses "
        "the pre-rename primary label, which HPO now lists as a synonym; "
        "recorded explicitly in case a future HPO release drops it."
    ),
    ("HP:0012443", "Abnormality of brain morphology"): (
        "HPO renamed this term to 'Abnormal brain morphology'. The sheet "
        "still uses the pre-rename primary label, which HPO now lists as a "
        "synonym; recorded explicitly in case a future HPO release drops it."
    ),
    ("HP:0003674", "Postnatal onset"): (
        "HPO's onset hierarchy has no discrete postnatal-onset term; "
        "HP:0003674 is the abstract 'Onset' parent. The importer now emits "
        "the accurate label 'Onset' for this id (migration/phenopackets/"
        "age_parser.py, commit 2acfe03); this entry only tolerates the "
        "pre-correction label already stored in the existing corpus, "
        "pending spec §3.2's T5 correction migration."
    ),
    ("ECO:0000033", "author statement"): (
        "Label is an imprecise shortening of the canonical 'author "
        "statement supported by traceable reference'; correcting it is "
        "deferred as cosmetic, with no reader, per the design spec's "
        "non-goals (§4)."
    ),
}


@lru_cache(maxsize=1)
def _snapshot() -> dict[str, dict]:
    """Load the pinned ontology snapshot: `{id: {name, synonyms, definition}}`."""
    with _SNAPSHOT_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    return data["terms"]


def _normalize_text(text: str) -> str:
    """Case-insensitive, trailing-period-insensitive comparison key."""
    return text.strip().rstrip(".").strip().lower()


def _texts_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return _normalize_text(a) == _normalize_text(b)


def _find_term_by_definition(description: str) -> Optional[str]:
    """Search the snapshot for the one term whose definition matches `description`."""
    for candidate_id, term in _snapshot().items():
        if _texts_match(description, term.get("definition") or ""):
            return candidate_id
    return None


def check_label(term_id: str, label: str) -> Optional[str]:
    """A3 — does `label` match `term_id`'s pinned canonical name or a synonym?

    Deliberately insufficient on its own: it is satisfiable by editing the
    label to agree with whatever identifier is stored, which is exactly how
    `HP:0033133` survived — its label had already been normalised to its own
    canonical name while the identifier itself remained wrong.
    `check_source_row` (A1) is the check that actually catches a wrong
    identifier; this one catches drift, typos, and upstream renames.

    Returns `None` when the pair is fine (or an accepted, documented
    deviation); otherwise a human-readable violation message.
    """
    if (term_id, label) in ALLOWED_DEVIATIONS:
        return None

    term = _snapshot().get(term_id)
    if term is None:
        return (
            f"{term_id} is not a known term in the pinned ontology snapshot "
            "(app/ontology/data/ontology_snapshot.json). Refresh the "
            "snapshot if this is a legitimate new term, or check the id."
        )

    if label == term["name"] or label in term.get("synonyms", []):
        return None

    return (
        f"{term_id} is stored with label {label!r}, but the pinned "
        f"snapshot's canonical name is {term['name']!r} "
        f"(synonyms: {term.get('synonyms', [])})."
    )


def check_source_row(term_id: str, name: str, description: str) -> Optional[str]:
    """A1 — is `term_id` corroborated by a field label-normalisation never touches?

    Evaluated in this order, matching spec §3.3:

    1. `description` non-empty and matches `term_id`'s canonical definition
       → corroborated, `None`.
    2. Else `name` matches `term_id`'s canonical name or a listed synonym →
       corroborated, `None`. This is a genuine fallback, checked whenever
       rule 1 didn't already pass — not only when `description` is empty.
       Most curated descriptions are a human paraphrase of the ontology's
       definition, not a verbatim copy (compare "characterised" vs
       "characterized", or a shortened restatement); demanding an exact
       string match on the description alone flags the majority of a real
       curation sheet's honest rows as violations and buries the one row
       that is actually wrong. A name/synonym match is still real
       corroboration — normalisation never touches this field either — so
       falling through to it after a failed description match does not
       reopen the bypass rule 1 exists to close: a **wrong** identifier
       whose label has been *normalised* still fails here, because its
       label was rewritten to match the wrong id's own canonical name, and
       that id is exactly `term_id`, so this check is checking the id
       against itself and only passes if it truly is that id's name.
    3. Otherwise the row fails. The snapshot is searched for the term whose
       definition `description` actually matches; if found, the violation
       names it — this is what turns "this id is wrong" into "you meant
       `HP:0033132`".

    Returns `None` when corroborated; otherwise a human-readable violation
    message. Never rewrites `name` or `term_id` — it only reports.

    Does not consult `ALLOWED_DEVIATIONS` (that allowlist belongs to
    `check_label`/A3 only). Every documented A3 deviation already
    corroborates independently here — via a verbatim definition match
    (`HP:0012622`, `HP:0002910`) or a synonym match (`HP:0000708`,
    `HP:0012443`) — so A1 doesn't need the allowlist to accept them, and a
    hypothetical future "deviation" that couldn't pass on its own evidence
    is exactly the wrong-identifier defect A1 exists to catch, not a case to
    quietly wave through.
    """
    term = _snapshot().get(term_id)
    description = (description or "").strip()
    name = name or ""

    if (
        description
        and term is not None
        and _texts_match(description, term.get("definition") or "")
    ):
        return None

    if term is not None and (name == term["name"] or name in term.get("synonyms", [])):
        return None

    if description:
        match = _find_term_by_definition(description)
        if match is not None and match != term_id:
            return (
                f"{term_id} is named {name!r} with description "
                f"{description!r}, but that description is {match}'s "
                f"canonical definition, not {term_id}'s. The identifier "
                f"should probably be {match}."
            )
        if term is None:
            return (
                f"{term_id} is not a known term in the pinned ontology "
                f"snapshot, and its description {description!r} matches no "
                "other term either."
            )
        return (
            f"{term_id} is named {name!r} with description {description!r}, "
            f"which matches neither {term_id}'s canonical definition nor "
            "any other term in the pinned ontology snapshot, and the name "
            f"does not match {term_id}'s canonical name "
            f"({term['name']!r}) or a listed synonym either."
        )

    if term is None:
        return (
            f"{term_id} is not a known term in the pinned ontology snapshot, "
            "and no description was given to corroborate it."
        )

    return (
        f"{term_id} is named {name!r}, but the pinned snapshot's canonical "
        f"name is {term['name']!r} (synonyms: {term.get('synonyms', [])}), "
        "and no description was given to corroborate the identifier."
    )

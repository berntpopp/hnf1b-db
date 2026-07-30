"""Laterality modifier parsing for phenotype columns.

The curation source records laterality as free-ish compound text in each
phenotype column, not as bare ontology tokens:

    bilateral                797
    unilateral unspecified   177
    unilateral left          119
    unilateral right         112
    no                      2114   (absence, not laterality)
    not reported            2314   (no assertion)

The original extractor matched values against
``["bilateral", "unilateral", "left", "right"]`` exactly. Only ``bilateral``
ever occurs as a bare token, so 408 laterality annotations were dropped while
the phenotype row itself was still written — leaving a feature that is
indistinguishable from one whose laterality was never stated.

Terms are the four HPO clinical modifiers declared in the source's
``Phenotype_modifier`` sheet, all verified against HPO 2026-06-23:

    HP:0012832  Bilateral   Being present on both sides of the body.
    HP:0012833  Unilateral  Being present on only the left or only the right side.
    HP:0012835  Left        Being located on the left side of the body.
    HP:0012834  Right       Being located on the right side of the body.
"""

from typing import Any, Dict, List

BILATERAL = {"id": "HP:0012832", "label": "Bilateral"}
UNILATERAL = {"id": "HP:0012833", "label": "Unilateral"}
LEFT = {"id": "HP:0012835", "label": "Left"}
RIGHT = {"id": "HP:0012834", "label": "Right"}

# Values that carry no laterality assertion at all.
_NON_LATERALITY = {
    "",
    "no",
    "none",
    "absent",
    "negative",
    "yes",
    "not reported",
    "not applicable",
    "unknown",
}


def parse_laterality(value: Any) -> List[Dict[str, str]]:
    """Return the HPO modifiers a source value asserts.

    Bilateral and unilateral are mutually exclusive, so a value naming both is
    treated as unparseable and yields no modifiers rather than a contradiction.

    >>> parse_laterality("bilateral")
    [{'id': 'HP:0012832', 'label': 'Bilateral'}]
    >>> parse_laterality("unilateral left")
    [{'id': 'HP:0012833', 'label': 'Unilateral'}, {'id': 'HP:0012835', 'label': 'Left'}]
    >>> parse_laterality("unilateral unspecified")
    [{'id': 'HP:0012833', 'label': 'Unilateral'}]
    >>> parse_laterality("not reported")
    []

    Args:
        value: Raw cell value from a phenotype column.

    Returns:
        Ordered list of modifier dicts; empty when no laterality is asserted.
    """
    if value is None:
        return []

    text = str(value).strip().lower()
    if text in _NON_LATERALITY:
        return []

    has_bilateral = "bilateral" in text
    # "bilateral" contains "lateral" but not "unilateral"; check explicitly.
    has_unilateral = "unilateral" in text

    if has_bilateral and has_unilateral:
        return []
    if has_bilateral:
        return [dict(BILATERAL)]
    if not has_unilateral:
        return []

    modifiers = [dict(UNILATERAL)]
    if "left" in text:
        modifiers.append(dict(LEFT))
    elif "right" in text:
        modifiers.append(dict(RIGHT))
    return modifiers

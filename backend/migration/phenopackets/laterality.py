"""Laterality parsing driven by the versioned ``Phenotype_modifier`` source sheet."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

_SHA256 = re.compile(r"^[a-f0-9]{64}$", re.IGNORECASE)
_HPO_ID = re.compile(r"^HP:\d{7}$", re.IGNORECASE)
_REQUIRED_MODIFIERS = ("bilateral", "unilateral", "left", "right")
_EXPECTED_TERMS = {
    "bilateral": ("HP:0012832", "Bilateral"),
    "unilateral": ("HP:0012833", "Unilateral"),
    "left": ("HP:0012835", "Left"),
    "right": ("HP:0012834", "Right"),
}
# Public canonical terms shared with the curator-side domain validator.  The
# importer still requires a versioned source ``ModifierVocabulary`` at parse
# time; these constants are not a parser fallback.
BILATERAL = {"id": "HP:0012832", "label": "Bilateral"}
UNILATERAL = {"id": "HP:0012833", "label": "Unilateral"}
LEFT = {"id": "HP:0012835", "label": "Left"}
RIGHT = {"id": "HP:0012834", "label": "Right"}
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


class ModifierVocabularyError(ValueError):
    """The source did not supply a complete, valid modifier vocabulary."""


@dataclass(frozen=True)
class ModifierVocabulary:
    """The content-addressed source vocabulary used for laterality parsing."""

    version_sha256: str
    terms: Mapping[str, tuple[str, str]]


def modifier_vocabulary_from_rows(
    rows: Sequence[Mapping[str, Any]], *, version_sha256: str
) -> ModifierVocabulary:
    """Create a complete laterality vocabulary from validated source rows."""
    if not _SHA256.fullmatch(version_sha256):
        raise ModifierVocabularyError("modifier vocabulary version must be SHA-256")

    terms: dict[str, tuple[str, str]] = {}
    for row in rows:
        label = str(row.get("modifier", "")).strip()
        term_id = str(row.get("modifier_id", "")).strip()
        key = label.casefold()
        if key not in _REQUIRED_MODIFIERS:
            continue
        if not _HPO_ID.fullmatch(term_id) or key in terms:
            raise ModifierVocabularyError("invalid source modifier vocabulary")
        expected_id, expected_label = _EXPECTED_TERMS[key]
        if term_id != expected_id or label != expected_label:
            raise ModifierVocabularyError("source modifier does not match HPO meaning")
        terms[key] = (term_id, label)
    if set(terms) != set(_REQUIRED_MODIFIERS):
        raise ModifierVocabularyError("source modifier vocabulary is incomplete")
    return ModifierVocabulary(version_sha256=version_sha256, terms=terms)


def parse_laterality(
    value: Any, *, vocabulary: ModifierVocabulary | None = None
) -> list[dict[str, str]]:
    """Return modifiers asserted by ``value``, using only supplied source terms.

    A non-laterality value is safe without a vocabulary. Any laterality assertion
    fails closed when the snapshot did not provide the corresponding source sheet.
    """
    if value is None:
        return []
    text = str(value).strip().casefold()
    if text in _NON_LATERALITY:
        return []

    if not re.fullmatch(r"[a-z]+(?: [a-z]+)*", text):
        if re.search(r"\b(?:bilateral|unilateral|left|right)\b", text):
            raise ModifierVocabularyError("invalid laterality qualifier")
        return []
    tokens = tuple(text.split())
    if not any(
        token in {"bilateral", "unilateral", "left", "right"} for token in tokens
    ):
        return []
    allowed = {
        ("bilateral",): ("bilateral",),
        ("unilateral",): ("unilateral",),
        # The source vocabulary uses this explicit phrase for a unilateral
        # finding whose side was not reported.  Preserve unilateral status
        # without inventing a left/right modifier.
        ("unilateral", "unspecified"): ("unilateral",),
        ("unilateral", "left"): ("unilateral", "left"),
        ("unilateral", "right"): ("unilateral", "right"),
    }
    keys = allowed.get(tokens)
    if keys is None:
        raise ModifierVocabularyError("invalid laterality qualifier")
    if vocabulary is None:
        raise ModifierVocabularyError(
            "laterality requires a source modifier vocabulary"
        )
    return [
        {"id": vocabulary.terms[key][0], "label": vocabulary.terms[key][1]}
        for key in keys
    ]

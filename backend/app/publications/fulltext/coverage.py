"""License normalization, the fail-closed license gate, and coverage tiering.

This is a pure module: it performs no I/O. It maps raw license strings to a
canonical token, decides whether a given license permits storing body text,
and assigns a :data:`~app.publications.fulltext.types.Coverage` tier to a
publication. The license gate is fail-closed: when the full-text license is not
explicitly permitted, the body sections are dropped and the publication falls
back to an abstract- or title-only tier so unlicensed body text is never stored.
"""

from __future__ import annotations

import re
from typing import Sequence

from app.publications.fulltext.types import CoverageDecision, FullTextResult

#: Mapping from a separator-normalised license string to its canonical token.
#: Keys are lower-cased, stripped of any trailing version number, and have all
#: runs of whitespace/hyphens collapsed to a single space.
_LICENSE_MAP: dict[str, str] = {
    "cc0": "CC0",
    "cc 0": "CC0",
    "public domain": "CC0",
    "cc by": "CC-BY",
    "ccby": "CC-BY",
    "cc by nc": "CC-BY-NC",
    "cc by sa": "CC-BY-SA",
    "cc by nc nd": "CC-BY-NC-ND",
    "cc by nd": "CC-BY-ND",
    "cc by nc sa": "CC-BY-NC-SA",
}

#: License inputs that explicitly mean "no usable license".
_UNKNOWN_TOKENS: frozenset[str] = frozenset({"", "unknown"})

#: Matches a trailing version number such as "4.0" or "3" *only* when preceded
#: by whitespace (e.g. "cc by 4.0"), so it never eats the meaningful "0" in a
#: glued token like "cc0".
_TRAILING_VERSION_RE = re.compile(r"\s+\d+(?:\.\d+)*\s*$")


def normalize_license(raw: str | None) -> str | None:
    """Map a raw license string to a canonical token.

    The comparison is case-insensitive and tolerant of separators and a
    trailing version number: the input is lower-cased, stripped, a trailing
    version (e.g. ``"4.0"``) is removed, and runs of whitespace and hyphens are
    collapsed to a single space before matching a known license.

    Args:
        raw: The raw license string from an upstream source, or ``None``.

    Returns:
        The canonical license token (e.g. ``"CC-BY"``), or ``None`` when the
        input is missing, empty, ``"unknown"``, or otherwise unrecognised.
    """
    if raw is None:
        return None
    collapsed = re.sub(r"[\s\-]+", " ", raw.strip().lower()).strip()
    if collapsed in _UNKNOWN_TOKENS:
        return None
    # Try the full collapsed form first so meaningful tokens like "cc 0" are
    # not mistaken for a trailing version; only then strip a trailing version.
    if collapsed in _LICENSE_MAP:
        return _LICENSE_MAP[collapsed]
    stripped = _TRAILING_VERSION_RE.sub("", collapsed).strip()
    return _LICENSE_MAP.get(stripped)


def is_license_allowed(
    license_token: str | None,
    *,
    is_open_access: bool,
    allowed: Sequence[str],
) -> bool:
    """Decide whether a license permits storing full-text body sections.

    Args:
        license_token: A canonical license token (typically the output of
            :func:`normalize_license`), or ``None`` when unknown.
        is_open_access: Whether the source reports the record as open access.
        allowed: The configured set of permitted license tokens. The pseudo
            token ``"PMC-OA"`` permits any open-access record.

    Returns:
        ``True`` iff ``license_token`` is not ``None`` and present in
        ``allowed``, or the record is open access and ``"PMC-OA"`` is permitted.
    """
    if license_token is not None and license_token in allowed:
        return True
    return is_open_access and "PMC-OA" in allowed


def classify_coverage(
    *,
    abstract: str | None,
    fulltext: FullTextResult | None,
    allowed_licenses: Sequence[str],
) -> CoverageDecision:
    """Apply the fail-closed license gate and assign a coverage tier.

    The richest tier that the license permits is selected:

    1. ``"full_text"`` when full text with non-empty sections is available and
       its license is permitted (see :func:`is_license_allowed`).
    2. ``"abstract_only"`` when a non-empty abstract is present but the full
       text is absent, has no sections, or is not permitted.
    3. ``"title_only"`` otherwise.

    The gate is fail-closed: when full-text body sections exist but the license
    is not permitted, the sections are dropped (``sections=()``) and the
    publication falls back to a lower tier. Unlicensed body text is never kept.

    Args:
        abstract: The abstract text, or ``None`` when unavailable.
        fulltext: The resolved full-text payload, or ``None`` when unavailable.
        allowed_licenses: The configured set of permitted license tokens.

    Returns:
        The :class:`~app.publications.fulltext.types.CoverageDecision` for the
        publication.
    """
    normalized = normalize_license(fulltext.license) if fulltext is not None else None

    if (
        fulltext is not None
        and fulltext.sections
        and is_license_allowed(
            normalized,
            is_open_access=fulltext.is_open_access,
            allowed=allowed_licenses,
        )
    ):
        return CoverageDecision(
            coverage="full_text",
            license=normalized,
            pmcid=fulltext.pmcid,
            sections=fulltext.sections,
            source=fulltext.source,
        )

    pmcid = fulltext.pmcid if fulltext is not None else None

    if isinstance(abstract, str) and abstract:
        return CoverageDecision(
            coverage="abstract_only",
            license=normalized,
            pmcid=pmcid,
            sections=(),
            source=None,
        )

    return CoverageDecision(
        coverage="title_only",
        license=normalized,
        pmcid=pmcid,
        sections=(),
        source=None,
    )

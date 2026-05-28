"""Local/DB-backed ontology and controlled-vocabulary resolution."""
from __future__ import annotations

from typing import Any

from ..client.api_client import ApiClient
from ..contract._generated_paths import (
    ALL_PATHS,
    ONTOLOGY_HPO_AUTOCOMPLETE,
)
from .errors import McpToolError

# Path prefix for named controlled vocabularies, e.g. /ontology/vocabularies/sex.
_VOCAB_PATH_PREFIX = "/ontology/vocabularies/"

#: Controlled-vocabulary names, derived from the generated ``/ontology/
#: vocabularies/{name}`` path segments so they cannot drift from the backend.
_CONTROLLED_VOCABS: list[str] = sorted(
    path[len(_VOCAB_PATH_PREFIX) :]
    for path in ALL_PATHS
    if path.startswith(_VOCAB_PATH_PREFIX)
)

_VALID_VOCABULARIES: list[str] = ["hpo", *_CONTROLLED_VOCABS]


def _map_vocab_item(item: dict[str, Any]) -> dict[str, Any]:
    """Map a controlled-vocabulary API item to ``{id, label, description}``.

    The API may use different key names (``id``/``code``, ``label``/``value``).
    We normalise to a canonical three-key dict and default missing fields to an
    empty string.

    Args:
        item: A raw item dict from the API response.

    Returns:
        Normalised ``{id, label, description}`` dict.
    """
    id_val = str(item.get("id") or item.get("code") or "")
    label_val = str(item.get("label") or item.get("value") or "")
    desc_val = str(item.get("description") or "")
    return {"id": id_val, "label": label_val, "description": desc_val}


def _map_hpo_item(item: dict[str, Any]) -> dict[str, Any]:
    """Map an HPO autocomplete API item to ``{id, label, description}``.

    Args:
        item: A raw HPO item dict from the autocomplete endpoint.

    Returns:
        Normalised ``{id, label, description}`` dict.
    """
    return {
        "id": str(item.get("hpo_id") or ""),
        "label": str(item.get("label") or ""),
        "description": str(item.get("description") or ""),
    }


async def resolve_terms(
    client: ApiClient,
    text: str,
    vocabulary: str = "hpo",
    limit: int = 10,
) -> dict[str, Any]:
    """Resolve ontology or controlled-vocabulary terms against the HNF1B-db API.

    For HPO vocabulary, calls ``/ontology/hpo/autocomplete`` with ``q=text`` and
    ``limit=limit``.  For named controlled vocabularies (sex, interpretation-status,
    progress-status, allelic-state, evidence-code), calls
    ``/ontology/vocabularies/{vocabulary}`` and optionally filters by ``text``
    (case-insensitive substring match), returning at most ``limit`` entries.

    Args:
        client: Authenticated :class:`~hnf1b_mcp.client.api_client.ApiClient`.
        text: Free-text query string.  May be empty for controlled vocabularies.
        vocabulary: One of ``"hpo"``, ``"sex"``, ``"interpretation-status"``,
            ``"progress-status"``, ``"allelic-state"``, ``"evidence-code"``.
        limit: Maximum number of matches to return.

    Returns:
        ``{query, vocabulary, matches}`` where *matches* is a list of
        ``{id, label, description}`` dicts.

    Raises:
        McpToolError: With code ``"invalid_input"`` if *vocabulary* is not
            recognised.
    """
    if vocabulary not in _VALID_VOCABULARIES:
        raise McpToolError(
            "invalid_input",
            "unknown vocabulary",
            argument="vocabulary",
            choices=_VALID_VOCABULARIES,
        )

    matches: list[dict[str, Any]]

    if vocabulary == "hpo":
        data = await client.get(
            ONTOLOGY_HPO_AUTOCOMPLETE,
            params={"q": text, "limit": limit},
        )
        raw_items: list[dict[str, Any]] = data.get("items") or []
        matches = [_map_hpo_item(item) for item in raw_items]
    else:
        data = await client.get(f"{_VOCAB_PATH_PREFIX}{vocabulary}")
        raw_items = data.get("items") or []
        mapped = [_map_vocab_item(item) for item in raw_items]
        if text:
            lower = text.lower()
            mapped = [
                m
                for m in mapped
                if lower in m["id"].lower()
                or lower in m["label"].lower()
                or lower in m["description"].lower()
            ]
        matches = mapped[:limit]

    return {
        "query": text,
        "vocabulary": vocabulary,
        "matches": matches,
    }

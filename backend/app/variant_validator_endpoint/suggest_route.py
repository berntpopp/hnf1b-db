"""``GET /api/v2/variants/suggest/{partial_notation}`` endpoint."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["variant-validation"])

# Common HNF1B variants used to seed the autocomplete suggestion list.
_COMMON_VARIANTS = [
    "NM_000458.4:c.544+1G>A",
    "NM_000458.4:c.544G>T",
    "NM_000458.4:c.1234A>T",
    "NM_000458.4:c.721C>T",
    "17:36459258-37832869:DEL",
    "17:36459258-37832869:DUP",
    "chr17:g.36459258A>G",
]


@router.get(
    "/suggest/{partial_notation}",
    summary="Get variant notation suggestions",
    description="""
Get autocomplete suggestions for partial variant notation.

This endpoint provides:
- Common HNF1B variant examples matching the partial input
- Format hints when no matches are found
- Helpful examples for different notation types

**Use Cases:**
- Frontend autocomplete during variant entry
- Format validation hints
- Learning correct notation formats

**Returns up to 10 suggestions** including:
- Matching HNF1B variants from common database
- Format templates (e.g., "Format: NM_000458.4:c.123A>G")
    """,
    response_description="List of notation suggestions",
    responses={
        200: {
            "description": "Suggestions returned",
            "content": {
                "application/json": {
                    "examples": {
                        "matching_variants": {
                            "summary": "Partial input matches variants",
                            "value": {
                                "query": "NM_000458",
                                "suggestions": [
                                    "NM_000458.4:c.544+1G>A",
                                    "NM_000458.4:c.544G>T",
                                    "NM_000458.4:c.1234A>T",
                                ],
                            },
                        },
                        "format_hints": {
                            "summary": "No matches, return format hints",
                            "value": {
                                "query": "c.123",
                                "suggestions": ["Format: NM_000458.4:c.123A>G"],
                            },
                        },
                    }
                }
            },
        }
    },
)
async def suggest_notation(partial_notation: str):
    """Get autocomplete suggestions for partial variant notation."""
    partial_lower = partial_notation.lower()

    suggestions = [v for v in _COMMON_VARIANTS if partial_lower in v.lower()]

    if not suggestions:
        if "c." in partial_lower:
            suggestions.append("Format: NM_000458.4:c.123A>G")
        elif "p." in partial_lower:
            suggestions.append("Format: NP_000449.3:p.Arg181*")
        elif "del" in partial_lower:
            suggestions.append("Format: 17:start-end:DEL")
        elif "dup" in partial_lower:
            suggestions.append("Format: 17:start-end:DUP")

    return {
        "query": partial_notation,
        "suggestions": suggestions[:10],
    }

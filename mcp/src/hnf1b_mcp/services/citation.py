"""Citation assembly with date-confidence gating."""

from __future__ import annotations

from typing import Any


def build_citation(pub: dict[str, Any]) -> dict[str, Any]:
    """Return recommended_citation and date_confidence for a publication record."""
    year = pub.get("year")
    confidence = "verified" if year else "unverified"
    parts = [str(pub.get("authors") or "").strip().rstrip(".")]
    if pub.get("title"):
        parts.append(str(pub["title"]).strip().rstrip("."))
    if pub.get("journal"):
        parts.append(str(pub["journal"]).strip())
    if year:
        parts.append(str(year))
    pmid = str(pub.get("pmid") or "").replace("PMID:", "")
    if pmid:
        parts.append(f"PMID:{pmid}")
    if pub.get("doi"):
        parts.append(f"doi:{pub['doi']}")
    citation = ". ".join(p for p in parts if p)
    if confidence == "unverified":
        citation += " (publication date unverified)"
    return {"recommended_citation": citation, "date_confidence": confidence}

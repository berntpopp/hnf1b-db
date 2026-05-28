from hnf1b_mcp.services.citation import build_citation


def test_full_citation():
    c = build_citation(
        {
            "pmid": "PMID:123",
            "title": "T",
            "authors": "Smith J et al.",
            "journal": "Kidney Int",
            "year": 2020,
            "doi": "10.1/x",
        }
    )
    assert "Smith J et al." in c["recommended_citation"]
    assert "2020" in c["recommended_citation"]
    assert c["date_confidence"] == "verified"


def test_unverified_when_no_year():
    c = build_citation(
        {
            "pmid": "PMID:9",
            "title": "T",
            "authors": "X",
            "journal": "J",
            "year": None,
            "doi": None,
        }
    )
    assert c["date_confidence"] == "unverified"
    assert "publication date unverified" in c["recommended_citation"]
    assert "None" not in c["recommended_citation"]

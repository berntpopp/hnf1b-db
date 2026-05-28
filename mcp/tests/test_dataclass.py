from hnf1b_mcp.services.dataclass import DataClass


def test_values():
    assert DataClass.CURATED == "curated_hnf1b_evidence"
    assert DataClass.DERIVED == "curated_derived_analysis"
    assert DataClass.EXTERNAL_REF == "external_reference_identifier"
    assert DataClass.OPERATIONAL == "operational_metadata"

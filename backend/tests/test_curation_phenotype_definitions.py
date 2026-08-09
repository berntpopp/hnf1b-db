"""Public contract for source questions and stable finding definitions."""

from app.phenopackets.curation.definitions import (
    FINDING_DEFINITIONS,
    PHENOTYPE_QUESTIONS,
)


def test_registry_has_the_exact_source_question_and_definition_cardinality():
    """Adding or dropping a source question is a data-conservation defect."""
    assert len(PHENOTYPE_QUESTIONS) == 30
    assert len(FINDING_DEFINITIONS) == 36
    assert {question.source_column for question in PHENOTYPE_QUESTIONS} == {
        "RenalInsufficancy",
        "Hyperechogenicity",
        "RenalCysts",
        "MulticysticDysplasticKidney",
        "KidneyBiopsy",
        "RenalHypoplasia",
        "SolitaryKidney",
        "UrinaryTractMalformation",
        "GenitalTractAbnormality",
        "AntenatalRenalAbnormalities",
        "Hypomagnesemia",
        "Hypokalemia",
        "Hyperuricemia",
        "Gout",
        "MODY",
        "PancreaticHypoplasia",
        "ExocrinePancreaticInsufficiency",
        "Hyperparathyroidism",
        "NeurodevelopmentalDisorder",
        "MentalDisease",
        "Seizures",
        "BrainAbnormality",
        "PrematureBirth",
        "CongenitalCardiacAnomalies",
        "EyeAbnormality",
        "ShortStature",
        "MusculoskeletalFeatures",
        "DysmorphicFeatures",
        "ElevatedHepaticTransaminase",
        "AbnormalLiverPhysiology",
    }


def test_registry_preserves_stable_question_semantics_for_multi_finding_columns():
    """CKD and biopsy remain one source question each, never synthetic siblings."""
    questions = {question.source_column: question for question in PHENOTYPE_QUESTIONS}
    ckd = questions["RenalInsufficancy"]
    biopsy = questions["KidneyBiopsy"]

    assert len(ckd.definition_ids) == 6
    assert len(biopsy.definition_ids) == 2
    assert ckd.finding_cardinality == "one_of"
    assert biopsy.finding_cardinality == "one_of"
    assert ckd.allowed_laterality == "none"
    assert all(definition.definition_id for definition in FINDING_DEFINITIONS)
    assert all(definition.allowed_states for definition in FINDING_DEFINITIONS)
    assert {definition.definition_id for definition in FINDING_DEFINITIONS} == {
        definition_id
        for question in PHENOTYPE_QUESTIONS
        for definition_id in question.definition_ids
    }

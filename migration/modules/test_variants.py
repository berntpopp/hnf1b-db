"""Test variants creation for API testing."""

from app.database import get_db
from app.models import (
    IndividualVariant,
    Variant,
    VariantAnnotation,
    VariantClassification,
)


async def create_test_variants():
    """Create test variants data for API testing."""
    print("[create_test_variants] Creating test variants...")

    # Realistic test variant data (core variant fields only)
    test_variants = [
        {
            "variant_id": "var0001",
            "variant_type": "SNV",
            "hg19": "chr17:36047468:G:A",
            "hg38": "chr17:36080568:G:A",
            "hg19_info": "17:36047468-36047468",
            "hg38_info": "17:36080568-36080568",
            "is_current": True,
        },
        {
            "variant_id": "var0002",
            "variant_type": "DEL",
            "hg19": "chr17:36045000:36050000:<DEL>",
            "hg38": "chr17:36078000:36083000:<DEL>",
            "hg19_info": "17:36045000-36050000",
            "hg38_info": "17:36078000-36083000",
            "is_current": True,
        },
        {
            "variant_id": "var0003",
            "variant_type": "SNV",
            "hg19": "chr17:36048000:C:T",
            "hg38": "chr17:36081000:C:T",
            "hg19_info": "17:36048000-36048000",
            "hg38_info": "17:36081000-36081000",
            "is_current": True,
        },
    ]

    # Separate annotation data for each variant
    variant_annotations = [
        [
            {
                "transcript": "ENST00000257555",
                "c_dot": "c.544G>A",
                "p_dot": "p.(Gly182Ser)",
                "impact": "MODERATE",
                "effect": "missense_variant",
                "source": "vep",
            }
        ],
        [{"impact": "HIGH", "effect": "transcript_ablation", "source": "vep"}],
        [
            {
                "transcript": "ENST00000257555",
                "c_dot": "c.612C>T",
                "p_dot": "p.(Arg204Ter)",
                "impact": "HIGH",
                "effect": "stop_gained",
                "source": "vep",
            }
        ],
    ]

    # Separate classification data for each variant
    variant_classifications = [
        [
            {
                "verdict": "Pathogenic",
                "criteria": "ACMG: PM1, PM2, PP2, PP3",
                "system": "ACMG",
                "comment": "Pathogenic variant in HNF1B gene",
            }
        ],
        [
            {
                "verdict": "Pathogenic",
                "criteria": "ACMG: PVS1, PM2",
                "system": "ACMG",
                "comment": "Large deletion encompassing HNF1B",
            }
        ],
        [
            {
                "verdict": "Pathogenic",
                "criteria": "ACMG: PVS1, PM2, PP5",
                "system": "ACMG",
                "comment": "Nonsense variant causing premature stop",
            }
        ],
    ]

    async for db_session in get_db():
        # Clear existing test variants first
        from sqlalchemy import text

        await db_session.execute(
            text(
                "DELETE FROM individual_variants WHERE variant_id IN "
                "(SELECT id FROM variants WHERE variant_id LIKE 'var%')"
            )
        )
        await db_session.execute(
            text(
                "DELETE FROM variant_annotations WHERE variant_id IN "
                "(SELECT id FROM variants WHERE variant_id LIKE 'var%')"
            )
        )
        await db_session.execute(
            text(
                "DELETE FROM variant_classifications WHERE variant_id IN "
                "(SELECT id FROM variants WHERE variant_id LIKE 'var%')"
            )
        )
        await db_session.execute(
            text("DELETE FROM variants WHERE variant_id LIKE 'var%'")
        )

        # Get individuals to associate variants with
        from app.repositories import IndividualRepository

        individual_repo = IndividualRepository(db_session)
        individuals = await individual_repo.get_multi(skip=0, limit=10)

        created_count = 0
        for i, variant_data in enumerate(test_variants):
            try:
                # Create variant
                variant_obj = Variant(**variant_data)
                db_session.add(variant_obj)
                await db_session.flush()  # Get the ID

                # Create annotations for this variant
                for annotation_data in variant_annotations[i]:
                    annotation_obj = VariantAnnotation(
                        variant_id=variant_obj.id, **annotation_data
                    )
                    db_session.add(annotation_obj)

                # Create classifications for this variant
                for classification_data in variant_classifications[i]:
                    classification_obj = VariantClassification(
                        variant_id=variant_obj.id, **classification_data
                    )
                    db_session.add(classification_obj)

                # Associate with some individuals
                for j, individual in enumerate(
                    individuals[0][:2]
                ):  # Associate each variant with 2 individuals
                    association_data = {
                        "individual_id": individual.id,
                        "variant_id": variant_obj.id,
                        "detection_method": "WES" if j % 2 == 0 else "Sanger",
                        "segregation": "de novo" if j % 3 == 0 else "inherited",
                        "is_current": True,
                    }

                    association_obj = IndividualVariant(**association_data)
                    db_session.add(association_obj)

                created_count += 1
                print(
                    f"[create_test_variants] Created variant: "
                    f"{variant_data['variant_id']} "
                    f"with {len(variant_annotations[i])} annotations and "
                    f"{len(variant_classifications[i])} classifications"
                )

            except Exception as e:
                print(
                    f"[create_test_variants] Error creating variant "
                    f"{variant_data['variant_id']}: {e}"
                )

        await db_session.commit()
        print(
            f"[create_test_variants] Successfully created {created_count} test variants"
        )
        break

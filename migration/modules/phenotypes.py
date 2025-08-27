"""Phenotype processing module for clinical data migration."""

from typing import Any, Dict

import pandas as pd

# Special phenotype mappings for complex fields
RENAL_MAPPING = {
    "chronic kidney disease, not specified": {
        "phenotype_id": "HP:0012622",
        "name": "chronic kidney disease, not specified",
        "group": "Kidney",
    },
    "stage 1 chronic kidney disease": {
        "phenotype_id": "HP:0012623",
        "name": "Stage 1 chronic kidney disease",
        "group": "Kidney",
    },
    "stage 2 chronic kidney disease": {
        "phenotype_id": "HP:0012624",
        "name": "Stage 2 chronic kidney disease",
        "group": "Kidney",
    },
    "stage 3 chronic kidney disease": {
        "phenotype_id": "HP:0012625",
        "name": "Stage 3 chronic kidney disease",
        "group": "Kidney",
    },
    "stage 4 chronic kidney disease": {
        "phenotype_id": "HP:0012626",
        "name": "Stage 4 chronic kidney disease",
        "group": "Kidney",
    },
    "stage 5 chronic kidney disease": {
        "phenotype_id": "HP:0003774",
        "name": "Stage 5 chronic kidney disease",
        "group": "Kidney",
    },
    "no": {
        "phenotype_id": "HP:0012622",
        "name": "chronic kidney disease, not specified",
        "group": "Kidney",
    },
    "not reported": {
        "phenotype_id": "HP:0012622",
        "name": "chronic kidney disease, not specified",
        "group": "Kidney",
    },
}

KIDNEY_BIOPSY_MAPPING = {
    "not reported": {
        "HP:0100611": {
            "phenotype_id": "HP:0100611",
            "name": "Multiple glomerular cysts",
            "group": "Kidney",
            "described": "not reported",
        },
        "ORPHA:2260": {
            "phenotype_id": "ORPHA:2260",
            "name": "Oligomeganephronia",
            "group": "Kidney",
            "described": "not reported",
        },
    },
    "no": {
        "HP:0100611": {
            "phenotype_id": "HP:0100611",
            "name": "Multiple glomerular cysts",
            "group": "Kidney",
            "described": "no",
        },
        "ORPHA:2260": {
            "phenotype_id": "ORPHA:2260",
            "name": "Oligomeganephronia",
            "group": "Kidney",
            "described": "no",
        },
    },
    "multiple glomerular cysts": {
        "HP:0100611": {
            "phenotype_id": "HP:0100611",
            "name": "Multiple glomerular cysts",
            "group": "Kidney",
            "described": "yes",
        },
        "ORPHA:2260": {
            "phenotype_id": "ORPHA:2260",
            "name": "Oligomeganephronia",
            "group": "Kidney",
            "described": "no",
        },
    },
    "oligomeganephronia": {
        "HP:0100611": {
            "phenotype_id": "HP:0100611",
            "name": "Multiple glomerular cysts",
            "group": "Kidney",
            "described": "no",
        },
        "ORPHA:2260": {
            "phenotype_id": "ORPHA:2260",
            "name": "Oligomeganephronia",
            "group": "Kidney",
            "described": "yes",
        },
    },
    "oligomeganephronia and multiple glomerular cysts": {
        "HP:0100611": {
            "phenotype_id": "HP:0100611",
            "name": "Multiple glomerular cysts",
            "group": "Kidney",
            "described": "yes",
        },
        "ORPHA:2260": {
            "phenotype_id": "ORPHA:2260",
            "name": "Oligomeganephronia",
            "group": "Kidney",
            "described": "yes",
        },
    },
}

PHENOTYPE_COLUMNS = [
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
]

# Manual modifier mappings for specific phenotype patterns
MANUAL_MODIFIER_MAP = {
    "unilateral left": "left",
    "unilateral right": "right",
    "unilateral unspecified": "unilateral",
    "bilateral": "bilateral",
}


async def process_phenotypes(
    row: pd.Series, phenotype_mapping: Dict[str, Any], modifier_mapping: Dict[str, Any]
) -> Dict[str, Any]:
    """Process phenotype data for a single report row."""
    phenotypes_obj = {}

    for col in PHENOTYPE_COLUMNS:
        raw_val = row.get(col, "")
        reported_val = str(raw_val).strip() if pd.notna(raw_val) else ""
        pheno_key = col.strip().lower()
        lower_val = reported_val.lower()

        if pheno_key == "renalinsufficancy":
            if lower_val == "":
                lower_val = "not reported"

            if lower_val in RENAL_MAPPING:
                std_info = RENAL_MAPPING[lower_val]
                if lower_val in ["no", "not reported"]:
                    described = lower_val
                    entry = {
                        "phenotype_id": std_info["phenotype_id"],
                        "name": std_info["name"],
                        "group": std_info.get("group", ""),
                        "modifier": None,
                        "described": described,
                    }
                    phenotypes_obj[std_info["phenotype_id"]] = entry
                else:
                    described = "yes"
                    # Add specific stage entry
                    entry_stage = {
                        "phenotype_id": std_info["phenotype_id"],
                        "name": std_info["name"],
                        "group": std_info.get("group", ""),
                        "modifier": None,
                        "described": described,
                    }
                    phenotypes_obj[std_info["phenotype_id"]] = entry_stage

                    # Add general chronic kidney disease entry
                    extra = RENAL_MAPPING["chronic kidney disease, not specified"]
                    entry_extra = {
                        "phenotype_id": extra["phenotype_id"],
                        "name": extra["name"],
                        "group": extra.get("group", ""),
                        "modifier": None,
                        "described": "yes",
                    }
                    phenotypes_obj[extra["phenotype_id"]] = entry_extra
            else:
                print(
                    f"[process_phenotypes] Warning: no matching renal phenotype for '{reported_val}'"
                )
                std_info = {"phenotype_id": "UNKNOWN", "name": reported_val}
                described = "yes"
                phenotypes_obj[std_info["phenotype_id"]] = {
                    "phenotype_id": std_info["phenotype_id"],
                    "name": std_info["name"],
                    "group": "",
                    "modifier": None,
                    "described": described,
                }

        elif pheno_key == "kidneybiopsy":
            if lower_val == "":
                lower_val = "not reported"

            mapping_vals = KIDNEY_BIOPSY_MAPPING.get(lower_val)
            if mapping_vals:
                phenotypes_obj["HP:0100611"] = mapping_vals["HP:0100611"]
                phenotypes_obj["ORPHA:2260"] = mapping_vals["ORPHA:2260"]
            else:
                print(
                    f"[process_phenotypes] Warning: no matching KidneyBiopsy phenotype for '{reported_val}'"
                )
                phenotypes_obj["UNKNOWN"] = {
                    "phenotype_id": "UNKNOWN",
                    "name": reported_val,
                    "group": "",
                    "modifier": None,
                    "described": "yes",
                }

        else:
            # Standard phenotype processing
            std_info = phenotype_mapping.get(
                pheno_key, {"phenotype_id": col, "name": col, "group": ""}
            )

            if lower_val in ["yes", "no", "not reported"]:
                described = lower_val
                modifier_obj = None
            else:
                described = "yes"

                # Apply modifier mapping
                if pheno_key in [
                    "congenitalcardiacanomalies",
                    "antenatalrenalabnormalities",
                ]:
                    modifier_key = "congenital onset"
                else:
                    modifier_key = MANUAL_MODIFIER_MAP.get(lower_val, lower_val)

                modifier_obj = modifier_mapping.get(modifier_key)

            phenotypes_obj[std_info["phenotype_id"]] = {
                "phenotype_id": std_info["phenotype_id"],
                "name": std_info["name"],
                "group": std_info.get("group", ""),
                "modifier": modifier_obj,
                "described": described,
            }

    return phenotypes_obj


async def load_phenotype_mappings(
    spreadsheet_id: str, gid_phenotypes: str
) -> Dict[str, Any]:
    """Load phenotype mappings from Google Sheets."""
    from .utils import csv_url, normalize_dataframe_columns

    print("[load_phenotype_mappings] Loading phenotype mappings...")
    url = csv_url(spreadsheet_id, gid_phenotypes)
    df = pd.read_csv(url)
    df = df.dropna(how="all")
    df = normalize_dataframe_columns(df)

    mapping = {}
    for _, row in df.iterrows():
        key = str(row["name"]).strip().lower()
        mapping[key] = {
            "phenotype_id": row["phenotype_id"],
            "name": row["name"].strip(),
            "group": row.get("group", "").strip(),
        }

        # Add synonyms to mapping
        if pd.notna(row.get("synonyms")):
            synonyms = row["synonyms"].split(",")
            for syn in synonyms:
                mapping[syn.strip().lower()] = {
                    "phenotype_id": row["phenotype_id"],
                    "name": row["name"].strip(),
                    "group": row.get("group", "").strip(),
                }

    print(
        f"[load_phenotype_mappings] Loaded mapping for {len(mapping)} phenotype keys."
    )
    return mapping


async def load_modifier_mappings(
    spreadsheet_id: str, gid_modifiers: str
) -> Dict[str, Any]:
    """Load modifier mappings from Google Sheets."""
    from .utils import csv_url, normalize_dataframe_columns

    print("[load_modifier_mappings] Loading modifier mappings...")
    url = csv_url(spreadsheet_id, gid_modifiers)
    df = pd.read_csv(url)
    df = df.dropna(how="all")
    df = normalize_dataframe_columns(df)

    mapping = {}
    for _, row in df.iterrows():
        key = str(row["modifier_name"]).strip().lower()
        mapping[key] = {
            "modifier_id": row["modifier_id"],
            "name": row["modifier_name"].strip(),
            "description": row.get("modifier_description", "").strip(),
            "synonyms": row.get("modifier_synonyms", "").strip(),
        }

        # Add synonyms to mapping
        if pd.notna(row.get("modifier_synonyms")):
            synonyms = row["modifier_synonyms"].split(",")
            for syn in synonyms:
                mapping[syn.strip().lower()] = {
                    "modifier_id": row["modifier_id"],
                    "name": row["modifier_name"].strip(),
                    "description": row.get("modifier_description", "").strip(),
                    "synonyms": row.get("modifier_synonyms", "").strip(),
                }

    print(f"[load_modifier_mappings] Loaded mapping for {len(mapping)} modifier keys.")
    return mapping

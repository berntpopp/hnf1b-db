"""Protein structure import module."""

import pandas as pd

from app.database import get_db
from app.models import Protein

from .utils import csv_url, normalize_dataframe_columns


async def import_proteins(spreadsheet_id: str, test_mode: bool = False):
    """Import protein structure and domains data from Google Sheets.

    Args:
        spreadsheet_id: Google Sheets ID
        test_mode: If True, create test data instead of fetching from sheets
    """
    print("[import_proteins] Starting protein structure import...")

    if test_mode:
        await create_test_proteins()
        return

    gid_proteins = "810380453"
    url = csv_url(spreadsheet_id, gid_proteins)
    print(f"[import_proteins] Reading proteins CSV from URL: {url}")

    try:
        df = pd.read_csv(url)
    except Exception as e:
        print(f"[import_proteins] Error accessing Google Sheets: {e}")
        print("[import_proteins] Falling back to test data...")
        await create_test_proteins()
        return

    df = normalize_dataframe_columns(df)

    expected_columns = [
        "gene",
        "transcript",
        "protein",
        "FeatureKey",
        "position",
        "start",
        "length",
        "description",
        "description_short",
        "source",
        "height",
    ]
    missing = [col for col in expected_columns if col not in df.columns]
    if missing:
        print(f"[import_proteins] Missing expected columns: {missing}")
        print("[import_proteins] Falling back to test data...")
        await create_test_proteins()
        return

    def sanitize_value(val) -> str:
        s = str(val).strip() if val is not None else ""
        return "" if s.upper() in ("NA", "NAN") else s

    for col in df.columns:
        df[col] = df[col].apply(sanitize_value)

    gene_val = sanitize_value(df.iloc[0]["gene"])
    transcript_val = sanitize_value(df.iloc[0]["transcript"])
    protein_val = sanitize_value(df.iloc[0]["protein"])

    features = {}
    for _, row in df.iterrows():
        feature_key = sanitize_value(row["FeatureKey"])
        if feature_key not in features:
            features[feature_key] = []

        pos_str = sanitize_value(row["position"])
        if ".." in pos_str:
            parts = pos_str.split("..")
            try:
                start_position = int(parts[0])
                end_position = int(parts[1])
            except Exception:
                start_position, end_position = None, None
        else:
            try:
                start_position = int(pos_str) if pos_str else None
                end_position = int(pos_str) if pos_str else None
            except Exception:
                start_position, end_position = None, None

        try:
            start_str = sanitize_value(row["start"])
            start_val = int(start_str) if start_str.isdigit() else None
        except Exception:
            start_val = None

        try:
            length_str = sanitize_value(row["length"])
            length_val = int(length_str) if length_str.isdigit() else None
        except Exception:
            length_val = None

        try:
            height_str = sanitize_value(row["height"])
            height_val = int(height_str) if height_str.isdigit() else None
        except Exception:
            height_val = None

        feature_obj = {
            "start_position": start_position,
            "end_position": end_position,
            "start": start_val,
            "length": length_val,
            "description": sanitize_value(row["description"]),
            "description_short": sanitize_value(row["description_short"]),
            "source": sanitize_value(row["source"]),
            "height": height_val,
        }
        features[feature_key].append(feature_obj)

    async for db_session in get_db():
        # Clear existing proteins
        from sqlalchemy import text

        await db_session.execute(text("DELETE FROM proteins"))

        # Create protein document
        protein_obj = Protein(
            gene=gene_val,
            transcript=transcript_val,
            protein=protein_val,
            features=features,
        )

        db_session.add(protein_obj)
        await db_session.commit()

        print(
            f"[import_proteins] Successfully imported protein structure for '{gene_val}'"
        )
        break


async def create_test_proteins():
    """Create test protein data for API testing."""
    print("[create_test_proteins] Creating test protein structure data...")

    # Realistic HNF1B protein structure data
    test_features = {
        "DNA_binding_domain": [
            {
                "start_position": 1,
                "end_position": 280,
                "start": 1,
                "length": 280,
                "description": "Hepatocyte nuclear factor 1-beta DNA-binding domain",
                "description_short": "HNF1B DNA-binding",
                "source": "UniProt",
                "height": 20,
            }
        ],
        "Dimerisation_domain": [
            {
                "start_position": 32,
                "end_position": 281,
                "start": 32,
                "length": 249,
                "description": "Dimerisation domain required for DNA binding",
                "description_short": "Dimerisation",
                "source": "UniProt",
                "height": 15,
            }
        ],
        "Trans_activation": [
            {
                "start_position": 282,
                "end_position": 557,
                "start": 282,
                "length": 275,
                "description": "Transcriptional activation domain",
                "description_short": "Trans-activation",
                "source": "UniProt",
                "height": 25,
            }
        ],
    }

    async for db_session in get_db():
        # Clear existing proteins
        from sqlalchemy import text

        await db_session.execute(text("DELETE FROM proteins"))

        # Create test protein
        protein_obj = Protein(
            gene="HNF1B",
            transcript="ENST00000257555",
            protein="ENSP00000257555",
            features=test_features,
        )

        db_session.add(protein_obj)
        await db_session.commit()

        print("[create_test_proteins] Successfully created test protein structure")
        break

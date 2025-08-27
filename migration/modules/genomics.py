"""Genomic file processing module for VCF, VEP, and CADD data."""

import re
from typing import Any, Dict

import pandas as pd

from .utils import none_if_nan, parse_date


def read_vcf_file(filepath: str) -> pd.DataFrame:
    """Read a VCF file and extract variant information."""
    print(f"[read_vcf_file] Reading VCF file: {filepath}")

    with open(filepath, "r") as f:
        lines = f.readlines()

    # Skip header lines starting with ##
    data_lines = []
    for line in lines:
        if line.startswith("#CHROM"):
            header = line.strip().split("\t")
            continue
        elif not line.startswith("#"):
            data_lines.append(line.strip().split("\t"))

    if not data_lines:
        print(f"[read_vcf_file] Warning: No data found in VCF file {filepath}")
        return pd.DataFrame()

    # Create DataFrame
    df = pd.DataFrame(data_lines, columns=header)

    # Create vcf_hg38 identifier
    df["var_id"] = range(1, len(df) + 1)
    df["vcf_hg38"] = df["#CHROM"] + ":" + df["POS"] + ":" + df["REF"] + ":" + df["ALT"]

    print(f"[read_vcf_file] Loaded {len(df)} variants from {filepath}")
    return df


def read_vep_file(filepath: str) -> pd.DataFrame:
    """Read a VEP annotation file."""
    print(f"[read_vep_file] Reading VEP file: {filepath}")

    try:
        # VEP files are tab-separated
        df = pd.read_csv(filepath, sep="\t", comment="#", low_memory=False)
        print(f"[read_vep_file] Loaded {len(df)} annotations from {filepath}")
        return df
    except Exception as e:
        print(f"[read_vep_file] Error reading VEP file {filepath}: {e}")
        return pd.DataFrame()


def read_cadd_file(filepath: str) -> pd.DataFrame:
    """Read a CADD annotation file."""
    print(f"[read_cadd_file] Reading CADD file: {filepath}")

    try:
        # CADD files are tab-separated and may be gzipped
        df = pd.read_csv(filepath, sep="\t", comment="#", low_memory=False)

        # Create vcf_hg38 identifier for merging
        if all(col in df.columns for col in ["Chrom", "Pos", "Ref", "Alt"]):
            df["vcf_hg38"] = (
                df["Chrom"].astype(str)
                + ":"
                + df["Pos"].astype(str)
                + ":"
                + df["Ref"].astype(str)
                + ":"
                + df["Alt"].astype(str)
            )

        print(f"[read_cadd_file] Loaded {len(df)} CADD scores from {filepath}")
        return df
    except Exception as e:
        print(f"[read_cadd_file] Error reading CADD file {filepath}: {e}")
        return pd.DataFrame()


def parse_vep_extra(vep_df: pd.DataFrame) -> pd.DataFrame:
    """Parse the Extra column from VEP output to extract additional annotations."""
    print("[parse_vep_extra] Parsing VEP Extra column...")

    df = vep_df.copy()

    # Initialize columns for parsed data
    extra_cols = ["SpliceAI_pred", "ClinVar", "ClinVar_CLNSIG", "VARIANT_CLASS"]
    for col in extra_cols:
        df[col] = None

    if "Extra" not in df.columns:
        print("[parse_vep_extra] Warning: No 'Extra' column found in VEP data")
        return df

    for idx, row in df.iterrows():
        extra_str = row.get("Extra", "")
        if pd.notna(extra_str) and extra_str:
            # Parse semicolon-separated key=value pairs
            pairs = extra_str.split(";")
            for pair in pairs:
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    if key in extra_cols:
                        df.at[idx, key] = value

    print(f"[parse_vep_extra] Parsed Extra column for {len(df)} rows")
    return df


async def build_annotation_map(
    vep_data: pd.DataFrame, cadd_data: pd.DataFrame
) -> Dict[str, Dict[str, Any]]:
    """Build annotation mapping from VEP and CADD data."""
    print("[build_annotation_map] Building annotation map from VEP and CADD data...")

    # Merge VEP with CADD data
    if not cadd_data.empty and "vcf_hg38" in cadd_data.columns:
        vep_annot = pd.merge(
            vep_data, cadd_data[["vcf_hg38", "PHRED"]], on="vcf_hg38", how="left"
        )
        vep_annot.rename(columns={"PHRED": "CADD_PHRED_v16"}, inplace=True)
    else:
        vep_annot = vep_data.copy()
        vep_annot["CADD_PHRED_v16"] = None

    # Parse VEP Extra column
    vep_parsed = parse_vep_extra(vep_annot)

    default_date = pd.to_datetime("2022-10-07").to_pydatetime()
    annotation_map = {}
    cnv_annotation_map = {}

    for _, row in vep_parsed.iterrows():
        vcf_key = row.get("vcf_hg38")
        if pd.notna(vcf_key):
            annotation_obj = {
                "transcript": none_if_nan(row.get("Feature")),
                "c_dot": none_if_nan(row.get("HGVSc")),
                "p_dot": none_if_nan(row.get("HGVSp")),
                "cDNA_position": none_if_nan(row.get("cDNA_position")),
                "protein_position": none_if_nan(row.get("Protein_position")),
                "impact": none_if_nan(row.get("IMPACT")),
                "effect": none_if_nan(row.get("Consequence")),
                "variant_class": none_if_nan(row.get("VARIANT_CLASS")),
                "SpliceAI_pred": none_if_nan(row.get("SpliceAI_pred")),
                "ClinVar": none_if_nan(row.get("ClinVar")),
                "ClinVar_CLNSIG": none_if_nan(row.get("ClinVar_CLNSIG")),
                "cadd_phred": (
                    float(row["CADD_PHRED_v16"])
                    if pd.notna(row.get("CADD_PHRED_v16"))
                    else None
                ),
                "source": "vep",
                "annotation_date": (
                    parse_date(row.get("Uploaded_date"))
                    if "Uploaded_date" in row and pd.notna(row.get("Uploaded_date"))
                    else default_date
                ),
            }

            # Handle CNVs separately
            if ("<DEL>" in vcf_key) or ("<DUP>" in vcf_key):
                cnv_annotation_map[vcf_key] = annotation_obj
            else:
                annotation_map[vcf_key] = annotation_obj

    print(
        f"[build_annotation_map] Built {len(annotation_map)} standard annotations and {len(cnv_annotation_map)} CNV annotations"
    )
    return annotation_map, cnv_annotation_map


def parse_varsome_annotation(varsome_str: str) -> Dict[str, Any]:
    """Parse Varsome annotation string to extract c.dot and p.dot."""
    pattern = r"^[^(]+\(([^)]+)\):([^ ]+)\s+(\(p\..+\))"
    match = re.match(pattern, varsome_str)

    if match:
        transcript = match.group(1)
        c_dot = match.group(2)
        p_dot = match.group(3)

        return {
            "transcript": transcript,
            "c_dot": c_dot,
            "p_dot": p_dot,
            "source": "varsome",
        }

    return {}


async def load_genomic_files(data_dir: str = "data") -> Dict[str, pd.DataFrame]:
    """Load all genomic data files (VCF, VEP, CADD)."""
    print("[load_genomic_files] Loading genomic annotation files...")

    files = {
        "vcf_small": f"{data_dir}/HNF1B_all_small.vcf",
        "vcf_large": f"{data_dir}/HNF1B_all_large.vcf",
        "vep_small": f"{data_dir}/HNF1B_all_small.vep.txt",
        "vep_large": f"{data_dir}/HNF1B_all_large.vep.txt",
        "cadd": f"{data_dir}/GRCh38-v1.6_8e57eaf4ea2378c16be97802d446e98e.tsv.gz",
    }

    data = {}

    try:
        # Load VCF files
        data["vcf_small"] = read_vcf_file(files["vcf_small"])
        data["vcf_large"] = read_vcf_file(files["vcf_large"])

        # Load VEP files
        data["vep_small"] = read_vep_file(files["vep_small"])
        data["vep_large"] = read_vep_file(files["vep_large"])

        # Merge VEP with VCF data
        data["vep_small_ann"] = pd.merge(
            data["vep_small"], data["vcf_small"], on="var_id", how="left"
        )
        data["vep_large_ann"] = pd.merge(
            data["vep_large"], data["vcf_large"], on="var_id", how="left"
        )

        # Combine VEP data
        data["vep_combined"] = pd.concat(
            [data["vep_small_ann"], data["vep_large_ann"]], ignore_index=True
        )

        # Load CADD data
        data["cadd"] = read_cadd_file(files["cadd"])

        print("[load_genomic_files] Loaded genomic files:")
        print(f"  VCF small: {len(data['vcf_small'])} variants")
        print(f"  VCF large: {len(data['vcf_large'])} variants")
        print(f"  VEP combined: {len(data['vep_combined'])} annotations")
        print(f"  CADD: {len(data['cadd'])} scores")

        return data

    except Exception as e:
        print(f"[load_genomic_files] Error loading genomic files: {e}")
        return {"error": str(e)}


async def process_variant_annotations(
    row: pd.Series, annotation_map: Dict, cnv_annotation_map: Dict
) -> list:
    """Process variant annotations for a single variant."""
    annotations = []

    # Check for Varsome annotation
    varsome_val = none_if_nan(row.get("Varsome"))
    if pd.notna(varsome_val):
        varsome_annotation = parse_varsome_annotation(str(varsome_val))
        if varsome_annotation:
            annotations.append(varsome_annotation)

    # Check for VEP/CADD annotation
    vcf_key = none_if_nan(row.get("hg38"))
    if vcf_key:
        if vcf_key in annotation_map:
            annotations.append(annotation_map[vcf_key])
        elif (
            ("<DEL>" in vcf_key) or ("<DUP>" in vcf_key)
        ) and vcf_key in cnv_annotation_map:
            annotations.append(cnv_annotation_map[vcf_key])

    return annotations


def build_variant_key(row: pd.Series) -> str:
    """Build a unique variant key from variant type and genomic coordinates."""
    variant_key_cols = ["VariantType", "hg19_INFO", "hg19", "hg38_INFO", "hg38"]
    key_parts = []

    for col in variant_key_cols:
        val = none_if_nan(row.get(col))
        key_parts.append(str(val).strip() if val is not None else "")

    return "|".join(key_parts)

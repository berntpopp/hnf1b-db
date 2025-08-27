"""Utility functions for migration from Google Sheets."""

import pandas as pd


def format_individual_id(value) -> str:
    """Format an individual id as 'ind' followed by a 4-digit zero-padded number."""
    try:
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            return f"ind{int(value):04d}"
    except Exception:
        pass
    return value


def format_report_id(value) -> str:
    """Format a report id as 'rep' followed by a 4-digit zero-padded number."""
    try:
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            return f"rep{int(value):04d}"
    except Exception:
        pass
    return value


def format_variant_id(value) -> str:
    """Format a variant id as 'var' followed by a 4-digit zero-padded number."""
    try:
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            return f"var{int(value):04d}"
    except Exception:
        pass
    return value


def format_publication_id(value) -> str:
    """Format a publication id as 'pub' followed by a 4-digit zero-padded number."""
    try:
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            return f"pub{int(value):04d}"
    except Exception:
        pass
    return value


def none_if_nan(v):
    """Convert pandas NaN values and 'NA' strings to None."""
    if pd.isna(v):
        return None
    if isinstance(v, str) and v.strip().upper() == "NA":
        return None
    return v


def parse_date(value):
    """Convert a date-like value to a Python datetime object using Pandas."""
    try:
        if value is None:
            return None
        dt = pd.to_datetime(value, errors="coerce")
        if pd.isnull(dt):
            return None
        return dt.to_pydatetime()
    except Exception:
        return None


def csv_url(spreadsheet_id: str, gid: str) -> str:
    """Build Google Sheets CSV export URL for a specific sheet."""
    url = (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/"
        f"export?format=csv&gid={gid}"
    )
    return url


def normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize DataFrame column names by stripping whitespace."""
    df.columns = df.columns.str.strip()
    return df


def safe_str(value) -> str:
    """Safely convert value to string, handling pandas data types."""
    if pd.isna(value):
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip() if value else ""

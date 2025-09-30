"""Google Sheets data loader for migration."""

import logging
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class GoogleSheetsLoader:
    """Loader for Google Sheets data."""

    def __init__(self, spreadsheet_id: str, gid_config: Dict[str, str]):
        """Initialize Google Sheets loader.

        Args:
            spreadsheet_id: Google Sheets spreadsheet ID
            gid_config: Dictionary mapping sheet names to GIDs
        """
        self.spreadsheet_id = spreadsheet_id
        self.gid_config = gid_config

    def _csv_url(self, gid: str) -> str:
        """Generate Google Sheets CSV export URL.

        Args:
            gid: Sheet GID

        Returns:
            CSV export URL
        """
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/export?format=csv&gid={gid}"

    def load_sheet(self, sheet_name: str) -> Optional[pd.DataFrame]:
        """Load a single sheet by name.

        Args:
            sheet_name: Name of the sheet to load (must be in gid_config)

        Returns:
            DataFrame or None if loading fails
        """
        gid = self.gid_config.get(sheet_name)
        if not gid:
            logger.error(f"No GID configured for sheet: {sheet_name}")
            return None

        try:
            url = self._csv_url(gid)
            df = pd.read_csv(url)
            df = df.dropna(how="all")
            logger.info(f"Loaded {len(df)} rows from {sheet_name} sheet")
            return df
        except Exception as e:
            logger.error(f"Failed to load {sheet_name} sheet: {e}")
            return None

    async def load_all_sheets(self) -> Dict[str, pd.DataFrame]:
        """Load all configured sheets.

        Returns:
            Dictionary mapping sheet names to DataFrames
        """
        sheets = {}

        for sheet_name in self.gid_config.keys():
            df = self.load_sheet(sheet_name)
            if df is not None:
                sheets[sheet_name] = df

        logger.info(f"Loaded {len(sheets)} sheets successfully")
        return sheets
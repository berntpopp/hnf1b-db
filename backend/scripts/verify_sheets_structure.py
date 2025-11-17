#!/usr/bin/env python3
"""Data discovery script to verify Google Sheets structure for reviewer import.

This script MUST be run before implementing the curation system to verify:
1. ReviewBy column format in Individuals sheet
2. Reviewers sheet structure and data quality
3. Join strategy feasibility
4. Data completeness and match rates

Critical for Phase 0 of Milestone 5 implementation.
"""

import logging
import sys
from typing import Dict, Optional

import pandas as pd
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, "/mnt/c/development/hnf1b-db/backend")

from migration.data_sources.google_sheets import GoogleSheetsLoader

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Google Sheets configuration
SPREADSHEET_ID = "1jE4-HmyAh1FUK6Ph7AuHt2UDVW2mTINTWXBtAWqhVSw"
GID_CONFIG = {
    "individuals": "0",
    "reviewers": "1321366018",
}


class SheetsStructureVerifier:
    """Verifies Google Sheets structure for reviewer import."""

    def __init__(self):
        """Initialize verifier with Google Sheets loader."""
        self.sheets_loader = GoogleSheetsLoader(SPREADSHEET_ID, GID_CONFIG)
        self.individuals_df: Optional[pd.DataFrame] = None
        self.reviewers_df: Optional[pd.DataFrame] = None

    def load_sheets(self) -> bool:
        """Load both Individuals and Reviewers sheets.

        Returns:
            True if both sheets loaded successfully
        """
        logger.info("Loading Google Sheets data...")

        self.individuals_df = self.sheets_loader.load_sheet("individuals")
        if self.individuals_df is None:
            logger.error("Failed to load Individuals sheet")
            return False

        self.reviewers_df = self.sheets_loader.load_sheet("reviewers")
        if self.reviewers_df is None:
            logger.error("Failed to load Reviewers sheet")
            return False

        logger.info("✅ Both sheets loaded successfully")
        return True

    def analyze_reviewby_column(self) -> Dict[str, any]:
        """Analyze ReviewBy column in Individuals sheet.

        Returns:
            Dictionary with analysis results
        """
        assert self.individuals_df is not None, "Individuals sheet not loaded"

        logger.info("\n" + "=" * 70)
        logger.info("ANALYZING REVIEWBY COLUMN")
        logger.info("=" * 70)

        # Check if ReviewBy column exists
        if "ReviewBy" not in self.individuals_df.columns:
            logger.error("❌ ReviewBy column not found in Individuals sheet!")
            logger.info(f"Available columns: {list(self.individuals_df.columns)}")
            return {"exists": False}

        reviewby_col = self.individuals_df["ReviewBy"]

        # Count non-null values
        total_rows = len(self.individuals_df)
        non_null = reviewby_col.notna().sum()
        null_count = reviewby_col.isna().sum()

        logger.info(f"Total rows in Individuals sheet: {total_rows}")
        logger.info(
            f"Rows with ReviewBy data: {non_null} ({non_null * 100 / total_rows:.1f}%)"
        )
        logger.info(
            f"Rows without ReviewBy: {null_count} "
            f"({null_count * 100 / total_rows:.1f}%)"
        )

        # Analyze unique values
        unique_values = reviewby_col.dropna().unique()
        logger.info(f"Unique ReviewBy values: {len(unique_values)}")

        # Show sample values
        sample_values = reviewby_col.dropna().head(10).tolist()
        logger.info(f"Sample ReviewBy values: {sample_values}")

        # Check for multiple reviewers (comma-separated, semicolon-separated, etc.)
        multi_reviewer_indicators = [",", ";", "and", "&"]
        multi_reviewer_count = 0
        for value in reviewby_col.dropna():
            if any(indicator in str(value) for indicator in multi_reviewer_indicators):
                multi_reviewer_count += 1

        if multi_reviewer_count > 0:
            logger.warning(
                f"⚠️  Found {multi_reviewer_count} rows with multiple reviewers "
                f"({multi_reviewer_count * 100 / non_null:.1f}% of non-null)"
            )
            # Show examples
            multi_examples = [
                str(v)
                for v in reviewby_col.dropna()
                if any(ind in str(v) for ind in multi_reviewer_indicators)
            ][:5]
            logger.info(f"Examples: {multi_examples}")

        return {
            "exists": True,
            "total_rows": total_rows,
            "non_null": non_null,
            "null_count": null_count,
            "coverage_percent": non_null * 100 / total_rows,
            "unique_values": len(unique_values),
            "has_multi_reviewers": multi_reviewer_count > 0,
            "multi_reviewer_count": multi_reviewer_count,
            "sample_values": sample_values,
        }

    def analyze_reviewers_sheet(self) -> Dict[str, any]:
        """Analyze Reviewers sheet structure.

        Returns:
            Dictionary with analysis results
        """
        assert self.reviewers_df is not None, "Reviewers sheet not loaded"

        logger.info("\n" + "=" * 70)
        logger.info("ANALYZING REVIEWERS SHEET")
        logger.info("=" * 70)

        logger.info(f"Total reviewers: {len(self.reviewers_df)}")
        logger.info(f"Columns: {list(self.reviewers_df.columns)}")

        # Check for required columns
        required_columns = ["email", "name"]  # Minimum required
        optional_columns = ["orcid", "affiliation", "reviewer_id"]

        missing_required = [
            col for col in required_columns if col not in self.reviewers_df.columns
        ]
        if missing_required:
            logger.error(f"❌ Missing required columns: {missing_required}")

        present_optional = [
            col for col in optional_columns if col in self.reviewers_df.columns
        ]
        logger.info(f"Optional columns present: {present_optional}")

        # Analyze each column
        for col in self.reviewers_df.columns:
            non_null = self.reviewers_df[col].notna().sum()
            total = len(self.reviewers_df)
            logger.info(
                f"  {col}: {non_null}/{total} non-null ({non_null * 100 / total:.1f}%)"
            )

        # Show sample data
        logger.info("\nSample reviewer data (first 5):")
        print(self.reviewers_df.head().to_string())

        return {
            "total_reviewers": len(self.reviewers_df),
            "columns": list(self.reviewers_df.columns),
            "missing_required": missing_required,
            "present_optional": present_optional,
        }

    def test_join_strategy(self) -> Dict[str, any]:
        """Test join strategy between ReviewBy and Reviewers.

        Returns:
            Dictionary with join analysis results
        """
        assert self.individuals_df is not None, "Individuals sheet not loaded"
        assert self.reviewers_df is not None, "Reviewers sheet not loaded"

        logger.info("\n" + "=" * 70)
        logger.info("TESTING JOIN STRATEGY")
        logger.info("=" * 70)

        # Check if we have the columns we need
        if "ReviewBy" not in self.individuals_df.columns:
            logger.error("❌ Cannot test join - ReviewBy column missing")
            return {"success": False, "error": "ReviewBy column missing"}

        # Determine which column to use for joining from Reviewers sheet
        join_columns = []
        if "email" in self.reviewers_df.columns:
            join_columns.append("email")
        if "name" in self.reviewers_df.columns:
            join_columns.append("name")

        if not join_columns:
            logger.error("❌ Cannot test join - no email or name column in Reviewers")
            return {"success": False, "error": "No join column in Reviewers"}

        results = {}

        for join_col in join_columns:
            logger.info(f"\n--- Testing join on '{join_col}' ---")

            # Get all unique ReviewBy values (non-null)
            reviewby_values = set(
                str(v).strip().lower() for v in self.individuals_df["ReviewBy"].dropna()
            )

            # Get all reviewer values from the join column
            reviewer_values = set(
                str(v).strip().lower() for v in self.reviewers_df[join_col].dropna()
            )

            # Calculate matches
            matches = reviewby_values.intersection(reviewer_values)
            unmatched = reviewby_values - reviewer_values

            match_rate = (
                len(matches) / len(reviewby_values) * 100 if reviewby_values else 0
            )

            logger.info(f"ReviewBy unique values: {len(reviewby_values)}")
            logger.info(f"Reviewer {join_col} values: {len(reviewer_values)}")
            logger.info(f"Matches: {len(matches)} ({match_rate:.1f}%)")
            logger.info(f"Unmatched: {len(unmatched)} ({100 - match_rate:.1f}%)")

            if match_rate < 80:
                logger.warning(
                    "⚠️  Match rate is below 80%! "
                    "May need fuzzy matching or data cleanup."
                )

            # Show sample unmatched values
            if unmatched:
                sample_unmatched = list(unmatched)[:10]
                logger.info(f"Sample unmatched ReviewBy values: {sample_unmatched}")

            results[join_col] = {
                "reviewby_count": len(reviewby_values),
                "reviewer_count": len(reviewer_values),
                "matches": len(matches),
                "unmatched": len(unmatched),
                "match_rate": match_rate,
                "sample_unmatched": list(unmatched)[:10] if unmatched else [],
            }

        # Determine best join column
        best_join = max(results.keys(), key=lambda k: results[k]["match_rate"])
        best_rate = results[best_join]["match_rate"]
        logger.info(
            f"\n✅ Best join column: '{best_join}' "
            f"({best_rate:.1f}% match rate)"
        )

        return {
            "success": True,
            "results": results,
            "best_join_column": best_join,
            "best_match_rate": results[best_join]["match_rate"],
        }

    def check_review_date(self) -> Dict[str, any]:
        """Check ReviewDate column if it exists.

        Returns:
            Dictionary with ReviewDate analysis
        """
        assert self.individuals_df is not None, "Individuals sheet not loaded"

        logger.info("\n" + "=" * 70)
        logger.info("CHECKING REVIEWDATE COLUMN")
        logger.info("=" * 70)

        if "ReviewDate" not in self.individuals_df.columns:
            logger.warning("⚠️  ReviewDate column not found")
            return {"exists": False}

        reviewdate_col = self.individuals_df["ReviewDate"]

        total = len(self.individuals_df)
        non_null = reviewdate_col.notna().sum()

        logger.info(
            f"Rows with ReviewDate: {non_null}/{total} ({non_null * 100 / total:.1f}%)"
        )

        # Show sample values
        sample_values = reviewdate_col.dropna().head(10).tolist()
        logger.info(f"Sample ReviewDate values: {sample_values}")

        # Try to parse as dates
        try:
            parsed_dates = pd.to_datetime(reviewdate_col.dropna(), errors="coerce")
            valid_dates = parsed_dates.notna().sum()
            valid_pct = valid_dates * 100 / non_null
            logger.info(
                f"Valid date formats: {valid_dates}/{non_null} ({valid_pct:.1f}%)"
            )

            if valid_dates > 0:
                logger.info(f"Date range: {parsed_dates.min()} to {parsed_dates.max()}")
        except Exception as e:
            logger.warning(f"Could not parse dates: {e}")

        return {
            "exists": True,
            "non_null": non_null,
            "total": total,
            "coverage_percent": non_null * 100 / total,
            "sample_values": sample_values,
        }

    def generate_recommendations(
        self, reviewby_analysis: Dict, join_analysis: Dict
    ) -> None:
        """Generate implementation recommendations.

        Args:
            reviewby_analysis: Results from ReviewBy analysis
            join_analysis: Results from join strategy testing
        """
        logger.info("\n" + "=" * 70)
        logger.info("RECOMMENDATIONS")
        logger.info("=" * 70)

        if not reviewby_analysis.get("exists"):
            logger.error("❌ BLOCKER: ReviewBy column does not exist!")
            logger.error(
                "   Cannot proceed with implementation until this is resolved."
            )
            return

        if not join_analysis.get("success"):
            logger.error("❌ BLOCKER: Cannot establish join strategy!")
            logger.error(
                "   Cannot proceed with implementation until this is resolved."
            )
            return

        match_rate = join_analysis.get("best_match_rate", 0)
        best_join = join_analysis.get("best_join_column", "unknown")

        if match_rate >= 90:
            logger.info(f"✅ EXCELLENT: {match_rate:.1f}% match rate on '{best_join}'")
            logger.info("   Can proceed with direct join strategy")
        elif match_rate >= 80:
            logger.info(f"✅ GOOD: {match_rate:.1f}% match rate on '{best_join}'")
            logger.info("   Recommend data cleanup for unmatched values")
        elif match_rate >= 60:
            logger.warning(
                f"⚠️  MODERATE: {match_rate:.1f}% match rate on '{best_join}'"
            )
            logger.warning("   Recommend fuzzy matching or manual review")
        else:
            logger.error(f"❌ POOR: {match_rate:.1f}% match rate on '{best_join}'")
            logger.error("   Data quality issues - need significant cleanup")

        # Check for multi-reviewer handling
        if reviewby_analysis.get("has_multi_reviewers"):
            count = reviewby_analysis.get("multi_reviewer_count", 0)
            logger.warning(f"⚠️  Need to handle {count} rows with multiple reviewers")
            logger.info("   Recommendation: Split and create multiple user links")

        # Overall readiness assessment
        logger.info("\n" + "=" * 70)
        if match_rate >= 80 and reviewby_analysis.get("coverage_percent", 0) >= 50:
            logger.info("✅ READY TO PROCEED with Phase 1 implementation")
        elif match_rate >= 60:
            logger.warning("⚠️  PROCEED WITH CAUTION - data cleanup recommended")
        else:
            logger.error("❌ NOT READY - resolve data quality issues first")
        logger.info("=" * 70)


def main():
    """Run the complete verification process."""
    verifier = SheetsStructureVerifier()

    # Load sheets
    if not verifier.load_sheets():
        logger.error("Failed to load sheets - exiting")
        sys.exit(1)

    # Run analyses
    reviewby_analysis = verifier.analyze_reviewby_column()
    _ = verifier.analyze_reviewers_sheet()  # Prints to console
    join_analysis = verifier.test_join_strategy()
    _ = verifier.check_review_date()  # Prints to console

    # Generate recommendations
    verifier.generate_recommendations(reviewby_analysis, join_analysis)

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("VERIFICATION COMPLETE")
    logger.info("=" * 70)
    logger.info(
        "Review the output above and document findings in the implementation plan."
    )
    logger.info("Only proceed to Phase 1 if match rate >= 80%.")


if __name__ == "__main__":
    main()

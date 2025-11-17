"""Reviewer mapping for phenopacket curation attribution.

Maps reviewer email addresses from Google Sheets to reviewer data,
enabling proper attribution of who reviewed each case.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from migration.phenopackets.base_mapper import SheetMapper

logger = logging.getLogger(__name__)


class ReviewerMapper(SheetMapper):
    """Maps reviewer emails to reviewer data from Google Sheets.

    The Reviewers sheet contains user information including email, name,
    ORCID, and role. This mapper enables looking up reviewer details by
    email address for proper curation attribution.

    Expected columns in Reviewers sheet:
        - email (required, primary key)
        - user_name (optional, for username generation)
        - first_name (optional)
        - family_name (optional)
        - orcid (optional)
        - user_role (optional, e.g., "Reviewer", "Administrator")
        - user_id (optional, legacy ID from original system)
    """

    def _get_map_name(self) -> str:
        """Get human-readable name for logging.

        Returns:
            "reviewer"
        """
        return "reviewer"

    def _get_key_columns(self) -> List[str]:
        """Get columns to use as lookup keys.

        Reviewers are indexed by email address, which is used in the
        ReviewBy column of the Individuals sheet.

        Returns:
            ["email"] - primary lookup key
        """
        return ["email"]

    def get_reviewer_data(self, email: str) -> Optional[Dict[str, Any]]:
        """Get complete reviewer data by email address.

        Args:
            email: Reviewer email address (case-insensitive)

        Returns:
            Dictionary with reviewer data, or None if not found

        Example:
            {
                "email": "john.doe@example.com",
                "user_name": "john.doe",
                "first_name": "John",
                "family_name": "Doe",
                "orcid": "0000-0001-2345-6789",
                "user_role": "Reviewer"
            }
        """
        if not email:
            return None

        # Normalize email to lowercase for case-insensitive lookup
        email_normalized = email.strip().lower()

        # Try direct lookup first
        row_data = self.get_as_dict(email_normalized)
        if row_data:
            return row_data

        # If not found, try case-insensitive search in all keys
        for key, row in self.data_map.items():
            if key.lower() == email_normalized:
                return row.to_dict() if hasattr(row, "to_dict") else row

        return None

    def generate_username(self, email: str) -> str:
        """Generate username from email address.

        Creates a username by taking the local part of the email
        (before @) and normalizing it.

        Args:
            email: Email address

        Returns:
            Username (e.g., "john.doe" from "john.doe@example.com")

        Example:
            >>> mapper.generate_username("John.Doe@Example.com")
            "john.doe"
        """
        if not email:
            return ""

        # Extract local part before @
        local_part = email.split("@")[0] if "@" in email else email

        # Normalize: lowercase, replace non-alphanumeric with underscore
        username = local_part.strip().lower()

        # Replace dots with underscores for database safety
        # (some databases don't allow dots in usernames)
        username = username.replace(".", "_")

        return username

    def get_full_name(self, email: str) -> Optional[str]:
        """Get reviewer's full name.

        Combines first_name and family_name if available.

        Args:
            email: Reviewer email address

        Returns:
            Full name as "FirstName FamilyName", or None if not found

        Example:
            >>> mapper.get_full_name("john.doe@example.com")
            "John Doe"
        """
        reviewer_data = self.get_reviewer_data(email)
        if not reviewer_data:
            return None

        first_name = reviewer_data.get("first_name")
        family_name = reviewer_data.get("family_name")

        if first_name and family_name:
            # Handle pandas NA/NaN values
            if pd.notna(first_name) and pd.notna(family_name):
                return f"{first_name} {family_name}".strip()

        # Fallback to user_name if available
        user_name = reviewer_data.get("user_name")
        if user_name and pd.notna(user_name):
            return str(user_name)

        return None

    def get_orcid(self, email: str) -> Optional[str]:
        """Get reviewer's ORCID identifier.

        Args:
            email: Reviewer email address

        Returns:
            ORCID identifier (e.g., "0000-0001-2345-6789"), or None

        Example:
            >>> mapper.get_orcid("john.doe@example.com")
            "0000-0001-2345-6789"
        """
        reviewer_data = self.get_reviewer_data(email)
        if not reviewer_data:
            return None

        orcid = reviewer_data.get("orcid")
        if orcid and pd.notna(orcid):
            return str(orcid).strip()

        return None

    def get_role(self, email: str) -> str:
        """Get reviewer's role.

        Args:
            email: Reviewer email address

        Returns:
            Role string (e.g., "Reviewer", "Administrator"), defaults to "curator"

        Note:
            Maps Google Sheets roles to application roles:
            - "Administrator" -> "admin"
            - "Reviewer" -> "curator"
            - Others -> "curator" (default)
        """
        reviewer_data = self.get_reviewer_data(email)
        if not reviewer_data:
            return "curator"  # Default role

        user_role = reviewer_data.get("user_role")
        if not user_role or pd.isna(user_role):
            return "curator"

        role_str = str(user_role).strip()

        # Map Google Sheets roles to application roles
        role_mapping = {
            "Administrator": "admin",
            "Reviewer": "curator",
        }

        return role_mapping.get(role_str, "curator")

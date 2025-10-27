"""Tests for audit logging functionality.

This module tests the audit logging for GDPR compliance and security monitoring.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from app.utils.audit_logger import (
    log_rate_limit_exceeded,
    log_validation_error,
    log_variant_search,
)


class TestVariantSearchLogging:
    """Test variant search audit logging."""

    @patch('app.utils.audit_logger.audit_logger')
    def test_log_variant_search_all_fields(self, mock_logger):
        """Test logging with all search criteria filled."""
        log_variant_search(
            client_ip="192.168.1.100",
            user_id="user@example.com",
            query="c.1654-2A>T",
            variant_type="SNV",
            classification="PATHOGENIC",
            gene="HNF1B",
            consequence="Splice Acceptor",
            result_count=5,
            request_path="/api/v2/phenopackets/aggregate/all-variants",
        )

        # Verify logger.info was called
        mock_logger.info.assert_called_once()

        # Verify event name
        args, kwargs = mock_logger.info.call_args
        assert args[0] == "VARIANT_SEARCH"

        # Verify extra data
        extra = kwargs["extra"]
        assert extra["event"] == "VARIANT_SEARCH"
        assert extra["client_ip"] == "192.168.1.100"
        assert extra["user_id"] == "user@example.com"
        assert extra["result_count"] == 5
        assert extra["request_path"] == "/api/v2/phenopackets/aggregate/all-variants"

        # Verify search criteria
        criteria = extra["search_criteria"]
        assert criteria["query"] == "c.1654-2A>T"
        assert criteria["variant_type"] == "SNV"
        assert criteria["classification"] == "PATHOGENIC"
        assert criteria["gene"] == "HNF1B"
        assert criteria["consequence"] == "Splice Acceptor"

    @patch('app.utils.audit_logger.audit_logger')
    def test_log_variant_search_minimal_fields(self, mock_logger):
        """Test logging with minimal fields (only required)."""
        log_variant_search(
            client_ip="192.168.1.100",
            user_id=None,
            query=None,
            variant_type=None,
            classification=None,
            gene=None,
            consequence=None,
            result_count=0,
            request_path="/api/v2/phenopackets/aggregate/all-variants",
        )

        # Verify logger.info was called
        mock_logger.info.assert_called_once()

        args, kwargs = mock_logger.info.call_args
        extra = kwargs["extra"]

        # Verify anonymous user
        assert extra["user_id"] == "anonymous"

        # Verify empty search criteria (no None values)
        criteria = extra["search_criteria"]
        assert criteria == {}  # Should be empty dict, not contain None values

    @patch('app.utils.audit_logger.audit_logger')
    def test_log_variant_search_partial_filters(self, mock_logger):
        """Test logging with some filters applied."""
        log_variant_search(
            client_ip="192.168.1.100",
            user_id="user@example.com",
            query="c.1654",
            variant_type=None,
            classification="PATHOGENIC",
            gene=None,
            consequence=None,
            result_count=10,
            request_path="/api/v2/phenopackets/aggregate/all-variants",
        )

        args, kwargs = mock_logger.info.call_args
        extra = kwargs["extra"]
        criteria = extra["search_criteria"]

        # Only query and classification should be in criteria
        assert "query" in criteria
        assert "classification" in criteria
        assert "variant_type" not in criteria  # Should not include None values
        assert "gene" not in criteria
        assert "consequence" not in criteria

    @patch('app.utils.audit_logger.audit_logger')
    def test_log_includes_timestamp(self, mock_logger):
        """Test that log includes ISO formatted timestamp."""
        log_variant_search(
            client_ip="192.168.1.100",
            user_id=None,
            query=None,
            variant_type=None,
            classification=None,
            gene=None,
            consequence=None,
            result_count=0,
            request_path="/api/v2/phenopackets/aggregate/all-variants",
        )

        args, kwargs = mock_logger.info.call_args
        extra = kwargs["extra"]

        # Verify timestamp exists and ends with Z (UTC)
        assert "timestamp" in extra
        assert extra["timestamp"].endswith("Z")


class TestRateLimitLogging:
    """Test rate limit violation logging."""

    @patch('app.utils.audit_logger.audit_logger')
    def test_log_rate_limit_exceeded(self, mock_logger):
        """Test logging of rate limit violations."""
        log_rate_limit_exceeded(
            client_ip="192.168.1.100",
            request_count=15,
            request_path="/api/v2/phenopackets/aggregate/all-variants",
        )

        # Verify logger.warning was called (not info)
        mock_logger.warning.assert_called_once()

        args, kwargs = mock_logger.warning.call_args
        assert args[0] == "RATE_LIMIT_EXCEEDED"

        extra = kwargs["extra"]
        assert extra["event"] == "RATE_LIMIT_EXCEEDED"
        assert extra["client_ip"] == "192.168.1.100"
        assert extra["request_count"] == 15
        assert extra["severity"] == "WARNING"


class TestValidationErrorLogging:
    """Test validation error logging."""

    @patch('app.utils.audit_logger.audit_logger')
    def test_log_sql_injection_attempt(self, mock_logger):
        """Test logging of SQL injection attempts."""
        log_validation_error(
            client_ip="192.168.1.100",
            user_id=None,
            error_type="SQL_INJECTION_ATTEMPT",
            invalid_input="'; DROP TABLE phenopackets;--",
            error_message="Search query contains invalid characters",
            request_path="/api/v2/phenopackets/aggregate/all-variants",
        )

        # Verify logger.warning was called
        mock_logger.warning.assert_called_once()

        args, kwargs = mock_logger.warning.call_args
        assert args[0] == "VALIDATION_ERROR"

        extra = kwargs["extra"]
        assert extra["event"] == "VALIDATION_ERROR"
        assert extra["error_type"] == "SQL_INJECTION_ATTEMPT"
        assert extra["invalid_input"] == "'; DROP TABLE phenopackets;--"
        assert extra["severity"] == "WARNING"

    @patch('app.utils.audit_logger.audit_logger')
    def test_log_invalid_hgvs(self, mock_logger):
        """Test logging of invalid HGVS notation."""
        log_validation_error(
            client_ip="192.168.1.100",
            user_id="user@example.com",
            error_type="INVALID_HGVS",
            invalid_input="c.invalid",
            error_message="Invalid HGVS notation format: c.invalid",
            request_path="/api/v2/phenopackets/aggregate/all-variants",
        )

        mock_logger.warning.assert_called_once()

        args, kwargs = mock_logger.warning.call_args
        extra = kwargs["extra"]

        assert extra["error_type"] == "INVALID_HGVS"
        assert extra["user_id"] == "user@example.com"


class TestAuditLoggerConfiguration:
    """Test audit logger configuration."""

    def test_audit_logger_exists(self):
        """Test that audit logger is properly configured."""
        from app.utils.audit_logger import audit_logger

        assert audit_logger is not None
        assert audit_logger.name == "audit"
        assert audit_logger.level == logging.INFO

    @patch('logging.FileHandler')
    @patch('os.makedirs')
    def test_configure_file_handler(self, mock_makedirs, mock_file_handler):
        """Test configuring audit logger with file handler."""
        from app.utils.audit_logger import configure_audit_logger

        # Mock file handler
        mock_handler = MagicMock()
        mock_handler.level = logging.INFO  # Set level attribute for comparison
        mock_file_handler.return_value = mock_handler

        # Configure with custom path
        configure_audit_logger("/var/log/hnf1b/audit.log")

        # Verify directory creation
        mock_makedirs.assert_called_once_with("/var/log/hnf1b", exist_ok=True)

        # Verify file handler created
        mock_file_handler.assert_called_once_with("/var/log/hnf1b/audit.log")

        # Verify handler added to logger
        mock_handler.setLevel.assert_called_once_with(logging.INFO)

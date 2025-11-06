"""Tests for audit logging functionality.

This module tests the audit logging for GDPR compliance and security monitoring.

Uses pytest's caplog fixture to capture actual log output (best practice for testing logging).
"""

import logging

from app.utils.audit_logger import (
    configure_audit_logger,
    log_rate_limit_exceeded,
    log_validation_error,
    log_variant_search,
)


class TestVariantSearchLogging:
    """Test variant search audit logging."""

    def test_log_variant_search_all_fields(self, caplog):
        """Test logging with all search criteria filled."""
        with caplog.at_level(logging.INFO, logger="audit"):
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
        assert len(caplog.records) == 1
        record = caplog.records[0]

        # Verify event name
        assert record.message == "VARIANT_SEARCH"
        assert record.levelname == "INFO"

        # Verify extra data exists
        assert hasattr(record, "event")
        assert record.event == "VARIANT_SEARCH"
        assert record.client_ip == "192.168.1.100"
        assert record.user_id == "user@example.com"
        assert record.result_count == 5
        assert record.request_path == "/api/v2/phenopackets/aggregate/all-variants"

        # Verify search criteria
        assert hasattr(record, "search_criteria")
        criteria = record.search_criteria
        assert criteria["query"] == "c.1654-2A>T"
        assert criteria["variant_type"] == "SNV"
        assert criteria["classification"] == "PATHOGENIC"
        assert criteria["gene"] == "HNF1B"
        assert criteria["consequence"] == "Splice Acceptor"

    def test_log_variant_search_minimal_fields(self, caplog):
        """Test logging with minimal fields (only required)."""
        with caplog.at_level(logging.INFO, logger="audit"):
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

        assert len(caplog.records) == 1
        record = caplog.records[0]

        # Verify anonymous user
        assert record.user_id == "anonymous"

        # Verify empty search criteria (no None values)
        criteria = record.search_criteria
        assert criteria == {}  # Should be empty dict, not contain None values

    def test_log_variant_search_partial_filters(self, caplog):
        """Test logging with some filters applied."""
        with caplog.at_level(logging.INFO, logger="audit"):
            log_variant_search(
                client_ip="192.168.1.100",
                user_id="user@example.com",
                query="c.1654",
                variant_type=None,
                classification="PATHOGENIC",
                gene=None,
                consequence=None,
                result_count=3,
                request_path="/api/v2/phenopackets/aggregate/all-variants",
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        criteria = record.search_criteria

        # Only query and classification should be in criteria
        assert "query" in criteria
        assert "classification" in criteria
        assert "variant_type" not in criteria  # Should not include None values
        assert "gene" not in criteria
        assert "consequence" not in criteria

    def test_log_includes_timestamp(self, caplog):
        """Test that log includes ISO formatted timestamp."""
        with caplog.at_level(logging.INFO, logger="audit"):
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

        assert len(caplog.records) == 1
        record = caplog.records[0]

        # Verify timestamp exists and ends with Z (UTC)
        assert hasattr(record, "timestamp")
        assert record.timestamp.endswith("Z")


class TestRateLimitLogging:
    """Test rate limit violation logging."""

    def test_log_rate_limit_exceeded(self, caplog):
        """Test logging of rate limit violations."""
        with caplog.at_level(logging.WARNING, logger="audit"):
            log_rate_limit_exceeded(
                client_ip="192.168.1.100",
                request_count=15,
                request_path="/api/v2/phenopackets/aggregate/all-variants",
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]

        assert record.message == "RATE_LIMIT_EXCEEDED"
        assert record.levelname == "WARNING"

        assert record.event == "RATE_LIMIT_EXCEEDED"
        assert record.client_ip == "192.168.1.100"
        assert record.request_count == 15
        assert record.severity == "WARNING"


class TestValidationErrorLogging:
    """Test validation error logging."""

    def test_log_sql_injection_attempt(self, caplog):
        """Test logging of SQL injection attempts."""
        with caplog.at_level(logging.WARNING, logger="audit"):
            log_validation_error(
                client_ip="192.168.1.100",
                user_id=None,
                error_type="SQL_INJECTION_ATTEMPT",
                invalid_input="'; DROP TABLE phenopackets;--",
                error_message="Search query contains invalid characters",
                request_path="/api/v2/phenopackets/aggregate/all-variants",
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]

        assert record.message == "VALIDATION_ERROR"
        assert record.levelname == "WARNING"

        assert record.event == "VALIDATION_ERROR"
        assert record.error_type == "SQL_INJECTION_ATTEMPT"
        assert record.invalid_input == "'; DROP TABLE phenopackets;--"
        assert record.severity == "WARNING"

    def test_log_invalid_hgvs(self, caplog):
        """Test logging of invalid HGVS notation."""
        with caplog.at_level(logging.WARNING, logger="audit"):
            log_validation_error(
                client_ip="192.168.1.100",
                user_id="user@example.com",
                error_type="INVALID_HGVS",
                invalid_input="c.invalid",
                error_message="Invalid HGVS notation format: c.invalid",
                request_path="/api/v2/phenopackets/search",
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]

        assert record.event == "VALIDATION_ERROR"
        assert record.user_id == "user@example.com"
        assert record.error_type == "INVALID_HGVS"
        assert record.invalid_input == "c.invalid"


class TestAuditLoggerConfiguration:
    """Test audit logger configuration."""

    def test_audit_logger_exists(self):
        """Test that audit logger exists and is properly configured."""
        audit_logger = logging.getLogger("audit")
        assert audit_logger is not None
        assert audit_logger.level == logging.INFO

    def test_configure_file_handler(self, tmp_path):
        """Test configuring audit logger with file handler."""
        log_file = tmp_path / "test_audit.log"
        configure_audit_logger(str(log_file))

        audit_logger = logging.getLogger("audit")
        # Verify file handler was added
        assert len(audit_logger.handlers) > 0

        # Verify log file was created
        assert log_file.exists()

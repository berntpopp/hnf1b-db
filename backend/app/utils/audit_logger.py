"""Audit logging for variant search queries (GDPR compliance).

This module provides structured logging for all variant search queries,
capturing user actions, filters applied, and results returned for audit
trail and compliance purposes.
"""

import logging
from datetime import datetime
from typing import Optional

# Create dedicated audit logger
# In production, configure this to write to a separate log file
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)


def log_variant_search(
    client_ip: str,
    user_id: Optional[str],
    query: Optional[str],
    variant_type: Optional[str],
    classification: Optional[str],
    gene: Optional[str],
    consequence: Optional[str],
    result_count: int,
    request_path: str,
) -> None:
    """Log variant search query for audit trail.

    Args:
        client_ip: Client IP address
        user_id: Authenticated user ID (if available, otherwise "anonymous")
        query: Search query text (HGVS notation, variant ID, etc.)
        variant_type: Variant type filter applied
        classification: Classification filter applied
        gene: Gene filter applied
        consequence: Molecular consequence filter applied
        result_count: Number of results returned
        request_path: Full request path/URL

    Audit Log Format:
        Structured JSON log entry with timestamp, user info, search criteria,
        and results count.

    GDPR Compliance:
        - Logs search queries (not actual patient data)
        - Captures user actions for accountability
        - Enables data access auditing
        - Can be used to demonstrate compliance with data protection regulations

    Example Log Entry:
        {
            "event": "VARIANT_SEARCH",
            "timestamp": "2025-10-27T12:34:56.789Z",
            "client_ip": "192.168.1.100",
            "user_id": "user@example.com",
            "search_criteria": {
                "query": "c.1654-2A>T",
                "variant_type": "SNV",
                "classification": "PATHOGENIC",
                "gene": "HNF1B",
                "consequence": "Splice Acceptor"
            },
            "result_count": 3,
            "request_path": "/api/v2/phenopackets/aggregate/all-variants"
        }
    """
    # Build search criteria dictionary (only include non-None values)
    search_criteria = {}
    if query:
        search_criteria["query"] = query
    if variant_type:
        search_criteria["variant_type"] = variant_type
    if classification:
        search_criteria["classification"] = classification
    if gene:
        search_criteria["gene"] = gene
    if consequence:
        search_criteria["consequence"] = consequence

    # Create structured log entry
    log_entry = {
        "event": "VARIANT_SEARCH",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "client_ip": client_ip,
        "user_id": user_id or "anonymous",
        "search_criteria": search_criteria,
        "result_count": result_count,
        "request_path": request_path,
    }

    # Log as structured JSON (easy to parse for analysis)
    audit_logger.info("VARIANT_SEARCH", extra=log_entry)


def log_rate_limit_exceeded(
    client_ip: str,
    request_count: int,
    request_path: str,
) -> None:
    """Log rate limit violation for security monitoring.

    Args:
        client_ip: Client IP address that exceeded limit
        request_count: Number of requests made
        request_path: Request path that was rate limited

    Use Case:
        - Security monitoring for API abuse
        - Identify potential DDoS attempts
        - Track repeated violations for blocking
    """
    log_entry = {
        "event": "RATE_LIMIT_EXCEEDED",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "client_ip": client_ip,
        "request_count": request_count,
        "request_path": request_path,
        "severity": "WARNING",
    }

    audit_logger.warning("RATE_LIMIT_EXCEEDED", extra=log_entry)


def log_validation_error(
    client_ip: str,
    user_id: Optional[str],
    error_type: str,
    invalid_input: str,
    error_message: str,
    request_path: str,
) -> None:
    """Log input validation failures for security monitoring.

    Args:
        client_ip: Client IP address
        user_id: Authenticated user ID (if available)
        error_type: Type of validation error
            (e.g., "SQL_INJECTION_ATTEMPT", "INVALID_HGVS")
        invalid_input: The invalid input that was rejected
        error_message: Error message returned to user
        request_path: Request path

    Use Case:
        - Detect SQL injection attempts
        - Monitor for malicious inputs
        - Track repeated validation failures
    """
    log_entry = {
        "event": "VALIDATION_ERROR",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "client_ip": client_ip,
        "user_id": user_id or "anonymous",
        "error_type": error_type,
        "invalid_input": invalid_input,
        "error_message": error_message,
        "request_path": request_path,
        "severity": "WARNING",
    }

    audit_logger.warning("VALIDATION_ERROR", extra=log_entry)


def configure_audit_logger(log_file_path: Optional[str] = None) -> None:
    """Configure audit logger with file handler.

    Args:
        log_file_path: Path to audit log file (default: logs/audit.log)

    Production Setup:
        - Log to dedicated audit log file
        - Rotate logs daily
        - Retain logs for compliance period (e.g., 7 years for GDPR)
        - Send to centralized logging system (ELK, Splunk, etc.)

    Example:
        configure_audit_logger("/var/log/hnf1b/audit.log")
    """
    if log_file_path is None:
        log_file_path = "logs/audit.log"

    # Create file handler
    try:
        import os

        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(logging.INFO)

        # JSON formatter for structured logging
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"message": "%(message)s", %(extra)s}'
        )
        file_handler.setFormatter(formatter)

        # Add handler to audit logger
        audit_logger.addHandler(file_handler)

        audit_logger.info("AUDIT_LOGGER_CONFIGURED", extra={"log_file": log_file_path})
    except Exception as e:
        # If file logging fails, log to console
        audit_logger.error(
            f"Failed to configure audit logger file handler: {e}",
            extra={"error": str(e)},
        )


async def log_user_action(
    db,  # AsyncSession, but avoiding circular import
    user_id: int,
    action: str,
    details: str,
) -> None:
    """Log user management action.

    Args:
        db: Database session
        user_id: User ID
        action: Action type (LOGIN, LOGOUT, PASSWORD_CHANGE, etc.)
        details: Action details
    """
    # For now, just log to console
    # Future: Store in audit_log table
    logger = logging.getLogger(__name__)
    logger.info(f"User action: user_id={user_id}, action={action}, details={details}")

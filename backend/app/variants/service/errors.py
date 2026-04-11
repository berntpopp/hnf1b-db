"""VEP-related exception classes for the variants service.

Extracted from the monolithic ``variants/service.py`` during Wave 4.
Re-exported by the package ``__init__`` so existing imports keep
working unchanged.
"""


class VEPError(Exception):
    """Base exception for VEP API errors."""


class VEPRateLimitError(VEPError):
    """Rate limit exceeded (429)."""


class VEPNotFoundError(VEPError):
    """Variant not found or invalid format (400/404)."""


class VEPTimeoutError(VEPError):
    """API request timed out."""


class VEPAPIError(VEPError):
    """General API error."""

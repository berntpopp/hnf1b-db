# app/core/config.py
"""Unified configuration system: YAML (behavior) + .env (secrets).

This module provides a centralized configuration system that:
- Loads secrets from .env files (DATABASE_URL, JWT_SECRET, API keys)
- Loads behavior parameters from config.yaml (timeouts, limits, URLs)
- Provides type-safe access to all configuration values via Pydantic models

Usage:
    from app.core.config import settings

    # Access secrets (from .env)
    db_url = settings.DATABASE_URL

    # Access behavior config (from config.yaml)
    timeout = settings.external_apis.vep.timeout_seconds
    page_size = settings.pagination.default_page_size
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import List, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# ============================================================================
# YAML Configuration Models (Behavior - NOT secrets)
# ============================================================================


class PaginationConfig(BaseModel):
    """Pagination configuration."""

    default_page_size: int = 20
    max_page_size: int = 1000
    search_page_size: int = 20
    search_max_page_size: int = 100
    aggregation_page_size: int = 100
    aggregation_max_page_size: int = 500


class ApiRateLimitConfig(BaseModel):
    """API endpoint rate limiting."""

    requests_per_second: int = 5
    window_seconds: int = 1


class VepRateLimitConfig(BaseModel):
    """VEP rate limiting."""

    requests_per_second: int = 15


class PubmedRateLimitConfig(BaseModel):
    """PubMed rate limiting."""

    requests_per_second_with_key: int = 10
    requests_per_second_without_key: int = 3


class RateLimitingConfig(BaseModel):
    """All rate limiting configuration."""

    api: ApiRateLimitConfig = ApiRateLimitConfig()
    vep: VepRateLimitConfig = VepRateLimitConfig()
    pubmed: PubmedRateLimitConfig = PubmedRateLimitConfig()


class VepApiConfig(BaseModel):
    """Ensembl VEP API configuration."""

    base_url: str = "https://rest.ensembl.org"
    timeout_seconds: int = 60  # Increased for batch requests
    max_retries: int = 4  # More retries for resilience
    retry_backoff_factor: float = 2.0
    batch_size: int = 50  # VEP recommends max 200, but 50 is more reliable
    cache_enabled: bool = True
    cache_size_limit: int = 1000
    cache_ttl_seconds: int = 86400


class OlsApiConfig(BaseModel):
    """OLS API configuration for HPO terms."""

    base_url: str = "https://www.ebi.ac.uk/ols4/api"
    timeout_seconds: int = 10
    cache_size_limit: int = 100
    cache_ttl_seconds: int = 3600  # 1 hour


class PubmedApiConfig(BaseModel):
    """PubMed API configuration."""

    base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    timeout_seconds: int = 5
    version: str = "2.0"


class ExternalApisConfig(BaseModel):
    """External API configurations."""

    vep: VepApiConfig = VepApiConfig()
    ols: OlsApiConfig = OlsApiConfig()
    pubmed: PubmedApiConfig = PubmedApiConfig()


class DatabaseConfig(BaseModel):
    """Database connection pool configuration."""

    pool_size: int = 20
    max_overflow: int = 0
    pool_recycle_seconds: int = 3600
    command_timeout_seconds: int = 60
    pool_pre_ping: bool = True


class HttpCacheConfig(BaseModel):
    """HTTP response caching configuration."""

    aggregations_max_age_seconds: int = 300


class MaterializedViewsConfig(BaseModel):
    """Materialized views configuration for aggregation optimization."""

    enabled: bool = True
    auto_refresh_after_import: bool = True
    views: List[str] = [
        "mv_feature_aggregation",
        "mv_disease_aggregation",
        "mv_sex_distribution",
        "mv_summary_statistics",
    ]


class HPOTermsConfig(BaseModel):
    """HPO term constants for survival analysis and disease classification.

    Centralizes HPO term definitions that were previously hardcoded in survival.py.
    This allows for easier maintenance and testing without code changes.
    """

    # CAKUT (Congenital Anomalies of Kidney and Urinary Tract)
    cakut: List[str] = [
        "HP:0000003",  # Multicystic kidney dysplasia
        "HP:0000122",  # Unilateral renal agenesis
        "HP:0000089",  # Renal hypoplasia
        "HP:0012210",  # Abnormal renal morphology
    ]

    # Genital abnormalities
    genital: str = "HP:0000078"  # Abnormality of the genital system

    # Any kidney-related HPO terms
    any_kidney: List[str] = [
        "HP:0012622",  # Chronic kidney disease (unspecified)
        "HP:0012623",  # Stage 1 chronic kidney disease
        "HP:0012624",  # Stage 2 chronic kidney disease
        "HP:0012625",  # Stage 3 chronic kidney disease
        "HP:0012626",  # Stage 4 chronic kidney disease
        "HP:0003774",  # Stage 5 chronic kidney disease
        "HP:0000003",  # Multicystic kidney dysplasia
        "HP:0000089",  # Renal hypoplasia
        "HP:0000107",  # Renal cyst
        "HP:0000122",  # Unilateral renal agenesis
        "HP:0012210",  # Abnormal renal morphology
        "HP:0033133",  # Renal cortical hyperechogenicity
        "HP:0000108",  # Multiple glomerular cysts
        "HP:0001970",  # Oligomeganephronia
    ]

    # MODY (Maturity-onset diabetes of the young)
    mody: str = "HP:0004904"

    # CKD stage terms
    ckd_stages: List[str] = [
        "HP:0012622",  # Chronic kidney disease (unspecified)
        "HP:0012623",  # Stage 1 CKD
        "HP:0012624",  # Stage 2 CKD
        "HP:0012625",  # Stage 3 CKD
        "HP:0012626",  # Stage 4 CKD
        "HP:0003774",  # Stage 5 CKD
    ]

    # Kidney failure (Stage 4 and Stage 5 CKD)
    kidney_failure: List[str] = ["HP:0012626", "HP:0003774"]

    # CKD Stage 3+ (for survival analysis endpoint)
    ckd_stage_3_plus: List[str] = [
        "HP:0012625",  # Stage 3 CKD
        "HP:0012626",  # Stage 4 CKD
        "HP:0003774",  # Stage 5 CKD
    ]

    # Stage 5 CKD only (ESRD)
    stage_5_ckd: List[str] = ["HP:0003774"]

    # Scalar aliases for individual CKD stages — used where the call site
    # wants a single HPO ID string rather than a list (e.g. raw-SQL
    # literal filters or human-readable metadata descriptions).
    chronic_kidney_disease: str = "HP:0012622"  # CKD unspecified
    ckd_stage_4: str = "HP:0012626"  # Stage 4 CKD
    ckd_stage_5: str = "HP:0003774"  # Stage 5 CKD / ESRD


class SecurityConfig(BaseModel):
    """Security settings (non-secret values)."""

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_min_length: int = 8
    max_login_attempts: int = 5
    account_lockout_minutes: int = 15


class EmailConfig(BaseModel):
    """Email delivery configuration (non-secret behavioral settings)."""

    backend: Literal["console", "smtp"] = "console"
    from_address: str = "noreply@hnf1b-db.org"
    from_name: str = "HNF1B Database"
    tls_mode: Literal["starttls", "ssl", "none"] = "starttls"
    validate_certs: bool = True
    timeout_seconds: int = 30
    use_credentials: bool = True
    max_retries: int = 3
    retry_backoff_factor: float = 2.0


class YamlConfig(BaseModel):
    """Complete YAML configuration structure."""

    pagination: PaginationConfig = PaginationConfig()
    rate_limiting: RateLimitingConfig = RateLimitingConfig()
    external_apis: ExternalApisConfig = ExternalApisConfig()
    database: DatabaseConfig = DatabaseConfig()
    http_cache: HttpCacheConfig = HttpCacheConfig()
    materialized_views: MaterializedViewsConfig = MaterializedViewsConfig()
    hpo_terms: HPOTermsConfig = HPOTermsConfig()
    security: SecurityConfig = SecurityConfig()
    email: EmailConfig = EmailConfig()


def load_yaml_config() -> YamlConfig:
    """Load configuration from YAML file.

    Searches for config.yaml in multiple locations:
    1. Current working directory
    2. backend/ directory
    3. Same directory as this module's parent
    """
    config_paths = [
        Path("config.yaml"),
        Path("backend/config.yaml"),
        Path(__file__).parent.parent.parent / "config.yaml",
    ]

    for path in config_paths:
        if path.exists():
            logger.info(f"Loading configuration from {path.absolute()}")
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            return YamlConfig(**data)

    logger.warning("No config.yaml found, using defaults")
    return YamlConfig()


# ============================================================================
# Environment Settings (Secrets)
# ============================================================================


class Settings(BaseSettings):
    """Application settings combining .env secrets and YAML behavior config.

    Secrets (from .env):
        DATABASE_URL, JWT_SECRET, REDIS_URL, PUBMED_API_KEY

    Behavior config (from config.yaml):
        pagination, rate_limiting, external_apis, database, security
    """

    # === SECRETS (from .env - NEVER in YAML) ===
    DATABASE_URL: str = ""
    OLD_DATABASE_URL: Optional[str] = None  # For migration purposes
    JWT_SECRET: str = Field(default="")
    REDIS_URL: str = "redis://localhost:6379/0"
    ALLOW_REDIS_FALLBACK: Optional[bool] = None
    PUBMED_API_KEY: Optional[str] = None

    # SMTP credentials (for email delivery)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""

    # Admin credentials (for initial setup)
    # SECURITY: ADMIN_PASSWORD is REQUIRED and has no default. The previous
    # default was removed in Wave 1 of the 2026-04-10 refactor roadmap to
    # prevent credential leakage via git history. The application exits at
    # startup if ADMIN_PASSWORD is unset or empty.
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = "admin@hnf1b-db.local"
    ADMIN_PASSWORD: str = Field(default="")

    # CORS (can be in .env for flexibility)
    CORS_ORIGINS: str = (
        "http://localhost:3000,http://localhost:5173,http://localhost:8080"
    )

    # Debug mode
    DEBUG: bool = False

    # Auth cookie contract (Phase 2)
    REFRESH_COOKIE_NAME: str = "refresh_token"
    CSRF_COOKIE_NAME: str = "csrf_token"
    AUTH_COOKIE_PATH: str = "/api/v2"
    CSRF_COOKIE_PATH: str = "/"
    AUTH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    AUTH_COOKIE_SECURE: bool = False

    # === Environment and dev-mode gating (Wave 5a Layer 1) ===

    environment: Literal["development", "staging", "production"] = "production"
    enable_dev_auth: bool = False

    # === YAML CONFIG (lazy-loaded) ===
    _yaml_config: Optional[YamlConfig] = None

    model_config = SettingsConfigDict(env_file=".env")

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Fail fast if JWT_SECRET is missing.

        Raises ValueError if JWT_SECRET is not set to prevent running
        with insecure configuration. Using ValueError instead of sys.exit()
        allows proper error handling in tests and provides better stack traces.
        """
        if not v or v.strip() == "":
            logger.critical(
                "JWT_SECRET is empty or not set! "
                "Set JWT_SECRET in .env file for secure authentication. "
                "Example: JWT_SECRET=$(openssl rand -hex 32)"
            )
            raise ValueError(
                "JWT_SECRET is required. Set JWT_SECRET in .env file. "
                "Generate with: openssl rand -hex 32"
            )
        return v

    @field_validator("ADMIN_PASSWORD")
    @classmethod
    def validate_admin_password(cls, v: str) -> str:
        """Fail fast if ADMIN_PASSWORD is missing.

        Mirrors the JWT_SECRET validation pattern. ADMIN_PASSWORD must be
        set via the .env file for initial admin-user creation. The previous
        hardcoded default was removed to prevent credential leakage.
        """
        if not v or v.strip() == "":
            logger.critical(
                "ADMIN_PASSWORD is empty or not set! "
                "Set ADMIN_PASSWORD in .env file for initial admin user "
                "creation. This credential is required and has no default."
            )
            raise ValueError(
                "ADMIN_PASSWORD is required. Set ADMIN_PASSWORD in .env file "
                "to a strong unique password (min 12 characters recommended)."
            )
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def validate_cors_origins(cls, v: object) -> str:
        """Ensure CORS_ORIGINS is a string."""
        if isinstance(v, list):
            return ",".join(v)
        return str(v) if v else ""

    def get_cors_origins_list(self) -> List[str]:
        """Convert CORS_ORIGINS string to list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @model_validator(mode="after")
    def _refuse_dev_auth_in_prod(self) -> "Settings":
        """Fail fast if ENABLE_DEV_AUTH is True outside development.

        Wave 5a Layer 1 of the dev-mode 5-layer defense (review §5.3).
        An unset ENVIRONMENT must never be interpreted as dev — the
        default is production. This mirrors the JWT_SECRET / ADMIN_PASSWORD
        validators in that refusing to start is the right response to a
        dangerous misconfiguration.
        """
        if self.enable_dev_auth and self.environment != "development":
            raise ValueError(
                "REFUSING TO START: ENABLE_DEV_AUTH=true is only permitted "
                f"when ENVIRONMENT=development (got {self.environment!r}). "
                "This is the first of five dev-mode defense layers — see "
                ".planning/reviews/2026-04-11-platform-readiness-review.md §5.3."
            )
        return self

    @model_validator(mode="after")
    def _validate_environment_security_requirements(self) -> "Settings":
        """Fail closed on environment-specific email and cookie settings."""
        email_cfg = self.yaml.email

        if self.environment == "production" and email_cfg.backend == "console":
            raise ValueError(
                "REFUSING TO START: email.backend is 'console' while "
                "ENVIRONMENT=production. Configure SMTP delivery before "
                "starting production."
            )

        if (
            self.environment in {"staging", "production"}
            and not self.AUTH_COOKIE_SECURE
        ):
            raise ValueError(
                "REFUSING TO START: AUTH_COOKIE_SECURE must be true when "
                f"ENVIRONMENT={self.environment}."
            )

        return self

    @model_validator(mode="after")
    def _validate_redis_fallback_contract(self) -> "Settings":
        """Apply an explicit, fail-closed Redis fallback contract."""
        if self.ALLOW_REDIS_FALLBACK is None:
            self.ALLOW_REDIS_FALLBACK = self.environment == "development"

        if self.ALLOW_REDIS_FALLBACK and self.environment != "development":
            raise ValueError(
                "REFUSING TO START: ALLOW_REDIS_FALLBACK=true is only permitted "
                f"when ENVIRONMENT=development (got {self.environment!r})."
            )

        return self

    @model_validator(mode="after")
    def _validate_smtp_config(self) -> "Settings":
        """Fail fast if email backend is smtp but SMTP_HOST is missing."""
        email_cfg = self.yaml.email
        if email_cfg.backend == "smtp":
            if not self.SMTP_HOST or self.SMTP_HOST.strip() == "":
                raise ValueError(
                    "REFUSING TO START: email.backend is 'smtp' but SMTP_HOST "
                    "is empty. Set SMTP_HOST in .env or switch to "
                    "email.backend: 'console' in config.yaml."
                )
            if email_cfg.use_credentials:
                if not self.SMTP_USERNAME or not self.SMTP_PASSWORD:
                    raise ValueError(
                        "REFUSING TO START: email.backend is 'smtp' with "
                        "use_credentials: true, but SMTP_USERNAME or "
                        "SMTP_PASSWORD is empty. Set them in .env or set "
                        "email.use_credentials: false in config.yaml."
                    )
            # Gate TLS warning behind smtp backend — it is irrelevant (and
            # noisy) when backend is console (Copilot PR #235 review).
            if email_cfg.tls_mode == "none":
                logger.critical(
                    "EMAIL TLS IS DISABLED (email.tls_mode: 'none'). "
                    "Emails will be sent unencrypted. This is only safe "
                    "for trusted internal relays."
                )
        return self

    @property
    def yaml(self) -> YamlConfig:
        """Lazy-load YAML configuration."""
        if self._yaml_config is None:
            self._yaml_config = load_yaml_config()
        return self._yaml_config

    # === Convenience accessors for YAML config ===

    @property
    def pagination(self) -> PaginationConfig:
        """Access pagination configuration."""
        return self.yaml.pagination

    @property
    def rate_limiting(self) -> RateLimitingConfig:
        """Access rate limiting configuration."""
        return self.yaml.rate_limiting

    @property
    def external_apis(self) -> ExternalApisConfig:
        """Access external APIs configuration."""
        return self.yaml.external_apis

    @property
    def database(self) -> DatabaseConfig:
        """Access database configuration."""
        return self.yaml.database

    @property
    def http_cache(self) -> HttpCacheConfig:
        """Access HTTP cache configuration."""
        return self.yaml.http_cache

    @property
    def materialized_views(self) -> MaterializedViewsConfig:
        """Access materialized views configuration."""
        return self.yaml.materialized_views

    @property
    def hpo_terms(self) -> HPOTermsConfig:
        """Access HPO terms configuration."""
        return self.yaml.hpo_terms

    @property
    def security(self) -> SecurityConfig:
        """Access security configuration."""
        return self.yaml.security

    @property
    def email(self) -> EmailConfig:
        """Access email configuration."""
        return self.yaml.email

    # === Legacy compatibility properties ===
    # These provide backward compatibility with code using old config names

    @property
    def JWT_ALGORITHM(self) -> str:
        """Legacy: JWT algorithm."""
        return self.security.jwt_algorithm

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        """Legacy: Access token expiration."""
        return self.security.access_token_expire_minutes

    @property
    def REFRESH_TOKEN_EXPIRE_DAYS(self) -> int:
        """Legacy: Refresh token expiration."""
        return self.security.refresh_token_expire_days

    @property
    def PASSWORD_MIN_LENGTH(self) -> int:
        """Legacy: Minimum password length."""
        return self.security.password_min_length

    @property
    def MAX_LOGIN_ATTEMPTS(self) -> int:
        """Legacy: Maximum login attempts."""
        return self.security.max_login_attempts

    @property
    def ACCOUNT_LOCKOUT_MINUTES(self) -> int:
        """Legacy: Account lockout duration."""
        return self.security.account_lockout_minutes

    @property
    def VEP_API_BASE_URL(self) -> str:
        """Legacy: VEP API base URL."""
        return self.external_apis.vep.base_url

    @property
    def VEP_RATE_LIMIT_REQUESTS_PER_SECOND(self) -> int:
        """Legacy: VEP rate limit."""
        return self.rate_limiting.vep.requests_per_second

    @property
    def VEP_REQUEST_TIMEOUT_SECONDS(self) -> int:
        """Legacy: VEP request timeout."""
        return self.external_apis.vep.timeout_seconds

    @property
    def VEP_MAX_RETRIES(self) -> int:
        """Legacy: VEP max retries."""
        return self.external_apis.vep.max_retries

    @property
    def VEP_RETRY_BACKOFF_FACTOR(self) -> float:
        """Legacy: VEP retry backoff factor."""
        return self.external_apis.vep.retry_backoff_factor

    @property
    def VEP_CACHE_ENABLED(self) -> bool:
        """Legacy: VEP cache enabled."""
        return self.external_apis.vep.cache_enabled

    @property
    def VEP_CACHE_SIZE_LIMIT(self) -> int:
        """Legacy: VEP cache size limit."""
        return self.external_apis.vep.cache_size_limit


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    This function is cached to ensure only one Settings instance exists.
    Use this function in FastAPI dependencies for proper testing support.
    """
    return Settings()


# Global settings instance for direct import
settings = get_settings()

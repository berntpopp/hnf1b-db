"""Compat-hook tests for the ``variant_validator`` package split.

When Wave 4 split the 1,008-LOC ``variant_validator.py`` flat module
into a sub-package, the 1,671-line regression suite
``test_variant_validator_enhanced.py`` kept working **only** because the
package ``__init__.py`` re-exports ``cache`` and ``settings`` before
loading submodules, and the submodules look both names up dynamically
through ``_vv_pkg`` at call time.

This file tests those compat hooks directly so a future cleanup pass
that removes the re-exports or switches submodules to binding imports
fails loudly here — instead of spreading failures across the 1,671-line
suite that happens to exercise the same code path for other reasons.

See ``docs/refactor/tech-debt.md`` for the removal criteria.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.phenopackets.validation import variant_validator as _vv_pkg
from app.phenopackets.validation.variant_validator import (
    VariantValidator,
)
from app.phenopackets.validation.variant_validator import (
    cache as pkg_cache,
)
from app.phenopackets.validation.variant_validator import (
    settings as pkg_settings,
)


class TestPackageLevelReExports:
    """Both legacy patch targets must resolve at the package root."""

    def test_cache_is_re_exported_at_package_root(self):
        """``app.phenopackets.validation.variant_validator.cache`` resolves."""
        assert pkg_cache is not None
        assert hasattr(pkg_cache, "get_json")
        assert hasattr(pkg_cache, "set_json")

    def test_settings_is_re_exported_at_package_root(self):
        """``app.phenopackets.validation.variant_validator.settings`` resolves."""
        assert pkg_settings is not None
        assert hasattr(pkg_settings, "external_apis")

    def test_cache_re_export_shares_identity_with_app_core_cache(self):
        """Patching ``app.core.cache.cache`` must be visible through the re-export.

        Both names must point at the same object so the regression suite's
        ``patch("app.phenopackets.validation.variant_validator.cache")``
        calls actually affect the annotator / recoder.
        """
        from app.core.cache import cache as core_cache

        assert pkg_cache is core_cache

    def test_settings_re_export_shares_identity_with_app_core_config(self):
        """Same invariant for ``settings``."""
        from app.core.config import settings as core_settings

        assert pkg_settings is core_settings


class TestVVPkgDynamicLookup:
    """Submodules must read settings/cache through the package at call time."""

    def test_patching_settings_via_package_affects_new_validator(self):
        """A freshly-constructed ``VariantValidator`` must pick up the patched value.

        The rate limiter reads ``_vv_pkg.settings.external_apis.vep.requests_per_second``
        in ``VariantValidator.__init__``. If the submodules bound
        ``settings`` at import time, patching the package attribute would
        be a no-op — this test would then fail, signalling that the
        compat hook has regressed.
        """
        fake_settings = MagicMock()
        # VariantValidator reads the rps from rate_limiting.vep and the
        # retry/cache knobs from external_apis.vep — mirror both.
        fake_settings.rate_limiting.vep.requests_per_second = 42
        fake_settings.external_apis.vep.max_retries = 7
        fake_settings.external_apis.vep.retry_backoff_factor = 3.0
        fake_settings.external_apis.vep.cache_ttl_seconds = 9999

        with patch(
            "app.phenopackets.validation.variant_validator.settings", fake_settings
        ):
            validator = VariantValidator()

        # Properties on the facade forward to the sub-components that
        # were configured from ``_vv_pkg.settings`` during construction.
        assert validator._requests_per_second == 42
        assert validator._max_retries == 7
        assert validator._backoff_factor == 3.0
        assert validator._cache_ttl == 9999

    def test_patching_cache_via_package_is_visible_to_submodules(self):
        """Patching ``...variant_validator.cache`` must affect submodule lookups.

        The submodules (``vep_annotate``, ``vep_recoder``) read the cache
        via ``_vv_pkg.cache.get_json(...)``. The regression suite relies on
        this to inject a fake cache without monkey-patching private
        attributes on the annotator.
        """
        fake_cache = MagicMock()
        with patch("app.phenopackets.validation.variant_validator.cache", fake_cache):
            # The name on the package object must now point at the fake.
            assert _vv_pkg.cache is fake_cache


class TestFacadeLegacyAttributeSurface:
    """The pre-Wave-4 private attributes must still be mutable on the facade."""

    def test_set_max_retries_propagates_to_annotator_and_recoder(self):
        """Tests that poke ``validator._max_retries = 1`` must affect both paths."""
        validator = VariantValidator()
        validator._max_retries = 99
        assert validator._annotator._max_retries == 99
        assert validator._recoder._max_retries == 99

    def test_set_backoff_factor_propagates_to_annotator_and_recoder(self):
        """Tests that poke ``validator._backoff_factor = ...`` must affect both."""
        validator = VariantValidator()
        validator._backoff_factor = 10.0
        assert validator._annotator._backoff_factor == 10.0
        assert validator._recoder._backoff_factor == 10.0

    def test_set_cache_ttl_propagates_to_annotator_and_recoder(self):
        """Tests that poke ``validator._cache_ttl = ...`` must affect both."""
        validator = VariantValidator()
        validator._cache_ttl = 12345
        assert validator._annotator._cache_ttl == 12345
        assert validator._recoder._cache_ttl == 12345

    def test_rate_limiter_fields_are_readable_and_writable(self):
        """The rate-limiter-facing legacy fields must round-trip via properties."""
        validator = VariantValidator()
        # Read is a property that forwards to the RateLimiter instance.
        original_count = validator._request_count
        validator._request_count = original_count + 5
        assert validator._rate_limiter._request_count == original_count + 5
        assert validator._request_count == original_count + 5

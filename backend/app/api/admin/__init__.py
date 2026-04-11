"""Admin API sub-package.

Split from the old flat ``app/api/admin_endpoints.py`` during Wave 4.
The ``endpoints``/``schemas``/``queries``/``sync_service`` submodules
land in a follow-up commit; the first commit introduces only the
cache-backed ``task_state`` module so the new infrastructure can be
reviewed (and tested) independently of the router split.
"""

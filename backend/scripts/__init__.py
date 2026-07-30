"""Scripts package for administrative tasks.

This package contains standalone scripts for:
- Database administration (create_admin_user.py)
- Data synchronization (sync_*.py)
- Reference data import (import_*.py)
- Ontology reporting (ontology_preflight.py, refresh_ontology_snapshot.py)

``normalize_hpo_labels.py`` was deleted (see
docs/ontology-defect-report-2026-07-30.md §4.1): it rewrote curator labels
to match their stored identifier -- a sixth instance of the label-laundering
defect family, and the one that most directly defeated the importer fix in
``migration/phenopackets/hpo_mapper.py``. ``app.ontology.conformance.check_label``
plus ``scripts/ontology_preflight.py`` supersede it.
"""

"""JSONB path constants for phenopacket aggregation queries.

Extracted during Wave 4 from the monolithic
``aggregations/sql_fragments.py`` — these string constants are used
across every other submodule in the sub-package and need to sit at
the bottom of the import graph.
"""

# Base path to variationDescriptor within genomicInterpretation.
VD_BASE = "diagnosis,genomicInterpretations,0,variantInterpretation,variationDescriptor"

# Variation descriptor field paths (require interp alias in query).
# Note: triple braces ``{{{`` produce literal ``{`` + f-string substitution.
VD_ID = f"interp.value#>>'{{{VD_BASE},id}}'"
VD_EXTENSIONS = f"interp.value#>'{{{VD_BASE},extensions}}'"
VD_EXPRESSIONS = f"interp.value#>'{{{VD_BASE},expressions}}'"

# Subject age path (used in survival queries).
CURRENT_AGE_PATH = "p.phenopacket->'subject'->'timeAtLastEncounter'->>'iso8601duration'"

# Interpretation status path (used for P/LP filtering).
INTERP_STATUS_PATH = (
    "interp.value->'diagnosis'->'genomicInterpretations'->0->>'interpretationStatus'"
)

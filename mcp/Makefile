.PHONY: install lint typecheck test check contract contract-verify
install:
	uv sync --group dev
lint:
	uv run ruff check .
typecheck:
	uv run mypy src/
test:
	uv run pytest
check: lint typecheck test

# Regenerate the API contract package from the committed OpenAPI snapshot.
# Pinned datamodel-codegen + deterministic emitter; output is formatted so the
# contract-verify git-diff gate stays stable.
contract:
	uv run python scripts/gen_contract.py
	uvx --from 'datamodel-code-generator==0.40.0' datamodel-codegen \
	  --input contract/openapi.snapshot.json --input-file-type openapi \
	  --output-model-type pydantic_v2.BaseModel --target-python-version 3.11 \
	  --use-standard-collections --enum-field-as-literal all \
	  --use-annotated --disable-timestamp \
	  --output src/hnf1b_mcp/contract/_generated_models.py
	uv run ruff format src/hnf1b_mcp/contract/

# CI-only: fail if the committed contract artifacts are stale. Separate from
# `check` so local runs do not depend on git state.
contract-verify:
	$(MAKE) contract && git diff --exit-code -- contract/ src/hnf1b_mcp/contract/

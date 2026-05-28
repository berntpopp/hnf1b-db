.PHONY: install lint typecheck test check
install:
	uv sync --group dev
lint:
	uv run ruff check .
typecheck:
	uv run mypy src/
test:
	uv run pytest
check: lint typecheck test

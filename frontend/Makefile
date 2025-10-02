.PHONY: help install dev build preview lint format clean

help:  ## Show frontend commands
	@echo "Frontend Development Commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	npm install

dev:  ## Start development server (http://localhost:5173)
	npm run dev

build:  ## Build for production
	npm run build

preview:  ## Preview production build
	npm run preview

lint:  ## Lint and fix code
	npm run lint

lint-check:  ## Lint code (check only, no auto-fix)
	npm run lint:check

format:  ## Format code with Prettier
	npm run format

format-check:  ## Check code formatting (no auto-fix)
	npm run format:check

check:  ## Run all checks (lint + format)
	npm run lint:check
	npm run format:check

clean:  ## Remove node_modules and build artifacts
	rm -rf node_modules dist

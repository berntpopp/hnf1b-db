.PHONY: help install dev build preview test test-watch test-coverage test-ui lint lint-check format format-check check ci clean

help:  ## Show frontend commands
	@echo "Frontend Development Commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	npm install

dev:  ## Start development server (http://localhost:5173)
	npm run dev

build:  ## Build for production
	npm run build

preview:  ## Preview production build
	npm run preview

test:  ## Run tests once
	npm test

test-watch:  ## Run tests in watch mode
	npm run test:watch

test-coverage:  ## Run tests with coverage report
	npm run test:coverage

test-ui:  ## Run tests with interactive UI
	npm run test:ui

lint:  ## Lint and fix code
	npm run lint

lint-check:  ## Lint code (check only, no auto-fix)
	npm run lint:check

format:  ## Format code with Prettier
	npm run format

format-check:  ## Check code formatting (no auto-fix)
	npm run format:check

check:  ## Run all quality checks (test + lint + format)
	@echo "Running all quality checks..."
	@echo "📋 Step 1/3: Running tests..."
	npm test
	@echo "✅ Tests passed"
	@echo ""
	@echo "📋 Step 2/3: Checking linting..."
	npm run lint:check
	@echo "✅ Linting passed"
	@echo ""
	@echo "📋 Step 3/3: Checking formatting..."
	npm run format:check
	@echo "✅ Formatting passed"
	@echo ""
	@echo "🎉 All quality checks passed!"

ci: check  ## Run the frontend CI parity target
	@echo "📋 Step 4/6: Building production bundle..."
	npm run build
	@echo "✅ Build passed"
	@echo ""
	@echo "📋 Step 5/6: Verifying dev-auth strings are absent from dist/..."
	@if grep -rqE "dev/login-as|DevQuickLogin|dev-admin|dev-curator|dev-viewer" dist/ --include='*.js' --include='*.css' 2>/dev/null; then \
		echo "dev-auth strings leaked into the production bundle"; \
		grep -rnE "dev/login-as|DevQuickLogin|dev-admin|dev-curator|dev-viewer" dist/ --include='*.js' --include='*.css' || true; \
		exit 1; \
	fi
	@echo "✅ Dev-auth strings absent from production bundle"
	@echo ""
	@echo "📋 Step 6/6: Verifying production compose guards..."
	@if grep -Eq "^[[:space:]]*(-[[:space:]]*)?ENABLE_DEV_AUTH[[:space:]]*[:=][[:space:]]*['\"]?(true|True|TRUE|yes|Yes|YES|on|On|ON|1)['\"]?[[:space:]]*$$" ../docker/docker-compose.npm.yml; then \
		echo "ENABLE_DEV_AUTH must not be truthy in docker/docker-compose.npm.yml"; \
		grep -nE "^[[:space:]]*(-[[:space:]]*)?ENABLE_DEV_AUTH" ../docker/docker-compose.npm.yml || true; \
		exit 1; \
	fi
	@if ! grep -Eq "^[[:space:]]*(-[[:space:]]*)?ENVIRONMENT[[:space:]]*[:=][[:space:]]*production[[:space:]]*$$" ../docker/docker-compose.npm.yml; then \
		echo "docker/docker-compose.npm.yml must set ENVIRONMENT=production explicitly"; \
		exit 1; \
	fi
	@echo "✅ Production compose guards passed"
	@echo ""
	@echo "🎉 Frontend CI parity checks passed!"

clean:  ## Remove node_modules and build artifacts
	rm -rf node_modules dist

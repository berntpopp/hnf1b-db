# HNF1B Database - Frontend

Vue 3 application for the HNF1B clinical genetics database. Part of the HNF1B Database monorepo.

## Features

- Browse and search GA4GH Phenopackets v2 data
- Interactive D3.js data visualizations
- Clinical feature aggregations and statistics
- HPO term autocomplete search
- Responsive Material Design interface
- JWT authentication with in-memory access tokens and cookie-backed refresh

## Prerequisites

- Node.js (v20 or higher)
- npm or yarn
- Backend API running (see root README.md)

## Quick Start

```bash
# From the frontend directory
make install    # Install dependencies
make dev        # Start development server
```

The application will be available at `http://localhost:5173`

**Note:** For full-stack setup, see the [root README.md](../README.md) in the parent directory.

## Development Commands

```bash
make help         # Show all available commands
make install      # Install dependencies
make dev          # Start development server
make build        # Build for production
make preview      # Preview production build
make lint         # Lint and fix code
make format       # Format code with Prettier
make check        # Run all checks (lint + format)
make clean        # Remove node_modules and build artifacts
```

Or use npm directly:

```bash
npm run dev       # Start development server
npm run build     # Build for production
npm run lint      # Lint and fix code
npm run format    # Format code with Prettier
```

## Project Structure

```
src/
├── api/          # API service layer
├── assets/       # Static assets and mixins
├── components/   # Reusable Vue components
│   ├── analyses/ # Data visualization components
│   └── tables/   # Table components
├── router/       # Vue Router configuration
├── utils/        # Utility functions
└── views/        # Page-level components
```

## Technology Stack

- **Vue 3** - Progressive JavaScript framework with Composition API
- **Vite 7** - Next generation frontend tooling
- **Vitest 4** - Unit/component test runner (with @vue/test-utils)
- **Playwright** - End-to-end test runner (`tests/e2e/`)
- **Vuetify 4** - Material Design component framework
- **Vue Router 5** - Official router for Vue.js
- **Pinia** - State management (stores in `src/stores/`)
- **Axios** - HTTP client for API requests with in-memory access tokens, cookie-backed refresh, and CSRF support
- **D3.js** - Data visualization library

## API Configuration

### Environment Variables

Create a `.env` file in the frontend directory (copy from `.env.example`):

```bash
cp .env.example .env
```

Configure the backend API URL (v2 Phenopackets API):

```env
# Development
VITE_API_URL=http://localhost:8000/api/v2

# Production
# VITE_API_URL=https://api.hnf1b.example.com/api/v2
```

### API Structure

The application uses the **GA4GH Phenopackets v2** API format:

- **Base URL**: `http://localhost:8000/api/v2`
- **Authentication**: Short-lived access token in frontend memory, rotating refresh token in an `HttpOnly` cookie, and `X-CSRF-Token` header support for cookie-auth flows (see [ADR 0002](../docs/adr/0002-cookie-refresh-and-memory-access-token.md))
- **Pagination**: JSON:API v1.1 — `page[number]`/`page[size]` (offset) or `page[after]` (cursor); `sort=-created_at` style sort keys
- **Data Format**: JSON:API v1.1 responses (data/meta/links envelope)

**Key Endpoints:**

- `GET /phenopackets/` - List phenopackets with filters
- `GET /phenopackets/{id}` - Get single phenopacket
- `POST /phenopackets/search` - Advanced search
- `GET /phenopackets/aggregate/*` - Aggregations and statistics
- `GET /clinical/*` - Clinical feature queries
- `POST /auth/login` - JWT authentication

See `src/api/index.js` for complete API client documentation.

## License

MIT License - Copyright (c) 2025 Bernt Popp

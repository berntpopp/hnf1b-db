# HNF1B Database - Frontend

Vue 3 application for the HNF1B clinical genetics database. Part of the HNF1B Database monorepo.

## Features

- Browse and search individuals, variants, and publications
- Interactive data visualizations and charts
- Aggregated statistics dashboard
- Responsive Material Design interface

## Prerequisites

- Node.js (v16 or higher)
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

- **Vue 3** - Progressive JavaScript framework
- **Vite** - Next generation frontend tooling
- **Vuetify 3** - Material Design component framework
- **Vue Router 4** - Official router for Vue.js
- **Axios** - HTTP client for API requests
- **Chart.js** - Data visualization library

## API Configuration

### Environment Variables

Create a `.env` file in the frontend directory (copy from `.env.example`):

```bash
cp .env.example .env
```

Configure the backend API URL:

```env
VITE_API_URL=http://localhost:8000
```

The Vite proxy (configured in `vite.config.js`) forwards `/api` requests to the backend.

## License

MIT License - Copyright (c) 2025 Bernt Popp
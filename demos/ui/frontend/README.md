# AgentConnect Frontend

## Overview
The AgentConnect frontend is a modern React application built with TypeScript, Vite, and Tailwind CSS. It provides a real-time chat interface with AI agents through WebSocket communication.

## Tech Stack
- React 18.3.1
- TypeScript 5.6.3
- Vite 6.0.11
- Tailwind CSS 4.0.3
- React Router DOM 7.1.5
- React Query (@tanstack/react-query) 5.66.0
- Zustand 5.0.3

## Project Structure
```
frontend/
├── src/
│   ├── components/     # Reusable UI components
│   ├── pages/         # Route pages
│   ├── services/      # API and WebSocket services
│   ├── hooks/         # Custom React hooks
│   ├── utils/         # Utility functions
│   ├── types/         # TypeScript type definitions
│   ├── config/        # Configuration files
│   ├── store/         # State management (Zustand)
│   ├── styles/        # Global styles
│   ├── layouts/       # Layout components
│   └── assets/        # Static assets
├── public/           # Public assets
└── dist/            # Production build output
```

## Getting Started

### Prerequisites
- Node.js (Latest LTS version recommended)
- npm (comes with Node.js)

### Installation
```bash
# Install dependencies
npm install
```

### Development
```bash
# Start development server
npm run dev
```
The development server will start at http://localhost:5173

### Production Build
```bash
# Build for production
npm run build
```
The production build will be available in the `dist` directory.

### Preview Production Build
```bash
# Preview production build
npm run preview
```
The preview server will start at http://localhost:4173

## Development Features

### Path Aliases
The project uses TypeScript path aliases for cleaner imports:
- @/* -> src/*
- @components/* -> src/components/*
- @pages/* -> src/pages/*
- @hooks/* -> src/hooks/*
- @utils/* -> src/utils/*
- @types/* -> src/types/*
- @services/* -> src/services/*
- @store/* -> src/store/*
- @styles/* -> src/styles/*
- @assets/* -> src/assets/*
- @layouts/* -> src/layouts/*

### API Proxy Configuration
Development server includes proxy settings for API and WebSocket connections:
- API endpoints: http://127.0.0.1:8000/api
- WebSocket: ws://127.0.0.1:8000/ws

### Build Optimization
- Code splitting with manual chunks for vendor libraries
- Asset optimization and management
- Source maps in development
- Bundle size monitoring

### Styling
- Tailwind CSS with dark mode support
- Custom color scheme and animations
- Typography plugin for markdown content
- Forms plugin for form styling
- Aspect ratio utilities

## Known Issues
- There is a known moderate severity vulnerability in esbuild (dependency of Vite) that affects development server only. This doesn't impact production builds. Reference: GHSA-67mh-4wv8-2f99

## Scripts
- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint
- `npm run test` - Run tests
- `npm run test:watch` - Run tests in watch mode

## Dependencies
For a complete list of dependencies and their versions, refer to package.json


# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react/README.md) uses [Babel](https://babeljs.io/) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type aware lint rules:

- Configure the top-level `parserOptions` property like this:

```js
export default tseslint.config({
  languageOptions: {
    // other options...
    parserOptions: {
      project: ['./tsconfig.node.json', './tsconfig.app.json'],
      tsconfigRootDir: import.meta.dirname,
    },
  },
})
```

- Replace `tseslint.configs.recommended` to `tseslint.configs.recommendedTypeChecked` or `tseslint.configs.strictTypeChecked`
- Optionally add `...tseslint.configs.stylisticTypeChecked`
- Install [eslint-plugin-react](https://github.com/jsx-eslint/eslint-plugin-react) and update the config:

```js
// eslint.config.js
import react from 'eslint-plugin-react'

export default tseslint.config({
  // Set the react version
  settings: { react: { version: '18.3' } },
  plugins: {
    // Add the react plugin
    react,
  },
  rules: {
    // other rules...
    // Enable its recommended rules
    ...react.configs.recommended.rules,
    ...react.configs['jsx-runtime'].rules,
  },
})
```

# AgentConnect QuickStart Guide

## Prerequisites
- Python 3.11+
- Poetry (Python package manager)
- Node.js 18+ and npm
- Redis server running locally (required for session management)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/AKKI0511/AgentConnect.git
cd AgentConnect
```

2. Install Poetry:
Visit [Poetry's official installation guide](https://python-poetry.org/docs/#installation) and follow the instructions for your operating system.

3. Install backend dependencies:
```bash
# For development (includes all dependencies)
poetry install --with demo,dev --no-root

# For production (minimal installation)
poetry install --without dev --no-root

# For demo API server only
poetry install --with demo --without dev --no-root
```

4. Install frontend dependencies:
```bash
cd demos/ui/frontend
npm install
```

5. Set up environment:
```bash
# Copy environment file
copy example.env .env  # Windows
cp example.env .env    # Linux/Mac
```

Configure your environment in `.env`:

```ini
# Required: Set your default provider and its API key
DEFAULT_PROVIDER=groq  # Choose: groq, anthropic, openai, or google
GROQ_API_KEY=your_groq_api_key

# Optional: Other provider API keys
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
GOOGLE_API_KEY=your_google_api_key

# Optional: Customize API settings
API_HOST=127.0.0.1
API_PORT=8000
DEBUG=False

# Optional: Redis settings (if using custom configuration)
REDIS_HOST=localhost
REDIS_PORT=6379
```

See `example.env` in the project root for all available configuration options and their default values.

## Running the Application

### Backend API Server

Start the API server:
```bash
# Run with default settings (localhost:8000)
poetry run python demos/run_demo.py --backend-only

# Run with custom host and port
poetry run python demos/run_demo.py --backend-only --host 0.0.0.0 --port 8080
```

The API server will create necessary directories (like `logs`) automatically.

Once started, you can access:
- API Endpoints: `http://localhost:8000`
- Interactive API Documentation: `http://localhost:8000/docs`
- Alternative API Documentation: `http://localhost:8000/redoc`

### Frontend Application

The frontend is a modern React application with TypeScript and Tailwind CSS:

```bash
# Navigate to frontend directory
cd demos/ui/frontend

# Install dependencies (if not done already)
npm install

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:5173` and will automatically connect to the backend API.

### Production Deployment

For production deployment:

```bash
# Build frontend
cd demos/ui/frontend
npm run build

# Preview production build
npm run preview
```

The production build will be available in the `dist` directory and can be served using the preview server at `http://localhost:4173`.

## Known Issues

1. Frontend Development Server:
   - There is a known moderate severity vulnerability in esbuild (Vite dependency)
   - This only affects the development server, not production builds
   - Reference: GHSA-67mh-4wv8-2f99

2. If you get a "Port in use" error:
   - Make sure no other application is using ports 8000 (backend) or 5173 (frontend)
   - Try different ports using `--port` argument for backend
   - Use `--port` flag with `vite` for frontend

3. If you get Redis connection errors:
   - Make sure Redis server is running locally
   - Default Redis connection: localhost:6379

4. If you get import errors:
   - Make sure you're in the project root directory
   - Try reinstalling dependencies: `poetry install --no-root`

5. If you get API key errors:
   - Verify your API keys in `.env`
   - At least one provider's API key is required (default: GROQ)

## Documentation

For detailed information, refer to:
- [Main Documentation](../README.md)
- [API Documentation](api/README.md)
- [Frontend Documentation](ui/frontend/README.md) 
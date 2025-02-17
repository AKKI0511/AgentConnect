# AgentConnect: Decentralized Agent Framework

[![CI](https://github.com/AKKI0511/AgentConnect/actions/workflows/main.yml/badge.svg)](https://github.com/AKKI0511/AgentConnect/actions/workflows/main.yml)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📖 Overview

AgentConnect is a scalable framework for human-agent and agent-agent interactions, providing a robust foundation for building AI-powered applications. The framework enables real-time, autonomous agent interactions while maintaining security and extensibility.

### Key Features

- **🤖 Autonomous Agents**: Independent communication with async processing loops
- **⚡ Real-time Communication**: WebSocket-based updates for seamless interactions
- **🔌 Multi-Provider Support**: OpenAI, Anthropic, Groq, and Google AI integration
- **🔒 Security**: DID-based identity and cryptographic message verification
- **🎯 Capability System**: Dynamic discovery and interaction
- **🔧 Extensible Design**: Modular architecture with automatic session management

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- Poetry (Python package manager)
- Redis server
- Node.js and npm (for frontend)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/AKKI0511/AgentConnect.git
cd AgentConnect
```

2. Install Poetry:
Visit [Poetry's official installation guide](https://python-poetry.org/docs/#installation) and follow the instructions for your operating system.

3. Install dependencies:
```bash
# Install all dependencies (recommended)
poetry install --with demo,dev --no-root

# For production only (without dev tools)
poetry install --without dev --no-root
```

4. Set up environment:
```bash
# Copy environment file
copy example.env .env  # Windows
cp example.env .env    # Linux/Mac

# Edit .env and configure at least one provider API key
# The default provider is 'groq', but you can change it:
DEFAULT_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key

# Optional: Configure other providers
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
GOOGLE_API_KEY=your_google_api_key

# Optional: Configure other settings (see example.env for all options)
API_PORT=8000
DEBUG=True
```

> **Note**: Only the API key matching your `DEFAULT_PROVIDER` is required. Other settings have sensible defaults.

## 🎮 Usage

### Quick Demo

Run the backend API server:
```bash
poetry run python demos/run_demo.py --backend-only
```

The API will be available at:
- API Endpoints: `http://localhost:8000`
- Interactive API Documentation: `http://localhost:8000/docs`
- Alternative API Documentation: `http://localhost:8000/redoc`

### Example Applications

1. **Interactive Chat Demo**
```bash
poetry run python example_usage.py
```
- Real-time chat with AI agents
- Multiple provider/model selection
- Message history tracking

2. **Multi-Agent Analysis Demo**
```bash
poetry run python example_multi_agent.py
```
- Autonomous agent interaction
- Real-time conversation visualization
- Structured data analysis

## 🛠️ Development

### Development Commands

#### Using Poetry (Local Development)
```bash
# Install dependencies
poetry install

# Run linting
poetry run pylint src/ tests/ demos/

# Format code
poetry run black .

# Run tests
poetry run pytest

# Run demo
poetry run python demos/run_demo.py
```

#### Using Make (CI/CD)
```bash
make install   # Install dependencies
make lint      # Run linting
make format    # Format code
make test      # Run tests
make all       # Run all checks
```

### Project Structure
```
AgentConnect/
├── src/                    # Core source code
│   ├── agents/            # Agent implementations
│   ├── communication/     # Communication protocols
│   ├── core/              # Core framework components
|   ├── prompts/           # Prompt templates
|   ├── providers/         # AI provider integrations
|   └── utils/             # Utilities
├── demos/                 # Demo applications
│   ├── api/              # FastAPI backend implementation
│   ├── ui/               # Frontend UI implementation
│   └── utils/            # Demo utilities
├── tests/                # Test suite
├── example_usage.py      # Human-Agent demo
└── example_multi_agent.py # Agent-Agent demo
```

> **Note**: Frontend UI is currently under development. The backend API is fully functional and can be tested through the Swagger UI at `/docs`.

## 🔍 Architecture

### Core Components

1. **Communication Hub**
   - Central message routing
   - Agent registration and discovery
   - Protocol enforcement
   - Message history tracking

2. **Agent System**
   - Identity management (DID-based)
   - Capability declaration
   - Message signing/verification
   - Autonomous processing

3. **Provider Integration**
   - OpenAI (GPT, o1)
   - Anthropic (Claude)
   - Groq (Mixtral, LLaMA)
   - Google (Gemini)

## 📚 Documentation

- [Quick Start Guide](demos/QUICKSTART.md)
- [API Documentation](demos/api/README.md)
- [Frontend Documentation](demos/ui/frontend/README.md)

## Roadmap

- [x] MVP with basic agent-to-agent and human-to-agent interactions
- [ ] Secure data exchange between agents
- [ ] Decentralized payment integration
- [ ] Additional AI providers and communication protocols
- [ ] Advanced memory systems (Redis, PostgreSQL)

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Thanks to all contributors
- Built with [FastAPI](https://fastapi.tiangolo.com/), [LangChain](https://www.langchain.com/), and [React](https://reactjs.org/)
- Inspired by the need for secure autonomous multi-agent communication

## 📞 Support

- Create an [Issue](https://github.com/AKKI0511/AgentConnect/issues)
- Email: akkijoshi0511@gmail.com

# AgentConnect: Decentralized Agent Framework

<div align="center">

[![CI](https://github.com/AKKI0511/AgentConnect/actions/workflows/main.yml/badge.svg)](https://github.com/AKKI0511/AgentConnect/actions/workflows/main.yml)
[![Docs](https://github.com/AKKI0511/AgentConnect/actions/workflows/docs.yml/badge.svg)](https://github.com/AKKI0511/AgentConnect/actions/workflows/docs.yml)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://akki0511.github.io/AgentConnect/)
[![codecov](https://codecov.io/gh/AKKI0511/AgentConnect/branch/main/graph/badge.svg)](https://codecov.io/gh/AKKI0511/AgentConnect)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

<img src="https://raw.githubusercontent.com/AKKI0511/AgentConnect/main/docs/source/_static/logo.png" alt="AgentConnect Logo" width="200"/>

*A scalable framework for building autonomous AI agent systems*

[Installation](#-installation) •
[Documentation](https://akki0511.github.io/AgentConnect/) •
[Examples](examples/README.md) •
[Contributing](CONTRIBUTING.md)

</div>

## 📖 Overview

AgentConnect is a powerful framework for building AI agent systems that can communicate and collaborate autonomously. It provides the infrastructure for human-agent and agent-agent interactions, enabling developers to create sophisticated AI applications with minimal effort.

### Why AgentConnect?

- **Autonomous Operation**: Agents run independently with their own processing loops
- **Multi-Provider Support**: Works with OpenAI, Anthropic, Groq, and Google AI
- **Secure Communication**: DID-based identity and cryptographic verification
- **Extensible Architecture**: Modular design for easy customization
- **Comprehensive Monitoring**: Built-in tracing and debugging with LangSmith

## ✨ Key Features

<table>
  <tr>
    <td width="33%">
      <h3>🤖 Autonomous Agents</h3>
      <ul>
        <li>Independent processing loops</li>
        <li>Self-directed decision making</li>
        <li>Capability-based discovery</li>
      </ul>
    </td>
    <td width="33%">
      <h3>⚡ Real-time Communication</h3>
      <ul>
        <li>Asynchronous message delivery</li>
        <li>WebSocket-based API</li>
        <li>Structured conversation handling</li>
      </ul>
    </td>
    <td width="33%">
      <h3>🔌 Multi-Provider Support</h3>
      <ul>
        <li>OpenAI</li>
        <li>Anthropic</li>
        <li>Groq</li>
        <li>Google</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td>
      <h3>🔒 Security</h3>
      <ul>
        <li>DID-based identity</li>
        <li>Cryptographic verification</li>
        <li>Rate limiting and cooldown</li>
      </ul>
    </td>
    <td>
      <h3>🔍 Advanced Matching</h3>
      <ul>
        <li>Semantic capability search</li>
        <li>Embedding-based matching</li>
        <li>Dynamic agent discovery</li>
      </ul>
    </td>
    <td>
      <h3>📊 Monitoring</h3>
      <ul>
        <li>LangSmith integration</li>
        <li>Workflow tracing</li>
        <li>Performance analytics</li>
      </ul>
    </td>
  </tr>
</table>

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- Poetry (Python package manager)
- Redis server
- Node.js 18+ and npm (for frontend)

### 📥 Installation

1. **Clone the repository**

```bash
git clone https://github.com/AKKI0511/AgentConnect.git
cd AgentConnect
```

2. **Install Poetry** (if not already installed)

Visit [Poetry's installation guide](https://python-poetry.org/docs/#installation) for instructions.

3. **Install dependencies**

```bash
# Install all dependencies (recommended)
poetry install --with demo,dev

# For production only
poetry install --without dev

# Install directly from PyPI (coming soon)
# pip install agentconnect
```

4. **Set up environment**

```bash
# Copy environment template
copy example.env .env  # Windows
cp example.env .env    # Linux/Mac

# Verify your environment is correctly configured
agentconnect --check-env
```

5. **Configure API keys**

Edit the `.env` file to add at least one provider API key:

```
DEFAULT_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key
```

For monitoring and additional features, you can configure optional settings:

```
# LangSmith for monitoring (recommended)
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=AgentConnect

# Additional providers
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
GOOGLE_API_KEY=your_google_api_key
```

See `example.env` for all available configuration options.

## 🎮 Usage

### Command Line Interface (CLI)

AgentConnect includes a powerful CLI for running examples, demos, and performing system checks:

```bash
# Show version information
agentconnect --version

# Check environment configuration
agentconnect --check-env

# Run a specific example
agentconnect --example chat

# Run the demo application
agentconnect --demo

# Enable verbose logging
agentconnect --example multi --verbose
```

For more information about available commands:

```bash
agentconnect --help
```

### Running the Demo Application

1. **Start the backend server**

```bash
agentconnect --demo --backend-only
# or
poetry run python demos/run_demo.py --backend-only
```

2. **Start the frontend** (in a separate terminal)

```bash
cd demos/ui/frontend
npm install
npm run dev
```

3. **Access the application**

- Frontend UI: http://localhost:5173
- API Documentation: http://localhost:8000/docs

### Running Examples

AgentConnect includes several example applications to help you get started:

```bash
# Interactive menu of examples
agentconnect --example chat

# Run a specific example with verbose logging
agentconnect --example multi-agent --verbose
```

Available examples:
- **Chat**: Interactive conversation with an AI agent
- **Multi-Agent**: Autonomous collaboration between specialized agents
- **Research Assistant**: Collaborative research workflow
- **Data Analysis**: Specialized data processing and visualization

See the [Examples README](examples/README.md) for detailed descriptions.

### Importing AgentConnect

With the production-ready package structure, you can easily import AgentConnect components in your code:

```python
# Import the main components
from agentconnect import AIAgent
from agentconnect.core.types import Capability, ModelProvider, ModelName, AgentIdentity

# Create an AI agent
agent = AIAgent(
    agent_id="assistant",
    name="Assistant",
    provider_type=ModelProvider.OPENAI,
    model_name=ModelName.GPT4,
    api_key="your-api-key",
    identity=AgentIdentity(name="Assistant", role="assistant"),
    capabilities=[Capability(name="general", description="General assistance")]
)
```

## 🏗️ Architecture

AgentConnect is built around three core components:

### 1. Communication Hub

The central nervous system of AgentConnect, handling:
- Message routing between agents
- Agent registration and discovery
- Protocol enforcement
- Session management
- Asynchronous delivery

### 2. Agent System

The intelligent actors in the system, featuring:
- Identity management (DID-based)
- Capability declaration and discovery
- Message signing/verification
- Autonomous processing loops
- LangGraph-based workflows

### 3. Provider Integration

Flexible AI model integration with:
- Unified interface for multiple providers
- Automatic fallback mechanisms
- Streaming response support
- Token usage tracking
- Rate limiting

## 📊 Monitoring with LangSmith

AgentConnect integrates with LangSmith for comprehensive monitoring:

1. **Set up LangSmith**
   - Create an account at [LangSmith](https://smith.langchain.com/)
   - Add your API key to `.env`:
     ```
     LANGSMITH_TRACING=true
     LANGSMITH_API_KEY=your_langsmith_api_key
     LANGSMITH_PROJECT=AgentConnect
     ```

2. **Monitor agent workflows**
   - View detailed traces of agent interactions
   - Debug complex reasoning chains
   - Analyze token usage and performance

## 🛠️ Development

### Git Hooks with pre-commit

We use [pre-commit](https://pre-commit.com/) to manage our git hooks, which automatically check code quality before each commit:

```bash
# Install pre-commit hooks (do this once after cloning)
poetry run pre-commit install
# or
make install-hooks

# Run all hooks manually on all files
poetry run pre-commit run --all-files
# or
make hooks
```

The pre-commit hooks will:
- Format code with Black
- Sort imports with isort
- Check for common issues with flake8
- Ensure documentation is up-to-date

> **Note**: The `demos/` directory is excluded from pre-commit checks as it contains standalone demo applications that follow different coding standards.

### Development Commands

```bash
# Install dependencies
poetry install --with dev,demo

# Install git hooks
poetry run pre-commit install
# or
make install-hooks

# Format code
poetry run black .
# or
make format

# Run linting
poetry run flake8
# or
make lint

# Run tests
poetry run pytest
# or
make test

# Run all checks (format, lint, test, hooks)
make all
```

### Using Make

```bash
make format    # Format code with black
make lint      # Run linting with flake8
make test      # Run tests
make hooks     # Run pre-commit hooks on all files
make all       # Run all checks
```

## 📚 Documentation

- [Online Documentation](https://akki0511.github.io/AgentConnect/)
- [Quick Start Guide](demos/QUICKSTART.md)
- [API Reference](demos/api/README.md)
- [Architecture Overview](docs/DEVELOPER_GUIDELINES.md)
- [Development Guidelines](docs/DEVELOPER_GUIDELINES.md)
- [Module Documentation](docs/modules.md)

## 📋 Project Structure

```
AgentConnect/
├── agentconnect/           # Core framework
│   ├── __init__.py        # Package initialization with public API
│   ├── cli.py             # Command-line interface
│   ├── agents/            # Agent implementations
│   ├── communication/     # Communication protocols
│   ├── core/              # Core components
│   ├── prompts/           # Prompt templates
│   ├── providers/         # AI provider integrations
│   └── utils/             # Utilities
├── demos/                 # Demo applications
│   ├── api/              # FastAPI backend
│   └── ui/               # React frontend
├── examples/              # Example applications
├── docs/                  # Documentation
└── tests/                 # Test suite
```

## 🗺️ Roadmap

- [x] MVP with basic agent-to-agent interactions
- [x] Autonomous communication between agents
- [ ] Secure data exchange between agents
- [ ] Decentralized payment integration
- [ ] Additional AI providers and protocols
- [ ] Advanced memory systems (Redis, PostgreSQL)

## 🤝 Contributing

We welcome contributions to AgentConnect! Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## 📄 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

## 📝 Changelog

See the [Changelog](CHANGELOG.md) for a detailed history of changes to the project.

## 📜 Code of Conduct

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) to understand the expectations for participation in our community.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/), [LangChain](https://www.langchain.com/), and [React](https://reactjs.org/)
- Inspired by the need for secure autonomous multi-agent communication
- Thanks to all contributors who have helped shape this project

## 📞 Support

- Create an [Issue](https://github.com/AKKI0511/AgentConnect/issues)
- Email: akkijoshi0511@gmail.com

---

<div align="center">
  <sub>Built with ❤️ by the AgentConnect team</sub>
</div>

## Examples

The `examples/` directory contains example applications that demonstrate the capabilities of AgentConnect:

- **Agent Examples**: Demonstrates how to create and use different types of agents
- **Communication Examples**: Shows how agents communicate with each other
- **Multi-Agent Examples**: Examples of multi-agent systems and collaborative workflows

To run the examples:

```bash
# Using the CLI (recommended)
agentconnect --example chat

# Directly running the example script
python examples/agents/basic_agent_usage.py
```

See the [Examples Documentation](https://akki0511.github.io/AgentConnect/examples/) for more details.

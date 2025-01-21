# AgentConnect: Decentralized Agent Framework

[![CI](https://github.com/AKKI0511/AgentConnect/actions/workflows/main.yml/badge.svg)](https://github.com/AKKI0511/AgentConnect/actions/workflows/main.yml)

## Overview
AgentConnect is a scalable skeleton for human-agent and agent-agent interactions with future extensibility for payments, data exchange, and decentralized identities.

## Features

- **Autonomous Agent Interactions**: Agents can communicate, negotiate, and exchange information independently
- **Secure Identity System**: Built-in DID (Decentralized Identifier) based identity verification
- **Multi-Provider Support**: Works with OpenAI, Anthropic, Groq, and Google AI models
- **Flexible Communication**: Supports both agent-to-agent and human-to-agent interactions
- **Message Verification**: Cryptographic message signing and verification
- **Capability Discovery**: Agents can discover and interact based on capabilities
- **Extensible Architecture**: Easily add new AI providers, communication protocols, and memory systems

## Setup and Installation

### 1. Clone the Repository

```bash
git clone https://github.com/AKKI0511/AgentConnect.git
cd AgentConnect
```

### 2. Create and Activate Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies using Make

```bash
# Install all required packages
make install
```

### 4. Configuration

Copy the `example.env` file to `.env`:

```bash
cp example.env .env
```

Edit the `.env` file with your API keys:
```plaintext
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
GROQ_API_KEY=your_groq_api_key
GOOGLE_API_KEY=your_google_api_key
```

## Development Commands

The project includes a Makefile with the following commands:

```bash
# Install dependencies
make install

# Run code linting
make lint

# Format code using black
make format

# Run tests
make test

# Run all commands (install, lint, format, test)
make all
```

## Usage Examples

### Agent-to-Agent Interaction

Run the e-commerce analysis demo where two AI agents collaborate:

```bash
python example_multi_agent.py
```

### Human-to-Agent Interaction

Start an interactive session with an AI agent:

```bash
python example_usage.py
```

## Core Components

### 1. Communication Hub
- Central message routing
- Agent registration and discovery
- Protocol enforcement
- Message history tracking

### 2. Agent System
- Identity management (DID-based)
- Capability declaration
- Message signing/verification
- Autonomous processing

### 3. Provider Integration
Supported AI providers:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude 3)
- Groq (Mixtral, LLaMA)
- Google (Gemini)

## Project Structure

```
ai_agent_system/
├── README.md
├── requirements.txt
├── example_multi_agent.py  # Agent-Agent Uage Example
├── example_usage.py        # Human-Agent Usage example
├── setup.py
├── src/
│   ├── __init__.py
│   ├── utils/
│   │   ├── logging_config.py # Logging configuration
│   │   └── interaction_control.py # Token management
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py          # Base agent classes
│   │   ├── message.py        # Message definitions
│   │   ├── registry.py        # Central registry for agents
│   │   └── types.py          # Common types and enums
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── human_agent.py    # Human agent implementation
│   │   └── ai_agent.py       # AI agent implementation
│   ├── communication/
│   │   ├── __init__.py
│   │   ├── hub.py           # Communication hub
│   │   └── protocols/     # Communication protocols
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── chain_factory.py # Conversation chain creation
│   │   ├── memory_manager.py # Memory management
│   │   └── templates/       # Prompt templates
│   └── providers/
│       ├── __init__.py
│       ├── base_provider.py # Base provider class
│       ├── openai_provider.py # OpenAI provider
│       ├── anthropic_provider.py # Anthropic provider
│       ├── groq_provider.py # Groq provider
│       └── google_provider.py # Google provider
└── tests/
```

## Security Features

- DID-based identity verification
- Message signing and validation
- Protocol version checking
- Secure API key handling

## Roadmap

- [x] MVP with basic agent-to-agent and human-to-agent interactions
- [ ] Secure data exchange between agents
- [ ] Decentralized payment integration
- [ ] Additional AI providers and communication protocols
- [ ] Advanced memory systems (Redis, PostgreSQL)

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

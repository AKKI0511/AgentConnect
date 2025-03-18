# Installation

## Prerequisites

- Python 3.11 or higher
- Poetry (Python package manager)
- Redis server
- Node.js 18+ and npm (for frontend)

## Installing AgentConnect

Currently, AgentConnect is available from source only. Direct installation via pip will be available soon.

## Development Installation

For development, you can install AgentConnect from source:
```bash
git clone https://github.com/AKKI0511/AgentConnect.git
cd AgentConnect
```

### Using Poetry (Recommended)

AgentConnect uses Poetry for dependency management:

```bash
# Install Poetry (if not already installed)
# Visit https://python-poetry.org/docs/#installation for instructions

# Install all dependencies (recommended)
poetry install --with demo,dev

# For production only
poetry install --without dev
```

### Environment Setup

```bash
# Copy environment template
copy example.env .env  # Windows
cp example.env .env    # Linux/Mac
```

Configure API keys in the `.env` file:

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

## Dependencies

AgentConnect requires Python 3.11 or later and depends on the following packages:

* langchain
* openai
* anthropic
* google-generativeai
* groq
* cryptography
* fastapi (for API)
* redis (for distributed communication)

These dependencies will be automatically installed when you install AgentConnect using pip or Poetry.


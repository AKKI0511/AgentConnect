[![CI](https://github.com/AKKI0511/AgentConnect/actions/workflows/main.yml/badge.svg)](https://github.com/AKKI0511/AgentConnect/actions/workflows/main.yml)
# AgentConnect

A scalable skeleton for human-agent and agent-agent interactions with future extensibility for payments, data exchange, and decentralized identities.

## Setup and Installation

Follow the steps below to clone the repository and set up the environment:

### 1. Clone the Repository

Start by cloning the project repository to your local machine:

```bash
git clone https://github.com/AKKI0511/AgentConnect.git
cd AgentConnect
```

### 2. Create a Virtual Environment

Create a virtual environment to isolate the project dependencies:

```bash
python -m venv venv
```

Activate the virtual environment:

- **For macOS/Linux**:
  ```bash
  source venv/bin/activate
  ```

- **For Windows**:
  ```bash
  venv\Scripts\activate
  ```

### 3. Install Dependencies

Use the `Makefile` to install all required dependencies:

```bash
make install
```

This command will upgrade `pip` and install all necessary packages and dependencies listed in `requirements.txt`.

### 4. Environment Configuration

Copy the `example.env` file to `.env` and add your API keys for the providers you intend to use:

```bash
cp example.env .env
```

Edit the `.env` file to include your API keys:

```plaintext
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
GROQ_API_KEY=your_groq_api_key
GOOGLE_API_KEY=your_google_api_key
```

## Usage

### Running the Example

To see the system in action, run the `example_usage.py` script:

```bash
python example_usage.py
```

This script will guide you through selecting a provider and model, and then initiate a conversation between a human agent and an AI agent.

### Key Features

- **Modular Design**: Easily extendable to add new providers, models, and functionalities.
- **Memory Management**: Supports different memory types (buffer, summary, Redis) for maintaining conversation context.
- **Prompt Engineering**: Utilizes LangChain and LangGraph for advanced prompt engineering and memory integration.
- **Provider Integration**: Seamlessly integrates with multiple AI providers (OpenAI, Anthropic, Groq, Google) using a provider factory pattern.

## Project Structure

```
ai_agent_system/
├── README.md
├── requirements.txt
├── example_usage.py        # Usage example
├── setup.py
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py          # Base agent classes
│   │   ├── message.py        # Message definitions
│   │   └── types.py          # Common types and enums
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── human_agent.py    # Human agent implementation
│   │   └── ai_agent.py       # AI agent implementation
│   ├── communication/
│   │   ├── __init__.py
│   │   ├── hub.py           # Communication hub
│   │   └── protocols.py     # Communication protocols
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
    ├── __init__.py
    ├── test_agents/
    │   ├── __init__.py
    │   ├── test_human_agent.py
    │   └── test_ai_agent.py
    └── test_communication/
        ├── __init__.py
        └── test_hub.py
```

## Future Integration Points

- **Identity Management**: Can be added as a new module under `src/identity/`
- **Payment System**: Can be added as `src/payments/`
- **Storage**: Can be added as `src/storage/`
- **API Layer**: Can be added as `src/api/`

## Additional Commands

- **Lint the Code**: Check the code for style issues using `flake8`:

  ```bash
  make lint
  ```

- **Format the Code**: Automatically format the code using `black`:

  ```bash
  make format
  ```

- **Run Tests**: Execute the test suite using `pytest`:

  ```bash
  make test
  ```

- **Run All**: Perform installation, linting, formatting, and testing in sequence:

  ```bash
  make all
  ```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

# Installation

### Prerequisites

- Python 3.11 or higher
- Poetry (Python package manager)

### Installing AgentConnect

AgentConnect is currently available from source only. Direct installation via pip will be available soon.

### Development Installation

Clone the repository and install dependencies using Poetry:

```bash
git clone https://github.com/AKKI0511/AgentConnect.git
cd AgentConnect
poetry install --with demo,dev  # For development (recommended)
# For production only:
# poetry install --without dev
```

### Environment Setup

Copy the environment template and configure your API keys:

```bash
copy example.env .env  # Windows
cp example.env .env    # Linux/Mac
```

Edit the `.env` file to set your provider and API keys:

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

### Payment Capabilities (Optional)

AgentConnect supports agent-to-agent payments through the Coinbase Developer Platform (CDP). To enable these features, add the following to your `.env`:

```
CDP_API_KEY_NAME=your_cdp_api_key_name
CDP_API_KEY_PRIVATE_KEY=your_cdp_api_key_private_key
```

To obtain CDP API keys:
1. Create an account at [Coinbase Developer Platform](https://www.coinbase.com/cloud)
2. Create an API key with wallet management permissions
3. Save the API key name and private key securely

By default, payment features use the Base Sepolia testnet, which is suitable for development and testing without real currency.


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
Once the virtual environment is activated, run the following command to install all required dependencies:

```bash
make install
```

This will automatically set up all the necessary packages and dependencies for the project.

You're now ready to start working with the project!


# Project structure
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
│   └── utils/
│       ├── __init__.py
│       └── logger.py        # Logging utilities
└── tests/
    ├── __init__.py
    ├── test_agents/
    │   ├── __init__.py
    │   ├── test_human_agent.py
    │   └── test_ai_agent.py
    └── test_communication/
        ├── __init__.py
        └── test_hub.py

1. **Core Components**:
   - `core/`: Contains base classes and fundamental types
   - `agents/`: Different agent implementations
   - `communication/`: Handles message passing and agent interaction
   - `utils/`: Shared utilities and helpers

2. **Extension Points**:
   - New agent types can be added by extending `BaseAgent`
   - New message types can be added to `MessageType` enum
   - New communication protocols can be added to `protocols.py`
   - New capabilities can be added to `AIAgent`

3. **Future Integration Points**:
   - Identity Management: Can be added as a new module under `src/identity/`
   - Payment System: Can be added as `src/payments/`
   - Storage: Can be added as `src/storage/`
   - API Layer: Can be added as `src/api/`

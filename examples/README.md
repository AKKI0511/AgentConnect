# AgentConnect Examples

This directory contains examples demonstrating various features and use cases of the AgentConnect framework.

## Prerequisites

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/AKKI0511/AgentConnect.git
    cd AgentConnect
    ```
2.  **Install Dependencies:** Use Poetry to install base dependencies plus optional extras needed for specific examples (like demo, research, telegram).
    ```bash
    # Install core + demo dependencies (recommended for most examples)
    poetry install --with demo

    # Or install specific groups as needed
    # poetry install --with research
    ```
3.  **Set Up Environment Variables:** Copy the example environment file and fill in your API keys.
    ```bash
    # Windows
    copy example.env .env
    # Linux/macOS
    cp example.env .env
    ```
    Edit the `.env` file with your credentials. You need **at least one** LLM provider key (OpenAI, Google, Anthropic, Groq). See specific example requirements below for other keys (Telegram, Tavily, CDP).

## Running Examples (CLI Recommended)

The easiest way to run examples is using the `agentconnect` CLI tool:

```bash
agentconnect --example <example_name> [--verbose]
```

Replace `<example_name>` with one of the following:

*   `chat`: Simple interactive chat between a human and an AI agent.
*   `multi`: Demonstrates a multi-agent system for e-commerce analysis.
*   `research`: Research assistant workflow involving multiple agents.
*   `data`: Data analysis assistant performing analysis and visualization tasks.
*   `telegram`: A multi-agent system integrated with a Telegram bot interface.
*   `agent_economy`: Autonomous workflow showcasing agent-to-agent payments.

Use the `--verbose` flag for detailed logging output.

## Example Details

### Basic Chat (`chat`)

*   **Source:** `examples/example_usage.py`
*   **Description:** Demonstrates fundamental AgentConnect concepts: creating human and AI agents, establishing secure communication, and basic interaction.
*   **Optional:** Can be run with payment capabilities enabled (see `example_usage.py` comments and requires CDP keys in `.env`).

### E-commerce Analysis (`multi`)

*   **Source:** `examples/example_multi_agent.py`
*   **Description:** Showcases a collaborative workflow where multiple agents analyze e-commerce data.

### Research Assistant (`research`)

*   **Source:** `examples/research_assistant.py`
*   **Description:** An example of agents collaborating to perform research tasks, potentially involving web searches (requires `Tavily` key and `research` extras).
*   **Requires:** `poetry install --with research`, `TAVILY_API_KEY` in `.env`.

### Data Analysis Assistant (`data`)

*   **Source:** `examples/data_analysis_assistant.py`
*   **Description:** Agents work together to analyze data and generate visualizations.

### Telegram Assistant (`telegram`)

*   **Source:** `examples/multi_agent/multi_agent_system.py`
*   **Description:** Integrates a multi-agent backend (similar to research/content processing agents) with a Telegram bot front-end.
*   **Requires:** `TELEGRAM_BOT_TOKEN` in `.env`. 
    *   To get a token, talk to the [BotFather](https://t.me/botfather) on Telegram and follow the instructions to create a new bot.

### Autonomous Workflow with Agent Economy (`agent_economy`)

*   **Source:** `examples/autonomous_workflow/`
*   **Description:** Demonstrates a complete autonomous workflow featuring:
    *   Capability-based agent discovery.
    *   A user proxy orchestrating tasks between specialized agents (Research, Telegram Broadcast).
    *   Automated Agent-to-Agent (A2A) cryptocurrency payments (USDC on Base Sepolia testnet) using Coinbase Developer Platform (CDP).
*   **Requires:** LLM key(s), `TELEGRAM_BOT_TOKEN`, `TAVILY_API_KEY`, `CDP_API_KEY_NAME`, `CDP_API_KEY_PRIVATE_KEY` all set in `.env`.
    *   **Telegram Token:** See instructions in the `telegram` example section above.
    *   **CDP Keys:** 
        1. Sign up/in at [Coinbase Developer Platform](https://cloud.coinbase.com/products/develop).
        2. Create a new Project if needed.
        3. Navigate to the **API Keys** section within your project.
        4. Create a new API key with `wallet:transaction:send`, `wallet:transaction:read`, `wallet:address:read`, `wallet:user:read` permissions (or select the pre-defined "Wallet" role).
        5. Securely copy the **API Key Name** and the **Private Key** provided upon creation and add them to your `.env` file.

## Monitoring with LangSmith

All examples are configured to integrate with LangSmith for tracing and debugging.

1.  **Enable Tracing:** Ensure these variables are set in your `.env` file:
    ```
    LANGSMITH_TRACING=true
    LANGSMITH_API_KEY=your_langsmith_api_key
    LANGSMITH_PROJECT=AgentConnect # Or your preferred project name
    # LANGSMITH_ENDPOINT=https://api.smith.langchain.com (Defaults to this if not set)
    ```
2.  **Monitor:** View detailed traces of agent interactions, tool calls, and LLM usage in your LangSmith project.

## Troubleshooting

*   Ensure you run commands from the project root directory.
*   Verify all required dependencies for the chosen example are installed (e.g., `poetry install --with demo`).
*   Double-check that all necessary API keys and tokens are correctly set in your `.env` file.
*   Use the `--verbose` flag when running via CLI for detailed logs.
*   Check LangSmith traces for deeper insights into execution flow and errors.

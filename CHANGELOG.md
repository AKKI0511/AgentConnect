# Changelog

All notable changes to AgentConnect will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Team Runtime with store-backed mailboxes, Tickets, and Thread history. `Team("name").start()` serves join, send, lease, complete, reply, get_result, get_history, find, and get_profile. Memory is the default store; Redis keeps open Tickets across a Runtime restart.
- Agent Session and handler contract. Subclass `BaseAgent`, implement `process_message(msg, ctx)`, and `join` a Team in-process or by URL. The Session pulls work, maps return / None / raise / `ctx.ticket()` onto Runtime reply and complete, retries while the Team is coming up, and reconnects after a restart. `Team.serve()` exposes the HTTP binding (POST + SSE) on loopback.
- Join authentication. Every Agent has an Ed25519 `did:key`. `Team.issue_join_token` issues a scoped, expiring, revocable token. Network joins (`require_join_auth=True`) require that token plus an EdDSA identity proof. Revoking a token or removing a Membership drops the Session immediately. The Runtime mints a membership attestation JWT at join; inbound verification of that statement is later work.
- Ticket and Thread contract. Open Tickets (and Thread Messages they still need) are kept until at least the deadline. `collect=wait` holds `send` for at most `wait_hold_seconds` (default 25) and then returns the current Ticket. `BaseAgent.ask(collect="wait")` still waits for a terminal Ticket. A Delivery history window is capped by count and by `max_message_bytes`. `get_history(before=...)` with a missing UUID returns the newest page. `callback` and `stream` fail with `unsupported_collect_mode`.

### Changed
- Replaced the in-process communication hub and Future-backed response tracker. The Runtime never holds Agent objects and never calls a method on an Agent.
- Replaced `BaseAgent.run()`, the per-agent queue, and the 100ms poll loop with a pull Session. `join_network` / `register_agent` are gone. `process_message` takes `(msg, ctx)`.
- Switched Agent and Team key generation from RSA to Ed25519 `did:key`. Join identity proofs and MCP access tokens are EdDSA JWTs.
- Renamed ready-made agents from `agentconnect.agents` to `agentconnect.prebuilt`.
- Moved `aiogram`, `cdp-sdk`, and `aioconsole` to optional extras (`telegram`, `payments`, `cli`).
- Promoted `fastapi` and `uvicorn` to core dependencies so serving no longer requires the demo group.
- Laid out the Team-based package tree: `core/` (nouns), `agent/` (client SDK), `team/` (runtime), `transport/`, `gateway/`, and `index/`. `BaseAgent` lives in `agent/`. Message `kind` is the closed set `request`, `response`, `error`, `event`.
- Import boundaries are enforced with `import-linter`: `core/` imports no siblings, `agent/` and `team/` do not import each other, and nothing imports `prebuilt/`.

### Removed
- Deleted unused `agentconnect.communication.protocols`.
- Removed `pylint` and the PyPI `asyncio` backport from runtime dependencies.
- Removed the `communication/`, `servers/`, and `clients/` packages after moving their code into `team/`, `transport/`, `gateway/`, `index/`, and `config/`.

### Planned
- A2A communication hardening: ResponseTracker, HTTP transport SPI, Inbox server, metrics, remote A2A support.
- Unified AgentIdentity with registry-verified connect flows (DID-JWT/challenge) and route grants.
- Message v2 (payload, correlation_id, conversation_id), reply()/ignore() helpers.
- Hub-owned queue service and agent pull workers.
- Per-hub MCP communication server and hub-owned auth.
- Protocol adapters: Google A2A, IBM ACP, Google AP2 (outbound adapters and inbound gateways).
- Composite runtime (single ASGI) and improved CLI UX (serve runtime, human chat/send, register/unregister).

## [0.4.0] - 2026-07-02

### Added
- New `AgentProfile`, `Skill` classes in `types.py` for comprehensive agent configuration
- Enhanced capability discovery service using Qdrant vector database
- Improved agent search tool with filtering options and customizable result detail levels
- New folder structure for capability discovery implementation
- Dedicated folder for collaboration tools with improved organization
- MCP (Model Context Protocol) server (`agentconnect.mcp`) implementation for agent discovery and search tool
- Registry API server (`agentconnect.servers`) with FastAPI-based REST endpoints for agent operations
- Registry API client (`agentconnect.clients`) with async HTTP interface and retry logic
- Centralized search module (`agentconnect.core.registry.search`) with unified schemas and utilities
- Centralized SDK configuration system (`agentconnect.config`) with a single global settings object, YAML-based overrides, and helper utilities to generate, inspect, and validate configuration files
- New configuration CLI: `agentconnect config {init, show, validate}`
- Standalone server configuration via environment variables with production-friendly defaults and vector store options
- Comprehensive test suite for clients, servers, config, and MCP integration

### Changed
- refactor(cli): new CLI with config, serve, mcp, ping, and doctor commands. Legacy `agentconnect/cli.py` removed; CLI now lives under `agentconnect/cli/` and console script remains `agentconnect`.
- Simplified constructor for `BaseAgent` with focus on profile-based configuration
- Updated `AIAgent`, `HumanAgent`, `TelegramAgent` constructor to support both profile-based and parameter-based initialization
- Enhanced `AgentRegistration` class with additional fields for advanced searches
- Refactored examples to use the new profile-based agent configuration
- Reorganized package dependencies in pyproject.toml
- `AgentRegistration` converted from dataclass to Pydantic BaseModel
- `CommunicationHub` to support both local and remote registry clients
- Agent search tool to use centralized search schemas
- Project dependencies updated with MCP protocol and FastAPI support
- Adopted centralized settings across clients, agents, registry, communication hub, MCP, and utils
- Unified vector store configuration with in-memory, local-file, and remote modes
- Environment example files reorganized for clarity: root `example.env` for SDK-level variables; new `demos/.env.example` for demo-local secrets

### Deprecated
- Logging policy finalized: library uses NullHandler only; no handlers are added. MCP logs via Context; registry logs use uvicorn logger; CLI/examples control logging level per run. Experimental logging helpers removed.

### Removed
- SDK logging helpers and related config. Library no longer adds handlers or changes third-party loggers.
- Legacy core configuration module, replaced by centralized settings
- Temporary payment constants, consolidated into configuration

### Fixed
- Corrected release dates in CHANGELOG.md from 2024 to 2025
- Agent unregistration to properly call registry.unregister() method
- Registry index management for capabilities and organizations
- Agent registration update process to handle all fields correctly
- Updated Google provider and types to reflect Gemini model changes

### Known Limitations
- Identity verification and registration flows are not yet unified; registry-verified connect (DID-JWT/challenge) and route grants will land post-0.4.0.
- Message correlation remains metadata-based and will move to a first-class `correlation_id` in Message v2.
- Current `hub.register(agent)` API will be replaced by `agent.register(hub)` with hub-owned queues and agent pull workers.
- Registry registration currently accepts full identity payloads; future versions will only accept a public view plus proof and will return a short-lived route grant.
- Only Discovery MCP is available in 0.4.0 (search/browse). Communication MCP (send/check) arrives in a later 0.x release.
- Concurrency/backpressure in the hub is basic; ResponseTracker and queue backends arrive later.
- Only local A2A is supported; remote A2A transport and inbox arrive later.
- `agentconnect.yaml` exists but will be hardened and expanded in upcoming releases.

## [0.3.0] - 2025-05-02

### Added
- Agent payment capabilities using Coinbase Developer Platform (CDP) SDK and AgentKit.
- Wallet persistence for agents (`agentconnect.utils.wallet_manager`).
- CDP environment validation and payment readiness checks (`agentconnect.utils.payment_helper`).
- Payment-related dependencies (`cdp-sdk`, `coinbase-agentkit`, `coinbase-agentkit-langchain`) to `pyproject.toml`.
- Payment address (`payment_address`) field to `AgentMetadata` and `AgentRegistration`.
- Payment capability template (`PAYMENT_CAPABILITY_TEMPLATE`) for agent prompts.
- Autonomous workflow demo (`examples/autonomous_workflow`) showcasing inter-agent payments.
- Standalone chat method in `AIAgent` for using agents without registration to a hub.
- Response callbacks in `HumanAgent` for integration with external systems.
- Asynchronous collaboration request status checking tool for handling delayed agent responses.
- Enhanced reasoning step visualization in `ToolTracerCallbackHandler` for all LLM providers.
- Comprehensive end-to-end developer guides in documentation.
- Improved model support for OpenAI and Google AI.

### Changed
- `BaseAgent` and `AIAgent` to initialize wallet provider and AgentKit conditionally based on `enable_payments` flag.
- `AIAgent` workflow initialization to include AgentKit tools when payments are enabled.
- Agent prompts (`CORE_DECISION_LOGIC`, ReAct prompts) updated to include payment instructions and context.
- `CommunicationHub` registration updated to include `payment_address`.
- `ToolTracerCallbackHandler` enhanced to provide specific tracing for payment tool actions.
- Enhanced `HumanAgent` to function as an independent agent in the network with `run()` method.
- Added `stop()` method to `BaseAgent` for proper cleanup and resource management.
- `CommunicationHub` improved to handle late responses and request timeouts gracefully.
- Simplified and enhanced prompt templates for more customizable agents.
- Updated all examples to use the `stop()` method for better cleanup.
- Refactored postprocessing logic in `agent_prompts.py` for better error handling.

### Deprecated
- `examples/run_example.py` in favor of using the official CLI tool (`agentconnect` command)

### Fixed
- Suppressed unnecessary warnings in capability discovery module
- Improved error handling in agent communication
- Fixed reasoning step extraction for different LLM providers (OpenAI, Anthropic, Google)
- Addressed collaboration request timeouts with new polling mechanism

### Security
- Enhanced validation for inter-agent messages
- Implemented secure API key management
- Added rate limiting for API calls
- Set up environment variable handling
- Added input validation for all API endpoints

## [0.2.0] - 2025-04-01

### Added
- Research dependency group (`poetry install --with research`) for enhanced research capabilities
- Modular multi-agent system with separate specialized agent implementations
- Enhanced research assistant example with improved web search capabilities
- Vector embedding support in the agent registry for semantic search capabilities
- 'max_turns' configuration parameter for AIAgent class to limit conversation length

### Changed
- Refactored Telegram assistant into modular multi-agent system with independent components
- Updated CLI to use the new modular multi-agent system
- Updated documentation and examples to reflect new architecture
- Enhanced registry with vector embeddings for more accurate agent capability matching
- Delegated tool implementations to specialized custom_tools modules for better separation of concerns
- Optimized prompt templates to reduce redundancy and improve maintainability
- Updated Telegram agent implementation with improved configuration options
- Updated project dependencies to latest versions for improved performance and security

### Deprecated
- `examples/run_example.py` in favor of using the official CLI tool (`agentconnect` command)

### Fixed
- Suppressed unnecessary warnings in capability discovery module
- Improved error handling in agent communication

### Security
- Enhanced validation for inter-agent messages

## [0.1.0] - 2025-03-13

### Added
- Core agent management system with multiple AI provider support:
  - OpenAI integration
  - Anthropic integration
  - Groq integration
  - Google AI integration
- Multi-agent communication framework:
  - Asynchronous message passing
  - Structured conversation handling
  - Agent state management
- Example applications:
  - Basic chat with AI assistant
  - Multi-agent e-commerce analysis
  - Research assistant with multiple agents
  - Data analysis and visualization assistant
- Documentation:
  - Installation and setup guides
  - API reference
  - Usage examples
  - Contributing guidelines
- Development tooling:
  - Poetry-based dependency management
  - Automated testing with pytest
  - GitHub Actions workflows
  - Code quality tools (black, flake8, pylint)
- Security features:
  - Environment variable management
  - API key handling
  - Rate limiting support

### Security
- Implemented secure API key management
- Added rate limiting for API calls
- Set up environment variable handling
- Added input validation for all API endpoints

[Unreleased]: https://github.com/AKKI0511/AgentConnect/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/AKKI0511/AgentConnect/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/AKKI0511/AgentConnect/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/AKKI0511/AgentConnect/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/AKKI0511/AgentConnect/releases/tag/v0.1.0

# Changelog

All notable changes to AgentConnect will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

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

## [0.1.0] - 2024-03-13

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

[Unreleased]: https://github.com/AKKI0511/AgentConnect/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/AKKI0511/AgentConnect/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/AKKI0511/AgentConnect/releases/tag/v0.1.0

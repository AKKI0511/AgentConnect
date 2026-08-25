# Repository Guidelines

## Specification-First Rewrite

- AgentConnect is a runtime for Teams of independent AI agents.
- `spec/` is the design authority for the Team-based `0.5` rewrite. The legacy source tree must not override its names or boundaries while the rewrite is in progress.
- Public specification files contain only the current release contract. Keep internal planning, business information, later-release ideas, and implementation speculation out of `spec/`.
- Prefer a small closed contract over broad incomplete coverage. A public field or operation needs one meaning, one owner, and an observable test.
- Keep definitions, short explanations, examples, and behavioral vectors together when practical. Do not create a separate example file for one nearby example.
- `spec/schema/schema.ts` is the structural source of truth. Document every public type and non-obvious field there, then regenerate `schema.json`.
- Use `Skill` for what an Agent offers. Avoid a second overlapping noun for the same idea.
- Preserve the distinction between Team, Runtime, Membership, Session, Message, Delivery, Ticket, and Thread.
- Describe AgentConnect only as a runtime. Do not categorize it as a wire or communication standard.

## Project Structure & Module Organization
- Source: `agentconnect/` with subpackages `core/` (nouns), `agent/` (client SDK), `team/` (runtime), `transport/`, `mcp/`, `gateway/`, `index/`, `cli/`, `config/`, `prebuilt/`. `providers/` and `prompts/` remain until the helper rebuild. CLI lives in `agentconnect/cli/` and exposes the `agentconnect` entrypoint.
- Tests: `tests/` mirrors packages (e.g., `tests/core/`, `tests/team/`); configuration in `tests/pytest.ini`.
- Docs & examples: `docs/`, `demos/`, `examples/`. Data/scratch: `data/`, `downloads/`.
- Packaging/build: `pyproject.toml` (Poetry), targets in `Makefile`. Import boundaries are enforced with `import-linter` (`make lint`).

## Build, Test, and Development Commands
- Install: `make install-dev` (or `poetry install --with dev --extras "telegram payments cli"`); all extras: `make install-all`.
- Lint/format: `make lint` (Flake8) and `make format` (Black). Hooks: `make install-hooks` then `make hooks`.
- Test: `make test` (runs `pytest -v`); include slow tests: `poetry run pytest -m slow`.
- Docs: `make docs` (HTML build); clean with `make docs-clean`.
- Run CLI: `poetry run agentconnect --help` to explore commands.

## Coding Style & Naming Conventions
- Python 3.11–3.12; use 4-space indent and type hints for public APIs.
- Formatting via Black; linting via Flake8 (some minor rules relaxed in Makefile).
- Naming: modules/functions `snake_case`, classes `CamelCase`, constants `UPPER_SNAKE`.
- Use standard Python logging (`logging.getLogger(__name__)`) and `agentconnect/config` for configuration.

## Testing Guidelines
- Framework: Pytest + `pytest-asyncio` for async code.
- Location/naming: place tests under `tests/<area>/test_*.py`; classes `Test*`, functions `test_*`.
- Markers: slow tests are skipped by default; include with `-m slow`.
- Add unit tests with new features and fixes; prefer focused tests near touched modules.

## Commit & Pull Request Guidelines
- Conventional commits are used: `feat:`, `fix:`, `refactor:`, `chore:`, `ci:` (see git history).
- PRs: clear description, linked issues, CLI/demo snippets where relevant, updated tests/docs. Ensure `make lint format test` and pre-commit hooks pass.

## Security & Configuration Tips
- Copy `example.env` to `.env` and set provider keys; never commit secrets.
- Prefer environment variables/`dotenv`; grant least privileges and rotate credentials regularly.

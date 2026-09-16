# Contributing

## Development setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use Python 3.11 through 3.14.

```bash
git clone https://github.com/AKKI0511/AgentConnect.git
cd AgentConnect
uv sync --extra serve --extra cli --extra index --extra openai
```

Use your fork's URL if contributing through a fork. Pull requests target `main`. The test suite covers HTTP, CLI, Index, and hosted Directory tokenizer behavior, so the setup includes those extras.

## Tests and code style

```bash
uv run --extra serve --extra cli --extra index --extra openai pytest tests/ -q
uvx ruff@latest check agentconnect tests examples docs/generate_docs.py
uvx ruff@latest format agentconnect tests examples docs/generate_docs.py
```

A test file or directory can replace `tests/`. Routine tests do not need provider API keys. Optional Ruff commit hooks are available with `uvx pre-commit@latest install`.

## Public API

The public schema is in `spec/schema/schema.ts`; its Python models are in `agentconnect/core/`. Changes to public fields need matching definitions. With Node LTS installed:

```bash
npm --prefix spec/schema ci
npm --prefix spec/schema run generate
npm --prefix spec/schema run check
```

Package boundaries and generated-file locations are listed in [AGENTS.md](AGENTS.md).

## Documentation

[docs/README.md](docs/README.md) covers website changes, local preview, and API docstrings. The website includes the root [CHANGELOG.md](CHANGELOG.md), so release notes only need one edit.

## Pull requests

- Describe the problem and the change.
- Include tests for changed behavior and note what you ran.
- Update affected documentation and user-facing release notes.
- Keep unrelated changes in separate pull requests.

An issue is useful for discussing substantial features before implementation. Small fixes can go straight to a pull request. AI-assisted contributions follow the same review process.

## Code of conduct

The [Code of Conduct](CODE_OF_CONDUCT.md) applies to contributions and discussions.

## License

Contributions are distributed under the project's [Apache 2.0 license](LICENSE).

# Contributing

## Development setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use Python 3.11 through 3.14.

```bash
git clone https://github.com/AKKI0511/AgentConnect.git
cd AgentConnect
uv sync --extra serve --extra cli --extra index --extra openai --extra redis
```

Use your fork's URL if contributing through a fork. Pull requests target `main`. The test suite covers HTTP, CLI, Index, and hosted Directory tokenizer behavior, so the setup includes those extras.

## Tests and code style

```bash
uv run --extra serve --extra cli --extra index --extra openai --extra redis pytest tests/ -q
uvx ruff@latest check agentconnect tests examples benchmarks docs/generate_docs.py
uvx ruff@latest format --check agentconnect tests examples benchmarks docs/generate_docs.py
```

A test file or directory can replace `tests/`. Routine tests do not need provider API keys. Remove `--check` from the format command to apply formatting. Optional Ruff commit hooks are available with `uvx pre-commit@latest install`.

Redis cases skip locally when Redis is unavailable, but are required in Linux CI.
For the complete suite, start a dedicated test server (recovery tests restart it):

```bash
docker run -d --name agentconnect-test-redis -p 127.0.0.1:6380:6379 redis:8.2 redis-server --enable-debug-command yes --appendonly yes
```

On later runs use `docker start agentconnect-test-redis`. Tests default to
`redis://127.0.0.1:6380/15`; set `REDIS_URL` to use another dedicated test server.
Set `AGENTCONNECT_REQUIRE_REDIS=1` if a missing server should fail locally too.

## Performance

Routine tests do not run the full benchmark matrix. GitHub's **Performance**
workflow runs for relevant Runtime and benchmark changes and supports manual runs.
It checks discovery, overlapping messaging, and event-loop responsiveness with
pytest-benchmark, saving JSON measurements and JUnit results even on failure.
See [Runtime benchmarks](benchmarks/runtime/README.md) for focused local commands
and `make perf`. No benchmark dependency is added to a normal library install.

## Dependency changes

After changing `pyproject.toml` dependencies, extras, or groups, refresh every lockfile CI checks, then commit them together:

```bash
uv lock
uv lock --directory examples/quickstart
uv lock --directory examples/recipes
```

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

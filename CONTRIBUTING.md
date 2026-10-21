# Contributing

## Development setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use Python 3.11 through 3.14. CI installs the latest stable uv.

```bash
git clone https://github.com/AKKI0511/AgentConnect.git
cd AgentConnect
uv sync --extra redis --extra embeddings --extra prebuilt
```

Use your fork's URL if contributing through a fork. Pull requests target `main`. The extras add Redis persistence, local/hosted embedding tokenizers, and prebuilt agents, which the test suite also exercises.

## Tests and code style

```bash
uv run --locked --extra redis --extra embeddings --extra prebuilt pytest tests/ -q
uvx ruff@latest check agentconnect tests examples experiments benchmarks .github/scripts
uvx ruff@latest format --check agentconnect tests examples experiments benchmarks .github/scripts
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
It checks hashed and neural find latency, overlapping messaging, event-loop
responsiveness, request/reply exchange, and public SDK collaboration with
pytest-benchmark. Groups stop after a failure and still upload any JSON and
JUnit collected. The 10,000-member stress probe is dispatch-only.
Retrieval ranking is a separate Discovery quality workflow.
See [Runtime benchmarks](benchmarks/runtime/README.md) for focused local commands
and `make perf`. Request/reply steps are in
[request_reply/README.md](benchmarks/runtime/request_reply/README.md).
Collaboration steps are in
[public_sdk/README.md](benchmarks/runtime/public_sdk/README.md).
No benchmark dependency is added to a normal library install.

## Retrieval quality

Runtime performance and retrieval quality are separate checks. Run the
retrieval benchmark when a change can affect who `find` ranks: Profile text,
Directory embedding, or the hashed or FastEmbed path. Unrelated edits do not
need it. It does not use Redis or a chat-model key. Install the embeddings
extra, then follow [Discovery retrieval](benchmarks/discovery/README.md):

```bash
uv sync --locked --extra embeddings
uv run --no-sync python -m benchmarks.discovery.check
uv run --no-sync python -m benchmarks.discovery.score
```

Results are written to `benchmarks/discovery/artifacts/discovery-v1/`.
Coverage@10 and MRR on the held-out shuffled split are the gates. Coverage@1,
coverage@5, slices, and small-versus-large roster rows are context. A miss
names the need, the backend, and the rank of the acceptable recipient. A
roster no larger than the cutoff cannot show a miss at that cutoff. A neural
load failure or Directory fallback stays under `failed/` and is not filled
in with hashed ranks. `score` exits non-zero when a required backend or a
ranking gate fails. GitHub's Discovery quality workflow runs the same
commands on relevant paths.

## Dependency changes

After changing `pyproject.toml` dependencies, extras, or groups, refresh every lockfile CI checks, then commit them together:

```bash
uv lock
uv lock --directory examples/quickstart
uv lock --directory examples/recipes
uv lock --directory experiments/team_tools
```

## Qualitative Team tool-use

[`experiments/team_tools/`](experiments/team_tools/README.md) is a durable, harness-independent environment for judging Team MCP tools from a coding harness. It is not a user example, an automated benchmark, or a mandatory LLM run.

Use it when advertised Team tools, their descriptions, or the ship-desk fixtures change. Start `uv run python team.py`, add the printed MCP URL with native MCP support, then follow `PROMPT.md` and `CHECKLIST.md`. Startup, messaging and shutdown smoke checks run in `tests/experiments/test_team_tools.py`.

## Public API

The public schema is in `spec/schema/schema.ts`; its Python models are in `agentconnect/core/`. Changes to public fields need matching definitions. With Node LTS installed:

```bash
npm --prefix spec/schema ci
npm --prefix spec/schema run generate
npm --prefix spec/schema run check
```

Package boundaries and generated-file locations are listed in [AGENTS.md](AGENTS.md).

## Documentation

The public site lives in [`docs-v2/`](docs-v2/README.md). From that directory: `uv sync --locked`, `npm ci`, then `npm run dev` to preview or `npm run check` to validate. Preview CI generates the Python reference from the pull-request tree, then checks the site and uploads a preview artifact. It does not write `docs-release`.

Production docs use `docs-release` and API from the published package. Retry
**Docs release** with the original version, SHA, CI run ID and artifact ID.
For guide corrections, choose `docs-only` and a full main SHA descended from
the current guide source. Published Release assets support docs retries after
CI artifact expiry. Older sources and conflicting same-version snapshots fail;
identical reruns are no-ops. See [docs-v2/README.md](docs-v2/README.md) for host
configuration. Release history lives in [CHANGELOG.md](CHANGELOG.md).

## Releases

Version bumps belong on `release/*` pull requests. CI rejects version changes from other PR branches. Protect `main` with required pull requests and the `CI` check to enforce this policy; direct pushes bypass the PR branch check.

Release publishes the wheel and sdist tested by successful main CI, without
rebuilding. It verifies commit, version, artifact identity and hashes; matching
partial uploads can resume, while conflicts fail. CI artifacts last 90 days.
To retry publication, dispatch **Release** from `main` with the original
successful CI run ID. Missing artifacts must be recovered before publication.
GitHub Release retains distributions and intent for durable docs retries.

One-time setup before an authorized publication:

1. Protect `main` with required pull requests and required `CI` status.
2. Create GitHub Environment `pypi-prod`, limited to `main`, with required reviewers.
3. Configure the PyPI Trusted Publisher for project `agentconnect`: GitHub organization `AKKI0511`, repository `AgentConnect`, workflow `release.yml`, environment `pypi-prod`.
4. Claim the PyPI project name if it is still unclaimed.

Contributor pull requests need no publish credentials. Publication waits for approval from the `pypi-prod` environment reviewers.


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

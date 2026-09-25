# AgentConnect website (Mintlify)

Isolated Mintlify documentation project. The legacy Sphinx site under `docs/` is untouched.

## Architecture

| Path | Role |
| --- | --- |
| `*.mdx`, `concepts/`, `guides/`, `examples/` | **Handwritten** guides (write these) |
| `python-api/index.mdx` | **Handwritten** API tab overview |
| `python-api/*.mdx` (everything else) | **Generated** from Python via mdxify + Griffe 2 |
| `python-api-pages.json` | **Generated** Mintlify nav fragment (`$ref` from `docs.json`) |
| `docs.json` | Mintlify config, theme, handwritten navigation |
| `scripts/generate_api.py` | Thin wrapper around mdxify (excludes, banners, paths) |
| `scripts/check.py` | Stale / deterministic / config / Mintlify checks |
| `pyproject.toml` + `uv.lock` | Docs-only Python tooling (isolated from runtime deps) |
| `package.json` + `package-lock.json` | Pinned `mint` CLI |

Do **not** hand-edit generated API MDX. Files carry a `DO NOT EDIT` banner. CI fails if the tree drifts from a fresh generation.

## Commands (from repository root)

```bash
make website          # generate API reference + start Mintlify locally
make website-check    # all docs checks (stale, deterministic, mint validate, links)
make website-api      # regenerate API MDX only
```

Equivalent from this directory:

```bash
uv sync
npm ci
uv run python scripts/generate_api.py
npm run dev           # mint dev
uv run python scripts/check.py
```

## Stack (September 2026)

- Mintlify Pro / `mint` CLI (`mint` npm package — not legacy `mintlify`)
- MDX + `docs.json`
- Griffe 2 (`griffe` meta-package → `griffelib`)
- [mdxify](https://github.com/zzstoatzz/mdxify) for Griffe → Mintlify MDX (same approach as FastMCP/Prefect)
- `uv` for Python tooling; discovery patterns adapted from `modelcontextprotocol/python-sdk` `scripts/docs/` (no Zensical/mkdocstrings)

## Public API surface

Generation documents public (non-`_`) modules under `agentconnect`, excluding:

- `agentconnect.gateway`
- `agentconnect.utils`
- `agentconnect.index.registry.capability_discovery_impl`

Adjust excludes in `scripts/generate_api.py` when the public surface changes.

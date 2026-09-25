# AgentConnect docs-v2 (Mintlify)

Isolated Mintlify documentation project. The legacy Sphinx site under `docs/` is untouched until cutover.

## Architecture

| Path | Role |
| --- | --- |
| `*.mdx`, `concepts/`, `guides/`, `examples/` | **Handwritten** guides |
| `api-reference.mdx` | **Generated** from `agentconnect/__init__.py` (API tab landing page) |
| `api/*.mdx` | **Generated** module/package pages |
| `api-pages.json` | **Generated** Mintlify nav (`$ref` from `docs.json`) |
| `docs.json` | Mintlify config + handwritten navigation |
| `style.css` / `site.js` | Dark-first chrome, glass header, dense API sidebar |
| `scripts/generate_api.py` | mdxify + reshape (roots, short labels, docstring polish) |
| `scripts/check.py` | Stale / deterministic / config / Mintlify checks |

### Site chrome

- Aspen theme, **dark default**, Syne + Manrope fonts
- Fixed dual header: logo left · search center · GitHub + theme right; second row tabs (Documentation / Cookbooks / Reference / Contribute)
- Header goes frosted glass on scroll (`site.js` + `style.css`)

### API navigation rules

- Opening the **Reference** tab shows `api-reference.mdx` (`agentconnect` package docstring).
- A package group such as **agent** uses Mintlify `root` pointing at that package's `__init__.py` page — there is no visible `__init__` child.
- Sidebar labels drop the `agentconnect.` prefix (`agent`, `core`, `team`, …). Leaf pages keep short names (`base`, `runtime`).
- Sidebar row spacing is intentionally dense (custom CSS).

Do **not** hand-edit generated API MDX. Files carry a `DO NOT EDIT` banner. CI fails if the tree drifts.

## Commands (from repository root)

```bash
make docs-v2          # generate API reference + start Mintlify locally
make docs-v2-check    # all docs checks
make docs-v2-api      # regenerate API MDX only
```

## Docstring contract

Write **Google**-style docstrings so Args / Returns / Raises / Examples parse correctly. See [guides/docstrings](/guides/docstrings).

## Stack (September 2026)

- Mintlify Pro / `mint` CLI (npm `mint`, not legacy `mintlify`)
- MDX + `docs.json`
- Griffe 2 (`griffe` → `griffelib`) via [mdxify](https://github.com/zzstoatzz/mdxify)
- Nav/structure aligned with Typesafe + MCP Python SDK API reference patterns

## Public API surface

Excludes: `agentconnect.gateway`, `agentconnect.utils`, `agentconnect.index.registry.capability_discovery_impl`.

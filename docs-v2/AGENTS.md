# AgentConnect docs-v2 (Mintlify)

Isolated Mintlify documentation project. The legacy Sphinx site under `docs/` is untouched until cutover.

## Architecture

| Path | Role |
| --- | --- |
| `*.mdx`, `concepts/`, `guides/`, `examples/`, `integrate/`, `agents/`, `templates/` | **Handwritten** pages |
| `api-reference.mdx` | **Generated** from `agentconnect/__init__.py` (Reference tab landing page) |
| `api/*.mdx` | **Generated** module/package pages |
| `api-pages.json` | **Generated** Mintlify nav (`$ref` from `docs.json`) |
| `docs.json` | Mintlify config + handwritten navigation |
| `style.css` / `site.js` | Dark-first chrome, skip link, dense API sidebar |
| `scripts/generate_api.py` | mdxify + reshape (roots, short labels, docstring polish) |
| `scripts/check.py` | Stale / deterministic / config / Mintlify checks |

### Site chrome

- Aspen theme, **dark default**, IBM Plex Sans + IBM Plex Mono
- Sharp near-black (`#0E0E10`) and bright white; faint hairlines
- Sidebar **section labels** (Start, Concepts, …) sit farther apart than files in a section. Nested dropdowns use Mintlify `expanded: false`, look like file rows, and start closed. Dummy nested pages live under **Surfaces**.
- Body copy is grey; headings and links stay bright.
- Code blocks use native Mintlify UI with Shiki `light-plus` / `dark-plus`. No custom syntax colors.
- Tabs: Docs / Examples / Reference
- Header: logo, search, GitHub, theme. Skip link injected by `site.js`

### Information architecture

- **Docs:** Start, Concepts (nouns), Guides (jobs), Connect (Python / CLI / MCP), Agents, Contribute
- **Examples:** copyable recipes
- **Reference:** generated Python API
- Page templates under Contribute are for writers. They are not product docs.

### Visual rules

- No teal/cyan accent, glass, gradients, or card mosaics
- Light theme is designed, not inverted dark
- Cards, if used, have no icons and no hover lift
- Next steps are lists, not tiles

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

## Stack

- Mintlify Pro / `mint` CLI (npm `mint`, not legacy `mintlify`)
- MDX + `docs.json`
- Griffe 2 (`griffe` → `griffelib`) via [mdxify](https://github.com/zzstoatzz/mdxify)

## Public API surface

Excludes: `agentconnect.gateway`, `agentconnect.utils`, `agentconnect.index.registry.capability_discovery_impl`.

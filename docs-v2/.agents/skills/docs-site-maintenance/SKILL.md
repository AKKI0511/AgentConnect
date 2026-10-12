---
name: docs-site-maintenance
description: Maintain this repository's Mintlify website, Python reference generation, navigation and validation. Use for docs-v2 infrastructure and publishing decisions, not SDK prose or model-facing tool design.
---

# Documentation site maintenance

Work in `docs-v2/`. The SDK lives in `../agentconnect/`. The legacy `../docs/` site stays until explicit cutover. Do not require private planning files or skills to maintain this site.

## Ownership

- `docs.json` owns navigation and appearance; handwritten MDX is grouped by topic. `images/` owns assets, `snippets/` owns reused content. Remove unused demonstration pages instead of publishing a component gallery.
- `scripts/api_surface.py` owns the supported public module list and reference navigation. Do not expose internal modules by recursively documenting the SDK.
- `scripts/generate_api.py` statically reads Python through Griffe and griffe-pydantic. griffe2md and its two Jinja adapters render objects; `markdown.mjs` handles Markdown through Remark. Do not add a second parser, runtime import pass or prose-repair layer.
- Generated output is `api/*.mdx`, `api-reference.mdx`, and `api-pages.json`. Never edit it by hand. Package docstrings become overview pages; canonical object links lead to defining modules. Keep package roots and short sidebar labels.
- Preserve the existing Aspen design, Atkinson Hyperlegible Next typography, dark default, restrained glass header and native code blocks. Keep renderer markup in templates rather than source docstrings.

## Work loop

From `docs-v2/`, setup is `uv sync --locked` and `npm ci`. `npm run dev` generates current API pages before preview. After SDK edits, `npm run api` regenerates; reload the browser. `npm run check` verifies without fixing stale output. Do not install dependencies implicitly during checks or introduce a second task runner.

Keep dependencies and their locks together. Keep site logic here; `.github/workflows/docs-v2.yml` is the GitHub-required entry point and calls the same local check. Root AGENTS.md links here; root Makefile has no site targets.

Use the repository's public `python-api-reference` skill for Python prose and `agent-tool-design` for model-facing interfaces. README.md explains the workflow to humans without linking skills; AGENTS.md routes coding agents. Authoring policy belongs in skills, not website pages.

## Publishing policy

Commit generated MDX and navigation with the source that produced them. They are marked `linguist-generated` to reduce review noise. CI rejects stale output; it does not auto-commit or create another docs branch. Mintlify consumes the configured repository directory. A local npm hook is not evidence that hosted Mintlify executes Python.

This follows [Mintlify's generated-page pattern](https://www.mintlify.com/docs/create/reusable-snippets#generate-snippets-and-pages-from-yaml): generate files into the documentation source repository. We use reviewed source-plus-output changes rather than a bot commit. Do not ignore required pages without first implementing and verifying a replacement deployment path.

## Verification

Run `npm run check`: semantic generator tests, supported surface/navigation, freshness, determinism, MDX compilation, canonical links, Mintlify validation and broken links. Generated changes require inspection of representative constructors, methods, properties, models and aliases. Retain tests that catch real rendering failures; avoid exact-prose snapshots.

For navigation or appearance changes, inspect the existing preview at desktop and narrow widths: package roots, object anchors, long signatures, code fences and missing-page behavior. Check source regeneration when changing the preview workflow. Exclude tooling and agent instructions using `.mintignore`. Report local checks separately from CI, hosted search and deployment; none implies prose acceptance.

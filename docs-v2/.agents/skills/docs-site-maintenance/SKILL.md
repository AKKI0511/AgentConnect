---
name: docs-site-maintenance
description: Maintain this repository's Mintlify website, Python reference generation, navigation and validation. Use for docs-v2 infrastructure and publishing decisions, not SDK prose or model-facing tool design.
---

# Documentation site maintenance

Work in `docs-v2/`. The SDK lives in `../agentconnect/`. The legacy `../docs/` site stays until explicit cutover. Do not require private planning files or skills to maintain this site.

## Ownership

- `docs.json` owns navigation and appearance; handwritten MDX is grouped by topic. `images/` owns assets, `snippets/` owns reused content. Remove unused demonstration pages instead of publishing a component gallery.
- `scripts/api_surface.py` owns the supported public module list and reference navigation. Do not expose internal modules by recursively documenting the SDK.
- `scripts/generate_api.py` statically reads Python through Griffe and griffe-pydantic. griffe2md and small Jinja adapters render objects; `markdown.mjs` handles Markdown through Remark. Do not add a second parser, runtime import pass or prose-repair layer.
- Generated output is `api/*.mdx`, `api-reference.mdx`, and `api-pages.json`. Never edit it by hand. Package docstrings become that group's Overview page at the existing package URL (`sidebarTitle: Overview`). Canonical object links lead to defining modules. Nested public packages get the same Overview child. The SDK root reference page and leaf modules such as CLI stay single pages, not Overview groups. Do not add a second Overview path or use group `root` as a clickable title.
- Preserve the existing Aspen design, Atkinson Hyperlegible Next typography, dark default and restrained glass header. Let Mintlify render code fences and colors. Use native Python fences for signatures and examples; link annotation references in ordinary Markdown outside the fences. Keep renderer markup out of source docstrings.

## Reference links and signatures

Plain backticks mean literal code. Use the established explicit reference form
``[`Record`][package.models.Record]`` for clickable prose symbols. Remark resolves
reference definitions from the Griffe public inventory; unresolved internal targets
fail generation. Keep docstrings readable without JSX. Standard Markdown links to
verified published URLs are appropriate when a universal href is needed.

Use Griffe expressions and canonical aliases for annotation links. Native fenced
signatures are copyable Python; their code tokens cannot also be hyperlinks. Put
linked types in native annotation/reference sections beside them. Keep short
signatures on one line and break long ones between parameters. Put async, property,
classmethod, and staticmethod labels immediately below the symbol name as a muted
metadata line (`ac-symbol-meta`), not in the heading. Do not add a signature
component, custom syntax colors, second Python parser, or inferred inline-code links.
Do not expose internals solely to create links. Apply field/default rules by
semantics, not package prefixes. Check canonical anchors and Markdown links in the
existing checker. Website links do not prove IDE hover support; verify the editor
separately before claiming it. Index callers own canonical `DirectoryEntry`
models; do not reconstruct identity or registration shapes in reference examples.

## Folder navigation

Mintlify top-level groups cannot collapse; they render as always-open headings.
Package folders must be nested groups (for this site, under the Reference tab's
Libraries heading) so they are real folders. Put that package's `__init__` page
first with `sidebarTitle: Overview`. Keep the SDK root reference page and leaf
modules such as CLI as pages, not Overview groups. Do not use group `root` as a
clickable title, and do not add a second Overview path.

Set `interaction.drilldown: true` for Aspen's native first-page navigation.
The whole pill, including the chevron and
keyboard activation, is one native toggle:

- Closed folder, current page outside its descendants: expand and open Overview.
- Closed folder, current page inside its descendants: expand; keep the current page.
- Open folder: collapse; keep the current page.

Opening a child or Overview link must not collapse that group. Mintlify `expanded`
is only the default open state.

Do not store or reinsert sidebar HTML, synthesize clicks, reach into React, force
visibility with CSS, or keep a second navigation state. If native Mintlify or Aspen
cannot match the matrix, report that limitation instead of masking it.

## Work loop

From `docs-v2/`, setup is `uv sync --locked` and `npm ci`. `npm run dev` generates current API pages before preview. After SDK edits, `npm run api` regenerates; reload the browser. `npm run check` verifies without fixing stale output. Do not install dependencies implicitly during checks or introduce a second task runner.

On Windows, stop the preview before editing or regenerating pages, then use
`npm run dev`. The pinned CLI's watcher passes backslash filenames into page
metadata; fresh scans normalize them. Inspect the actual href and pathname before
attributing missing native selection, ancestor expansion or eyebrows to the theme.
Keep page titles short and use `styling.eyebrows: section` for the native parent
label across the site. Leave sidebar hover and active styles to Mintlify.

Keep dependencies and their locks together. Keep site logic here; `.github/workflows/docs-v2.yml` is the GitHub-required entry point and calls the same local check. Root AGENTS.md links here; root Makefile has no site targets.

Use the repository's public `python-api-reference` skill for Python prose and `agent-tool-design` for model-facing interfaces. README.md explains the workflow to humans without linking skills; AGENTS.md routes coding agents. Authoring policy belongs in skills, not website pages.

## Publishing policy

Commit generated MDX and navigation with the source that produced them. They are marked `linguist-generated` to reduce review noise. CI rejects stale output; it does not auto-commit or create another docs branch. Mintlify consumes the configured repository directory. A local npm hook is not evidence that hosted Mintlify executes Python.

This follows [Mintlify's generated-page pattern](https://www.mintlify.com/docs/create/reusable-snippets#generate-snippets-and-pages-from-yaml): generate files into the documentation source repository. We use reviewed source-plus-output changes rather than a bot commit. Do not ignore required pages without first implementing and verifying a replacement deployment path.

## Verification

Run `npm run check`: semantic generator tests, supported surface/navigation, freshness, determinism, MDX compilation, canonical links, Mintlify validation and broken links. Generated changes require inspection of representative constructors, methods, properties, models and aliases. Retain tests that catch real rendering failures; avoid exact-prose snapshots.

For navigation or appearance changes, inspect the existing preview at desktop and narrow widths: package Overview folders, nested groups, object anchors, long signatures, code fences and missing-page behavior. Prove the native folder matrix with real clicks, not injected markup. Check source regeneration when changing the preview workflow. Exclude tooling and agent instructions using `.mintignore`. Report local checks separately from CI, hosted search and deployment; none implies prose acceptance.

---
name: docs-site-maintenance
description: Maintain this repository's Mintlify website, Python reference generation, navigation and validation. Use for docs-v2 infrastructure and publishing decisions, not SDK prose or model-facing tool design.
---

# Documentation site maintenance

Work in `docs-v2/`; the SDK is `../agentconnect/`. This directory is the only active documentation site. Handwritten pages remaining under `../docs/source/` are an inactive migration reference. Site maintenance must not require private plans or skills. Use public `python-api-reference` for SDK prose and `agent-tool-design` for tool interfaces. Human setup belongs in README.md; AGENTS.md routes agents; authoring policy stays out of website pages.

## Ownership and generation

- `docs.json`: navigation/appearance. Group handwritten MDX by topic; assets belong in `images/`, reused content in `snippets/`. Remove unused demo pages instead of publishing a component gallery.
- `scripts/api_surface.py`: supported modules/reference navigation. Do not expose internals through recursive discovery.
- `scripts/generate_api.py`: static Griffe/griffe-pydantic extraction, griffe2md/Jinja rendering; `markdown.mjs`: Remark conversion. Do not add a second parser, runtime import pass or prose-repair layer.
- Generated `api/*.mdx`, `api-reference.mdx`, `api-pages.json`: edit their source, never output by hand. Canonical object links target defining modules.
- Preserve Aspen, Atkinson Hyperlegible Next, dark default and restrained glass header. Leave code colors, sidebar hover and active styling to Mintlify. Keep titles short; `styling.eyebrows: section` supplies native parent labels.

## Links and signatures

Use ``[`Record`][package.models.Record]`` for prose symbol links; plain backticks remain literal. Remark resolves references against the Griffe inventory and fails unresolved internal targets. Verified absolute Markdown URLs provide portable links. Keep JSX out of docstrings.

Use Griffe expressions/canonical aliases for annotation links. Signatures/examples stay native Python fences: copyable code cannot also contain Markdown hyperlinks. Put linked types in adjacent annotation/reference sections. Keep short signatures on one line; break long ones between parameters. Put async/property/classmethod/staticmethod labels below symbol names in muted `ac-symbol-meta`, never headings or repeated badges. Do not add signature components or custom syntax colors.

Apply field/default rules by semantics, not package prefixes; do not expose internals just to link them. Check canonical anchors and Markdown links with the existing checker. Website links do not prove IDE hover support. Index examples use canonical `DirectoryEntry` snapshots such as `BaseAgent.get_entry`, not reconstructed identity/registration shapes.

## Native folder navigation

Top-level Mintlify groups are always-open headings. Nest package folders under Reference → Libraries. Each public package, including nested packages, has its existing `__init__` page first with `sidebarTitle: Overview`. Keep root SDK reference and leaf modules such as CLI as single pages. Do not duplicate Overview paths or use group `root` as a clickable title.

Set `interaction.drilldown: true` for Aspen's native first-page navigation. The whole pill, chevron and keyboard activation share one toggle:

- Closed/outside descendants: expand and navigate to Overview.
- Closed/inside descendants: expand and keep the page.
- Open: collapse and keep the page.

Child/Overview navigation must keep its group open. `expanded` only sets the default state. Do not store/reinsert sidebar HTML, synthesize clicks, reach into React, force visibility with CSS or maintain parallel navigation state. Report native limitations instead of masking them.

On Windows, stop preview before editing/regenerating pages, then run `npm run dev`. The pinned CLI watcher passes backslash filenames into page metadata; fresh scans normalize them. Compare actual href/pathname before blaming theme behavior for missing selection, ancestor expansion or eyebrows.

## Local work and publishing

From `docs-v2/`: `uv sync --locked`, `npm ci`, then `npm run dev` (generates before preview). `npm run api` regenerates after SDK edits; reload, or follow the Windows restart rule above. `npm run check` verifies without fixing stale output. Do not implicitly install dependencies during checks or add another task runner. Keep dependency/lock changes together.

Site logic stays here. Root Makefile has no site targets. Exclude tooling and instructions through `.mintignore`.

Preview CI generates and checks the checkout, then uploads a site artifact.
Production snapshots use `docs-release`; configure Mintlify to that branch
and `docs-v2/`. Workflow artifacts do not update the host.

Docs release requires verified successful main CI, durable Release intent and
distributions matching PyPI. Package source, supported API surface and Reference
navigation stay bound to that release. Docs-only corrections may use later main
guides, never an older guide source. Preserve provenance, fail closed on missing
or invalid evidence, reject rollback/conflicting snapshots, and make identical
reruns no-ops. Exclude install trees. Never expose unreleased API on production.

## Verification

Follow the user's verification scope; normally run `npm run check` for semantic generator tests, supported surface/navigation, freshness, determinism, MDX compilation, canonical links, Mintlify validation and broken links. Retain real rendering-failure tests, avoiding exact-prose snapshots.

Inspect generated constructors, methods, properties, models and aliases. For navigation/appearance changes, review desktop/narrow package folders, nested groups, anchors, long signatures, fences and missing pages. Prove the folder matrix with real clicks; inspect regeneration when changing preview workflow. Report local checks separately from CI, hosted search, deployment and prose acceptance.

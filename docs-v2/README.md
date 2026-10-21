# AgentConnect documentation website

This directory is the AgentConnect documentation site and Python API reference. Hosted publishing is not configured by the repository workflows.

## Local preview

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node.js 22 LTS or newer. From this directory:

```bash
uv sync --locked
npm ci
npm run dev
```

The preview command generates the Python reference from the local SDK before starting Mintlify. Open the URL it prints (normally http://localhost:3000). Stop it with Ctrl+C.

After editing Python source, run `npm run api` and reload the browser. Mintlify watches handwritten pages during preview.

On Windows, stop the preview before regenerating or editing pages, then restart
with `npm run dev`. The pinned Mintlify CLI's incremental watcher passes Windows
backslashes into page URLs, breaking native selection and folder matching. A
fresh launch generates the reference first and scans URLs correctly. Linux/macOS
previews do not need this restart workaround.

## Check changes

```bash
npm run check
```

This checks generation freshness and determinism, compiles reference pages, verifies links, and runs Mintlify validation. It does not rewrite stale reference files: run `npm run api` when needed.

Preview CI generates the reference from the pull-request tree, then runs the same checks with `--skip-stale` and uploads a downloadable site artifact. This artifact is not a hosted preview: Mintlify's Git integration reads committed files from its configured branch and directory, not workflow artifacts.

After a published GitHub Release, Docs release verifies the successful main CI run, durable release intent and distribution hashes against PyPI, extracts API from the package SHA, validates the site, and promotes `docs-v2/` to `docs-release`. Identical reruns are no-ops; conflicting same-version content and older releases fail. Docs retries use durable GitHub Release assets even after the original CI artifact expires. A `docs-only` dispatch may name a full guide-source SHA on main descended from the current guide source; provenance records it separately, and API extraction still uses the package SHA.

API pages in `api/`, `api-reference.mdx`, and `api-pages.json` are generated. Edit SDK docstrings rather than those files. Handwritten pages are grouped by topic; generator code and templates live in `scripts/`.

For hosted delivery, configure Mintlify to this repository's `docs-release` branch and `docs-v2/` directory. Search activation may require Mintlify login.

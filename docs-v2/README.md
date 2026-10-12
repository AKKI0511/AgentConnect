# AgentConnect documentation website

This directory contains the Mintlify website and Python API reference. The existing site in `../docs/` remains separate until migration.

## Local preview

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node.js 22 LTS or newer. From this directory:

```bash
uv sync --locked
npm ci
npm run dev
```

The preview command generates the Python reference from the local SDK before starting Mintlify. Open the URL it prints (normally http://localhost:3000). Stop it with Ctrl+C.

After editing Python source, run `npm run api` and reload the browser. Mintlify watches handwritten pages during preview.

## Check changes

```bash
npm run check
```

This checks generation freshness and determinism, compiles reference pages, verifies links, and runs Mintlify validation. It does not rewrite stale reference files: run `npm run api` when needed.

API pages in `api/`, `api-reference.mdx`, and `api-pages.json` are generated and committed alongside source changes. Edit SDK docstrings rather than those files. Handwritten pages are grouped by topic; generator code and templates live in `scripts/`. The handwritten content is still being reviewed for release.

Local preview does not configure deployment or hosted search. Search activation may require Mintlify login.

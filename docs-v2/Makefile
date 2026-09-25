# AgentConnect Mintlify docs (docs-v2) — run from docs-v2/ or via root `make docs-v2*`
.PHONY: sync api dev check validate links

UV ?= uv
NPM ?= npm

sync:
	$(UV) sync
	$(NPM) ci

api: sync
	$(UV) run python scripts/generate_api.py

dev: api
	$(NPM) run dev

check: sync
	$(UV) run python scripts/check.py

validate: sync
	$(NPM) run validate

links: sync
	$(NPM) run broken-links

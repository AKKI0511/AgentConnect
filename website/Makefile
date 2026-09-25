# AgentConnect Mintlify website — run from website/ or via root `make website*`
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

.PHONY: check format test docs docs-preview

check:
	uvx ruff@latest check agentconnect tests examples docs/generate_docs.py
	uvx ruff@latest format --check agentconnect tests examples docs/generate_docs.py
	uv lock --check

format:
	uvx ruff@latest format agentconnect tests examples docs/generate_docs.py

test:
	uv run --extra serve --extra cli --extra index pytest tests/ -q

docs:
	uv run --group docs --extra serve --extra cli python docs/generate_docs.py

docs-preview:
	uv run --group docs --extra serve --extra cli python docs/generate_docs.py --preview

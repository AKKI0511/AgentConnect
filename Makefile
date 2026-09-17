.PHONY: check format test perf docs docs-preview

check:
	uvx ruff@latest check agentconnect tests examples docs/generate_docs.py
	uvx ruff@latest format --check agentconnect tests examples docs/generate_docs.py
	uv lock --check
	uv lock --check --directory examples/quickstart
	uv lock --check --directory examples/recipes

format:
	uvx ruff@latest format agentconnect tests examples docs/generate_docs.py

test:
	uv run --extra serve --extra cli --extra index --extra openai --extra redis pytest tests/ -q

perf:
	uv run --extra serve --extra embeddings --extra redis python tests/m8/bench.py --require-neural --stress

docs:
	uv run --group docs --extra serve --extra cli python docs/generate_docs.py

docs-preview:
	uv run --group docs --extra serve --extra cli python docs/generate_docs.py --preview

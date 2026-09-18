.PHONY: check format test perf docs docs-preview

check:
	uvx ruff@latest check agentconnect tests examples benchmarks docs/generate_docs.py
	uvx ruff@latest format --check agentconnect tests examples benchmarks docs/generate_docs.py
	uv lock --check
	uv lock --check --directory examples/quickstart
	uv lock --check --directory examples/recipes

format:
	uvx ruff@latest format agentconnect tests examples benchmarks docs/generate_docs.py

test:
	uv run --extra serve --extra cli --extra index --extra openai --extra redis pytest tests/ -q

RESULTS := benchmarks/runtime/results
PERF := uv run --group benchmark --extra serve --extra embeddings --extra redis pytest -q --benchmark-warmup=off --benchmark-columns=min,median,max,mean,stddev,rounds

perf:
	$(PERF) benchmarks/runtime/test_phases.py --benchmark-json=$(RESULTS)/phases.json --junitxml=$(RESULTS)/phases.xml
	$(PERF) benchmarks/runtime/test_warm_find.py --benchmark-json=$(RESULTS)/warm.json --junitxml=$(RESULTS)/warm.xml
	$(PERF) benchmarks/runtime/test_overlap.py --benchmark-json=$(RESULTS)/overlap.json --junitxml=$(RESULTS)/overlap.xml
	$(PERF) benchmarks/runtime/test_neural.py --benchmark-json=$(RESULTS)/neural.json --junitxml=$(RESULTS)/neural.xml
	$(PERF) benchmarks/runtime/test_stress.py --benchmark-json=$(RESULTS)/stress.json --junitxml=$(RESULTS)/stress.xml

docs:
	uv run --group docs --extra serve --extra cli python docs/generate_docs.py

docs-preview:
	uv run --group docs --extra serve --extra cli python docs/generate_docs.py --preview

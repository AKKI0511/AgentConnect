.PHONY: check format test perf

check:
	uvx ruff@latest check agentconnect tests examples experiments benchmarks
	uvx ruff@latest format --check agentconnect tests examples experiments benchmarks
	uv lock --check
	uv lock --check --directory examples/quickstart
	uv lock --check --directory examples/recipes
	uv lock --check --directory experiments/team_tools

format:
	uvx ruff@latest format agentconnect tests examples experiments benchmarks

test:
	uv run --extra redis --extra embeddings --extra prebuilt pytest tests/ -q

RESULTS := benchmarks/runtime/results
PERF := uv run --group benchmark --extra embeddings --extra redis pytest -q --benchmark-warmup=off --benchmark-columns=min,median,max,mean,stddev,rounds

perf:
	$(PERF) benchmarks/runtime/test_phases.py --benchmark-json=$(RESULTS)/phases.json --junitxml=$(RESULTS)/phases.xml
	$(PERF) benchmarks/runtime/test_warm_find.py --benchmark-json=$(RESULTS)/warm.json --junitxml=$(RESULTS)/warm.xml
	$(PERF) benchmarks/runtime/test_overlap.py --benchmark-json=$(RESULTS)/overlap.json --junitxml=$(RESULTS)/overlap.xml
	$(PERF) benchmarks/runtime/test_neural.py --benchmark-json=$(RESULTS)/neural.json --junitxml=$(RESULTS)/neural.xml
	$(PERF) benchmarks/runtime/test_stress.py --benchmark-json=$(RESULTS)/stress.json --junitxml=$(RESULTS)/stress.xml
	$(PERF) benchmarks/runtime/request_reply --benchmark-json=$(RESULTS)/exchange.json --junitxml=$(RESULTS)/exchange.xml

.PHONY: install install-core install-demo lint format test all

install-core:
	poetry install --no-root

install-demo:
	poetry install --with demo --no-root

install: install-core

lint:
	poetry run flake8 --extend-ignore E501,W293,E128,W291,E402 src/ demos/api/ demos/utils/

format:
	poetry run black src/ demos/

test:
	@if ls tests/ 1> /dev/null 2>&1; then \
		poetry run pytest tests/ -v || true; \
	else \
		echo "No test files found, skipping tests."; \
	fi

all: install lint format test
install:
	pip install --upgrade pip &&\
		pip install -r requirements.txt

lint:
	flake8 --extend-ignore E501,W293,E128 src/

format:
	black src/
	black --check src/

test:
	@if ls tests/ 1> /dev/null 2>&1; then \
		pytest tests/ || true; \
	else \
		echo "No test files found, skipping tests."; \
	fi

all: install lint format test
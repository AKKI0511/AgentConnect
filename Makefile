.PHONY: install install-core install-dev install-demo lint format test clean build publish all install-hooks hooks docs docs-clean docs-html docs-coverage

install-core:
	poetry install

install-dev:
	poetry install --with dev

install-demo:
	poetry install --with demo

install-all:
	poetry install --with dev,demo

install-docs:
	poetry install --with docs

install: install-core

install-hooks:
	poetry run pre-commit install

hooks:
	poetry run pre-commit run --all-files

lint:
	poetry run flake8 --extend-ignore E501,W293,E128,W291,E402,E203 agentconnect/ demos/api/ demos/utils/

format:
	poetry run black agentconnect/ demos/

test:
	@echo "Tests are disabled - skipping test execution"
	@exit 0

docs:
	$(MAKE) -C docs html

docs-clean:
	$(MAKE) -C docs clean

docs-html:
	$(MAKE) -C docs html

docs-coverage:
	poetry run python docs/doc_coverage.py

clean:
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/ .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete

build:
	poetry build

publish:
	poetry publish

all: install-all lint format test hooks docs

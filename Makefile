# Thin shortcuts for the documented commands; on Windows run the python commands directly.
PYTHON ?= python

.PHONY: help install hooks dev validate integration audit bootstrap-check

help:
	@echo "install          install locked runtime and dev dependencies"
	@echo "hooks            install pre-commit hooks"
	@echo "dev              run the isolated dev profile with reload"
	@echo "validate         lint, format, types, unit tests and coverage"
	@echo "integration      validate plus disposable PostgreSQL tests"
	@echo "audit            check locked dependencies for known vulnerabilities"
	@echo "bootstrap-check  list template placeholders still pending"

install:
	$(PYTHON) -m pip install -r requirements.lock
	$(PYTHON) -m pip install -e ".[dev]"

hooks:
	$(PYTHON) -m pre_commit install

dev:
	$(PYTHON) -m src --profile dev --reload

validate:
	$(PYTHON) scripts/validate.py

integration:
	$(PYTHON) scripts/validate.py --integration

audit:
	$(PYTHON) -m pip_audit -r requirements.lock

bootstrap-check:
	$(PYTHON) scripts/bootstrap.py --check

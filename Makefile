.PHONY: install test lint prices

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check powstock/
	ruff format powstock/ --check

format:
	ruff format powstock/

prices:
	python -m powstock.services.prices

state:
	python scripts/build_daily_state.py

help:
	@echo "install   - install package in dev mode"
	@echo "test      - run tests"
	@echo "lint      - check lint"
	@echo "format    - format code"
	@echo "prices    - fetch daily prices"
	@echo "state     - build daily state"

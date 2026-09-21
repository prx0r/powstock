.PHONY: install test lint format doctor health run help

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check powstock/ layer1/ layer2/
	ruff format powstock/ layer1/ layer2/ --check

format:
	ruff format powstock/ layer1/ layer2/

doctor:
	python -m powstock.doctor

health:
	python -c "from layer1.health import check_all_health, print_health_report; print_health_report(check_all_health())"

run:
	python -c "from powstock.collectors.runner import run_all; run_all()"

layer1:
	@echo "Layer 1 — Data Garden (sources, collectors, manifests, health)"
	@echo "  make health    — check all source health"
	@echo "  make run       — run all collectors"

layer2:
	@echo "Layer 2 — Analysis (signals, experiments, models)"
	@echo "  No fish dependency. No powuk dependency."
	@echo "  Consumes Layer 1 data only."

help:
	@echo "install   — install package in dev mode"
	@echo "test      — run tests"
	@echo "lint      — check lint"
	@echo "format    — format code"
	@echo "doctor    — check source status (legacy)"
	@echo "health    — check Layer 1 source health with manifests"
	@echo "run       — run all collectors"
	@echo "layer1    — Layer 1 info"
	@echo "layer2    — Layer 2 info"

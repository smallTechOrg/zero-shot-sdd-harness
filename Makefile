PORT     := 8001
GOAL     := "What is the total revenue across all months?"
FOLLOWUP := "Which month had the highest revenue?"
DATA_FILE := scripts/fixtures/sample_data.csv

.PHONY: setup dev gate demo-gate analyze

setup:
	uv sync --extra dev
	uv run playwright install chromium

dev:
	uv run python -m agent

analyze:
	uv run python -m agent.analyze

gate: demo-gate

demo-gate:
	GOAL=$(GOAL) FOLLOWUP=$(FOLLOWUP) DATA_FILE=$(DATA_FILE) bash scripts/demo_gate.sh

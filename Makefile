.PHONY: dev backend frontend test lint migrate install

install:
	uv sync && cd frontend && npm install

dev:
	concurrently "make backend" "make frontend"

backend:
	uv run uvicorn src.data_analyst.api:app --host 0.0.0.0 --port 8001 --reload

frontend:
	cd frontend && npm run dev

test:
	uv run pytest tests/ -v && cd frontend && npm test -- --run

lint:
	uv run ruff check src/ tests/ && uv run black --check src/ tests/ && cd frontend && npm run lint

migrate:
	uv run alembic upgrade head

format:
	uv run ruff check --fix src/ tests/ && uv run black src/ tests/

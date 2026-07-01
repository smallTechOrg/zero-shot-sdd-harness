# syntax=docker/dockerfile:1

# ---- Stage 1: build the Next.js static export (frontend/out) ----
FROM node:20-slim AS frontend
WORKDIR /build
# Pin the exact pnpm the project builds with locally (workspace uses pnpm 10+ `allowBuilds`)
RUN npm install -g pnpm@11.9.0
# Copy the ENTIRE frontend (incl. pnpm-workspace.yaml) so the workspace + lockfile resolve.
COPY frontend/ ./frontend/
WORKDIR /build/frontend
RUN pnpm install --no-frozen-lockfile
# next.config: output "export", basePath "/app" -> produces /build/frontend/out
RUN pnpm build

# ---- Stage 2: python runtime ----
FROM python:3.12-slim AS runtime
RUN pip install --no-cache-dir uv
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    AGENT_LLM_PROVIDER=gemini

# Install runtime deps (no dev deps) from the lockfile
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

# Application code (tables are created on startup via init_db -> create_all)
COPY src/ ./src/

# Built frontend from stage 1 — backend serves this at /app when present
COPY --from=frontend /build/frontend/out ./frontend/out

# SQLite dir (ephemeral on Render — matches the app's session-only design)
RUN mkdir -p ./data

EXPOSE 8001
# Render injects $PORT; src/__main__.py reads it and binds 0.0.0.0.
CMD ["sh", "-c", "uv run python -m src"]

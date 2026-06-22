#!/usr/bin/env bash
# Resets the repo to a clean boilerplate state for a new demo/test run.
# Wipes all project-specific output. Safe to run between workshop iterations.
set -euo pipefail

echo "Resetting to clean boilerplate state..."

# Project spec files (keep templates, wipe filled-in content)
git checkout HEAD -- spec/ 2>/dev/null || true

# Generated source code and tests
rm -rf src/ tests/ alembic/ pyproject.toml uv.lock .venv/

# Runtime output
rm -rf data/ images/ reports/sessions/
mkdir -p data images reports/sessions

# Git state
git checkout HEAD -- .env.example 2>/dev/null || true

echo ""
echo "Done. Repo is back to boilerplate state."
echo "Next: create a new branch and run /zero-shot-build with your idea."
echo ""
echo "  git checkout -b feat/my-new-agent"
echo "  claude"
echo "  /zero-shot-build [your idea]"

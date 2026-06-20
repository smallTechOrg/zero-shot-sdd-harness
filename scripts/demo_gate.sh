#!/usr/bin/env bash
# demo_gate.sh — gate checks 1–8
set -euo pipefail

PORT=8001
BASE_URL="http://localhost:${PORT}"
GOAL="${GOAL:-What is the average salary?}"
FOLLOWUP="${FOLLOWUP:-What is the maximum age in the dataset?}"
DATA_FILE="${DATA_FILE:-}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
pass() { echo -e "${GREEN}PASS${NC} $1"; }
fail() { echo -e "${RED}FAIL${NC} $1"; exit 1; }
info() { echo -e "${YELLOW}INFO${NC} $1"; }

# ── check 0: README exists ────────────────────────────────────────────────────
[ -f README.md ] && pass "0: README.md present" || fail "0: README.md missing"

# ── check 1: eval_lint passes ─────────────────────────────────────────────────
uv run python -m agent.eval_lint && pass "1: eval_lint clean" || fail "1: eval_lint found issues"

# ── check 2: pytest (no e2e) passes ───────────────────────────────────────────
uv run pytest tests/ --ignore=tests/e2e -q && pass "2: unit tests green" || fail "2: unit tests failed"

# ── check 3: server boots ─────────────────────────────────────────────────────
# Kill any stale server on the port
lsof -ti :${PORT} | xargs kill -9 2>/dev/null || true
uv run python -m agent &
SERVER_PID=$!
trap "kill ${SERVER_PID} 2>/dev/null; exit" INT TERM EXIT

info "3: waiting for server on :${PORT} …"
for i in $(seq 1 30); do
    curl -sf "${BASE_URL}/health" >/dev/null 2>&1 && break || sleep 1
done
curl -sf "${BASE_URL}/health" >/dev/null 2>&1 \
    && pass "3: server booted" || fail "3: server did not boot in 30 s"

# ── check 4: health endpoint ──────────────────────────────────────────────────
HEALTH=$(curl -sf "${BASE_URL}/health")
echo "${HEALTH}" | grep -q '"status"' && pass "4: /health returns JSON" \
    || fail "4: /health body unexpected: ${HEALTH}"

# ── check 5: Q1 — upload + goal ───────────────────────────────────────────────
if [ -n "${DATA_FILE}" ]; then
    [ -f "${DATA_FILE}" ] || fail "5: DATA_FILE=${DATA_FILE} not found"
    DATA=$(cat "${DATA_FILE}")
else
    DATA=""
fi

Q1_BODY=$(jq -n \
    --arg goal "${GOAL}" \
    --arg data "${DATA}" \
    '{goal: $goal, data: $data}')

RESP1=$(curl -sf -X POST "${BASE_URL}/runs" \
    -H 'Content-Type: application/json' \
    -d "${Q1_BODY}")

echo "${RESP1}" | jq -e '.data.answer' >/dev/null 2>&1 \
    && pass "5: Q1 returned an answer" || fail "5: Q1 response missing answer: ${RESP1}"

SESSION_ID=$(echo "${RESP1}" | jq -r '.data.session_id // empty')
RUN_ID=$(echo "${RESP1}" | jq -r '.data.run_id')
ANSWER1=$(echo "${RESP1}" | jq -r '.data.answer')
info "5: Q1 answer (first 120 chars): ${ANSWER1:0:120}"

# ── check 6: Q2 — follow-up, no re-upload ─────────────────────────────────────
Q2_BODY=$(jq -n \
    --arg goal "${FOLLOWUP}" \
    --arg sid "${SESSION_ID}" \
    '{goal: $goal, session_id: $sid}')

RESP2=$(curl -sf -X POST "${BASE_URL}/runs" \
    -H 'Content-Type: application/json' \
    -d "${Q2_BODY}")

echo "${RESP2}" | jq -e '.data.answer' >/dev/null 2>&1 \
    && pass "6: Q2 answered without re-upload" || fail "6: Q2 response missing answer: ${RESP2}"

ANSWER2=$(echo "${RESP2}" | jq -r '.data.answer')
info "6: Q2 answer (first 120 chars): ${ANSWER2:0:120}"

# ── check 7: judge-stable outcome eval ───────────────────────────────────────
uv run python -m agent.gate_eval \
    --run-id "${RUN_ID}" \
    --goal "${GOAL}" \
    && pass "7: outcome eval passed (judge-stable)" \
    || fail "7: outcome eval failed — check CRITERION in agent/gate_eval.py"

# ── check 8: UI / Playwright (if playwright + browser installed) ─────────────
if python -c "import playwright" 2>/dev/null; then
    # Verify browser binary is present; install if missing
    if ! uv run python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    import pathlib; pathlib.Path(p.chromium.executable_path).stat()
" 2>/dev/null; then
        info "8: installing Playwright browsers …"
        uv run playwright install chromium 2>&1 | grep -v "^$" || true
    fi
    # -o addopts="" clears the default `--ignore=tests/e2e` so e2e actually runs here.
    uv run pytest tests/e2e/ -o addopts="" -q \
        && pass "8: Playwright UI journey green" \
        || fail "8: Playwright UI journey failed"
else
    info "8: playwright not installed — skipping UI check (run 'make setup' to install)"
fi

echo ""
echo -e "${GREEN}All gate checks passed.${NC}"

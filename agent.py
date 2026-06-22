#!/usr/bin/env python3
"""
agent.py — local setup checker and run helper

Usage:
  python agent.py           # check everything
  python agent.py --run     # check + alembic + build frontend + start server
  python agent.py --reset   # restore spec templates and wipe runtime data
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ── colours ──────────────────────────────────────────────────────────────────
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg: str)   -> None: print(f"  {GREEN}✓{RESET}  {msg}")
def fail(msg: str) -> None: print(f"  {RED}✗{RESET}  {msg}"); _failures.append(msg)
def warn(msg: str) -> None: print(f"  {YELLOW}!{RESET}  {msg}")
def info(msg: str) -> None: print(f"  {CYAN}→{RESET}  {msg}")
def header(msg: str) -> None: print(f"\n{BOLD}{msg}{RESET}")

_failures: list[str] = []


# ── helpers ───────────────────────────────────────────────────────────────────
def run(cmd: list[str], *, cwd: Path = ROOT, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=capture, text=True)

def which(name: str) -> bool:
    return shutil.which(name) is not None

def cmd_version(cmd: list[str]) -> str | None:
    r = run(cmd)
    return r.stdout.strip().splitlines()[0] if r.returncode == 0 else None

def env_key_set(path: Path, key: str) -> bool:
    if not path.exists():
        return False
    for line in path.read_text().splitlines():
        if line.startswith(f"{key}="):
            val = line.split("=", 1)[1].strip()
            return bool(val) and val != "#"
    return False


# ── checks ────────────────────────────────────────────────────────────────────
def check_tools() -> None:
    header("Tools")

    # git
    v = cmd_version(["git", "--version"])
    if v: ok(v)
    else: fail("git not found — install git")

    # python 3.11+
    vi = sys.version_info
    if vi >= (3, 11):
        ok(f"Python {vi.major}.{vi.minor}.{vi.micro}")
    else:
        fail(f"Python {vi.major}.{vi.minor} found — need 3.11+")

    # uv
    v = cmd_version(["uv", "--version"])
    if v: ok(v)
    else: fail("uv not found — install: curl -LsSf https://astral.sh/uv/install.sh | sh")

    # claude
    v = cmd_version(["claude", "--version"])
    if v: ok(v)
    else: fail("claude CLI not found — install Claude Code")

    # node + pnpm (optional — needed only for frontend build)
    if which("node"):
        v = cmd_version(["node", "--version"])
        ok(f"node {v}")
        v = cmd_version(["pnpm", "--version"])
        if v: ok(f"pnpm {v}")
        else: warn("pnpm not found — needed for frontend build: npm install -g pnpm")
    else:
        warn("node not found — needed for frontend build only; API works without it")


def check_env() -> None:
    header("Environment (.env)")

    env = ROOT / ".env"
    if not env.exists():
        fail(".env not found — run: cp .env.example .env  and fill in your API key")
        return
    ok(".env exists")

    providers = {
        "ANTHROPIC_API_KEY": "Anthropic",
        "GEMINI_API_KEY":    "Gemini",
        "OPENROUTER_API_KEY":"OpenRouter",
    }
    found = [name for key, name in providers.items() if env_key_set(env, key)]
    if found:
        ok(f"API key set: {', '.join(found)}")
    else:
        fail(f"No provider key found in .env — set one of: {', '.join(providers)}")


def check_python_env() -> None:
    header("Python environment")

    venv = ROOT / ".venv"
    if not venv.exists():
        fail(".venv not found — run: uv sync")
        return
    ok(".venv present")

    r = run(["uv", "run", "python", "-c", "import fastapi, sqlalchemy, langgraph, anthropic"])
    if r.returncode == 0:
        ok("core packages importable (fastapi, sqlalchemy, langgraph, anthropic)")
    else:
        fail("missing packages — run: uv sync")


def check_db() -> None:
    header("Database")

    data = ROOT / "data"
    data.mkdir(exist_ok=True)
    ok("data/ directory ready")

    r = run(["uv", "run", "alembic", "current"])
    if r.returncode == 0 and r.stdout.strip():
        ok(f"alembic migration applied: {r.stdout.strip().splitlines()[0]}")
    elif r.returncode == 0:
        warn("no migration applied yet — run: uv run alembic upgrade head")
    else:
        warn("alembic check failed — run: uv run alembic upgrade head")


def check_tests() -> None:
    header("Unit tests")

    r = run(["uv", "run", "pytest", "tests/unit/", "-q", "--tb=short"])
    if r.returncode == 0:
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        ok(lines[-1] if lines else "tests passed")
    else:
        fail("unit tests failed:\n" + r.stdout[-800:])


def check_frontend() -> None:
    header("Frontend")

    fe = ROOT / "frontend"
    if not fe.exists():
        warn("frontend/ not found — skipping")
        return

    nm = fe / "node_modules"
    if not nm.exists():
        warn("node_modules missing — run: cd frontend && pnpm install")
        return
    ok("node_modules present")

    lock = fe / "pnpm-lock.yaml"
    out = fe / "out"
    if out.exists():
        ok("frontend/out/ built — server will serve UI at /app/")
    else:
        warn("frontend not built — run: cd frontend && pnpm build  (or use --run)")


# ── actions ───────────────────────────────────────────────────────────────────
def do_run() -> None:
    header("Build & run")

    # alembic
    info("applying migrations...")
    r = run(["uv", "run", "alembic", "upgrade", "head"], capture=False)
    if r.returncode != 0:
        fail("alembic upgrade head failed")
        return

    r = run(["uv", "run", "alembic", "current"])
    rev = r.stdout.strip().splitlines()[0] if r.stdout.strip() else "(unknown)"
    ok(f"migrations applied: {rev}")

    # frontend
    fe = ROOT / "frontend"
    if not which("pnpm"):
        warn("pnpm not found — skipping frontend build")
    elif fe.exists():
        info("building frontend...")
        r = run(["pnpm", "build"], cwd=fe, capture=False)
        if r.returncode == 0:
            ok("frontend built → frontend/out/")
        else:
            fail("frontend build failed")

    if not _failures:
        print(f"\n{GREEN}{BOLD}Starting server…{RESET}")
        print(f"  {CYAN}http://localhost:8001{RESET}       (API)")
        fe_out = ROOT / "frontend" / "out"
        if fe_out.exists():
            print(f"  {CYAN}http://localhost:8001/app/{RESET}  (UI)\n")
        else:
            print()
        os.execvp("uv", ["uv", "run", "python", "-m", "agent"])


def do_reset() -> None:
    header("Reset to baseline")

    # restore spec templates from git
    info("restoring spec/ templates...")
    r = run(["git", "checkout", "HEAD", "--", "spec/"])
    if r.returncode == 0:
        ok("spec/ restored to boilerplate templates")
    else:
        warn("git checkout spec/ failed — spec/ unchanged")

    # wipe runtime data only
    data = ROOT / "data"
    if data.exists():
        shutil.rmtree(data)
    data.mkdir()
    (data / "uploads").mkdir(exist_ok=True)
    ok("data/ cleared")

    print(f"\n{GREEN}Baseline restored.{RESET}")
    print("  src/, frontend/, tests/ are untouched — they are the framework baseline.")
    print("  Next: branch and build.")
    print(f"\n    {CYAN}git checkout -b feat/my-agent && claude{RESET}")
    print(f"    {CYAN}/zero-shot-build [your idea]{RESET}\n")


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="agent.py — setup checker and build helper")
    parser.add_argument("--run", action="store_true", help="run alembic + build frontend after checks")
    parser.add_argument("--reset", action="store_true", help="restore spec templates and clear runtime data")
    args = parser.parse_args()

    if args.reset:
        do_reset()
        return

    print(f"\n{BOLD}=== Local Setup Check ==={RESET}")

    check_tools()
    check_env()
    check_python_env()
    check_db()
    check_tests()
    check_frontend()

    print()
    if _failures:
        print(f"{RED}{BOLD}{len(_failures)} issue(s) found — fix before starting.{RESET}")
        for f in _failures:
            print(f"  {RED}✗{RESET}  {f}")
        if not args.build:
            sys.exit(1)
    else:
        print(f"{GREEN}{BOLD}All checks passed.{RESET}")

    if args.build:
        do_run()
    else:
        print(f"\n  Run {CYAN}python agent.py --run{RESET} to apply migrations and build the frontend.")
        print(f"  Run {CYAN}python agent.py --reset{RESET} to restore spec templates for a fresh build.\n")


if __name__ == "__main__":
    main()

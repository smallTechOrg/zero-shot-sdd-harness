#!/usr/bin/env bash
# Stop-hook nudge: if source code changed but no spec/ doc did, suggest re-projecting. Quiet otherwise;
# never blocks (always exits 0). Wired in .claude/settings.json. Works for a global spec/ or a per-app */spec/.
set -uo pipefail
root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
changed=$(git -C "$root" ls-files -m -o --exclude-standard 2>/dev/null) || exit 0
code=$(printf '%s\n' "$changed" | grep -Ev '(^|/)spec/' | grep -Ev '^\.claude/' \
       | grep -E '\.(py|ts|tsx|js|jsx|go|rs|java|rb)$' || true)
spec=$(printf '%s\n' "$changed" | grep -E '(^|/)spec/' || true)
if [ -n "$code" ] && [ -z "$spec" ]; then
  printf '↻ spec may be stale: code changed but no spec/ doc was re-projected — run /sync.\n'
fi
exit 0

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, data_dir: Path) -> None:
        self._path = Path(data_dir) / "audit.jsonl"

    def log(
        self,
        event_type: str,
        session_id: str,
        payload: dict[str, Any],
        token_usage: dict | None = None,
    ) -> None:
        """Append one JSONL line. Never raises — errors go to stderr."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            entry: dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "session_id": session_id,
                "payload": payload,
            }
            if token_usage is not None:
                entry["token_usage"] = token_usage
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as exc:
            print(f"AuditLogger error: {exc}", file=sys.stderr)

    def read_recent(
        self,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Read recent entries in reverse-chronological order."""
        if not self._path.exists():
            return []
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except Exception:
            return []

        entries = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if session_id is not None and entry.get("session_id") != session_id:
                continue
            entries.append(entry)
            if len(entries) >= limit:
                break
        return entries

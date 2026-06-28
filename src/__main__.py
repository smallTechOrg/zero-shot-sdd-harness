import sys
from pathlib import Path

# Ensure the flat `src/` package root is importable so uvicorn can resolve
# the bare "api:app" target (the test path uses pythonpath=["src"]; the run
# path must match it).
_SRC = str(Path(__file__).resolve().parent)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=False)

import sys
from pathlib import Path

# Ensure the flat-package root (`src/`) is importable so `api:app` resolves the
# same way it does under pytest (pythonpath=["src"]). Run path == test path.
_SRC = str(Path(__file__).resolve().parent)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8001, reload=False)

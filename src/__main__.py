import os
import sys
from pathlib import Path

import uvicorn

# The codebase uses top-level absolute imports (e.g. `from api import ...`),
# which require src/ itself to be on sys.path. `python -m src` leaves the repo
# root on sys.path, so ensure the directory containing this file (src/) is too.
_SRC = str(Path(__file__).resolve().parent)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8001)),
        reload=False,
    )

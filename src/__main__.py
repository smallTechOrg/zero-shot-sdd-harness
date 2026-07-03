import os
import sys

import uvicorn

# Make src/ (this file's own directory) importable so bare imports like
# `from api import ...` resolve when running `uv run python -m src`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8001")),
        reload=False,
    )

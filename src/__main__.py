import os
import sys

import uvicorn

# Ensure the flat `src/` package root is importable when launched as `python -m src`.
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)

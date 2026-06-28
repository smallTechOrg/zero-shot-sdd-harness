import sys
from pathlib import Path

import uvicorn

# Internal modules use absolute imports rooted at the `src/` package dir
# (e.g. `from api import ask`, `from db.session import init_db`). Under pytest
# these resolve via `pythonpath = ["src"]`, but on the real `python -m src`
# boot from the repo root `src/` is not on sys.path. Add it so both the app
# import below and the app's own internal imports resolve identically.
_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from api import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)

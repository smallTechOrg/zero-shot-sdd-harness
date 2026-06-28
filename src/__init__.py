import sys as _sys
from pathlib import Path as _Path

# The intra-package modules import each other by bare name (e.g. ``from graph...``
# import ``from db...``). Ensure this package's own directory is on sys.path so
# those bare imports resolve whether the app is reached via ``src.<mod>`` (the
# editable install adds the repo root), via ``python -m src`` (CWD = repo root),
# or via pytest (pythonpath=["src"]). Idempotent.
_HERE = str(_Path(__file__).resolve().parent)
if _HERE not in _sys.path:
    _sys.path.insert(0, _HERE)

__version__ = "0.1.0"

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the workspace `src/` directory is on sys.path so imports like `libs.*`
# (used throughout the application code) work when running pytest from repo root.
_SRC_DIR = Path(__file__).resolve().parents[1]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

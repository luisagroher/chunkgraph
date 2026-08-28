"""Shared pytest configuration.

Adds the project's `src/` directory to sys.path so tests can import the
`parser` package without installing it (the project is not packaged for
distribution; see environment.yaml).
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

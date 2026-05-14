"""Pytest config: ensure repo root is importable and skip slow tests by default.

Slow tests (the eval-gated ones under tests/eval/) hit Pinecone + Groq and take
real wall-clock time. They run only when explicitly selected:

    pytest -m slow tests/eval/
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

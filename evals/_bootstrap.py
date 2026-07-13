"""
Shared bootstrap for the eval harness.

Import this FIRST in every eval script:

    import _bootstrap  # noqa: F401

It puts the backend package on sys.path and loads backend/.env into the
process environment, so the eval scripts can `from retrieval import ...`
and `from config import config` regardless of the current working directory.
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
EVALS = Path(__file__).resolve().parent

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Load backend/.env into os.environ so pydantic-settings picks up API keys
# even when the script is launched from the repo root.
try:
    from dotenv import load_dotenv

    load_dotenv(BACKEND / ".env")
except ImportError:  # python-dotenv not installed — rely on ambient env
    pass

os.environ.setdefault("PYTHONUNBUFFERED", "1")

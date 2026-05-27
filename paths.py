"""Single source of truth for project paths and environment variables.

Import this module before any ML model imports to ensure MODEL_CACHE_DIR
is set correctly and consistently.
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
MODELS_DIR = PROJECT_ROOT / "models"

# Must be set before surya/marker imports
os.environ.setdefault("MODEL_CACHE_DIR", str(MODELS_DIR))

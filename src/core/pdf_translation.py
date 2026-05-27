"""PDF → Markdown parsing and translation.

This module re-exports from the focused submodules for backward compatibility.
Import from the specific submodules directly for new code:
    - src.core.engine          — TranslationEngine, profile CRUD
    - src.core.document_parser — PDF/DOCX parsing
    - src.core.translator      — translation, bilingual merge, markdown utils
"""

from src.core.engine import *  # noqa: F401,F403
from src.core.document_parser import *  # noqa: F401,F403
from src.core.translator import *  # noqa: F401,F403

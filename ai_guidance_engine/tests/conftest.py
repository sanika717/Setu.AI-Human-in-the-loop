import sys
from pathlib import Path

# Ensure the repository root is available so ai_guidance_engine can be imported during tests.
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

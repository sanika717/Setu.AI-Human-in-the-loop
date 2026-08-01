"""Backward-compatible alias for the renamed `system_orchestrator/app`.

As of Phase B, the primary backend was renamed to the System Orchestrator
(folder: `system_orchestrator/`) to match the Sahaay.AI module vocabulary.
This package is a thin alias that redirects every import of `app` made from
inside `backend/` (and its submodules, e.g. `app.main`) to the real
`system_orchestrator/app` package, so the old run command still works
unchanged when invoked from this folder:

    cd backend && uvicorn app.main:app --reload --port 8000

New code should run `cd system_orchestrator && uvicorn app.main:app` instead.
This alias may be removed once nothing in the project references the old
`backend/` folder.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import system_orchestrator.app as _target  # noqa: E402

sys.modules[__name__] = _target

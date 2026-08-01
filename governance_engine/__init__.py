"""Backward-compatible alias for the renamed `trust_governance_engine`.

As of Phase B, the Governance Engine was renamed to the Trust & Governance
Engine (folder: `trust_governance_engine/`) to match the Sahaay.AI module
vocabulary. This package is a thin alias that redirects every import of
`governance_engine` (and its submodules) to the real package, so any
existing code, scripts, or deployment configs that still reference the old
name keep working unchanged, e.g.:

    import governance_engine
    from governance_engine.app import app
    uvicorn governance_engine.app:app --port 8003

New code should import `trust_governance_engine` directly. This alias may
be removed once nothing in the project references the old name.
"""
import sys

import trust_governance_engine as _target

sys.modules[__name__] = _target

"""Backward-compatible alias for the renamed `input_validation_security_engine`.

As of Phase B, the Document Validation Engine was renamed to the
Input Validation & Security Engine (folder: `input_validation_security_engine/`)
to match the Sahaay.AI module vocabulary. This package is a thin alias that
redirects every import of `document_validation_engine` (and its submodules)
to the real package, so any existing code, scripts, or deployment configs
that still reference the old name keep working unchanged, e.g.:

    import document_validation_engine
    from document_validation_engine.app import app
    uvicorn document_validation_engine.app:app --port 8001

New code should import `input_validation_security_engine` directly. This
alias may be removed once nothing in the project references the old name.
"""
import sys

import input_validation_security_engine as _target

sys.modules[__name__] = _target

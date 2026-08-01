"""Backward-compatible alias for the renamed `ai_guidance_engine`.

As of Phase B, the AI Extraction Engine was renamed to the AI Guidance
Engine (folder: `ai_guidance_engine/`) to match the Sahaay.AI module
vocabulary. This package is a thin alias that redirects every import of
`ai_extraction_engine` (and its submodules) to the real package, so any
existing code, scripts, or deployment configs that still reference the old
name keep working unchanged, e.g.:

    import ai_extraction_engine
    from ai_extraction_engine.app import app
    uvicorn ai_extraction_engine.app:app --port 8002

New code should import `ai_guidance_engine` directly. This alias may be
removed once nothing in the project references the old name.
"""
import sys

import ai_guidance_engine as _target

sys.modules[__name__] = _target

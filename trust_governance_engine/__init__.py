"""Trust & Governance Engine package.

Phase 4 of Sahaay.AI: an independent microservice that lets a human
caseworker approve, reject, or edit fields produced by the AI Guidance
Engine (Phase 2), gates final submission behind OTP verification, records
every decision to an immutable hash-chained audit log, and generates
CSV/JSON/PDF decision reports. It keeps its own database and talks to the
rest of the system only through its REST API.
"""

__all__ = ["app"]

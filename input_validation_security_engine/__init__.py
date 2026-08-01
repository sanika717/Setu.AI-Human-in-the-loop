"""Input Validation & Security Engine - independent microservice for Sahaay.AI.

Validates applicant-submitted documents (type, metadata, OCR text quality,
required-document completeness, and optional eligibility pre-checks) before
they are handed to the AI Guidance Engine or the Trust & Governance Engine.
This module is intentionally decoupled from those modules and communicates
only through its REST API and Pydantic models.
"""

"""Domain catalog for the Input Validation & Security Engine.

Document type codes are kept as lowercase snake_case strings so they line up
1:1 with the `type` field already used by `ai_guidance_engine` (see
`ai_guidance_engine/sample_data/sample_request.json`, which uses
"aadhaar" and "income_certificate").

As of Phase B this module only defines the generic document-type catalog
(what a document IS - "aadhaar", "pan_card", etc). It intentionally no
longer knows anything about which documents a given service requires, what
age gates apply, or any other service-specific rule - that used to be
pension-only logic hardcoded here (PensionType, BASE_REQUIRED_DOCUMENTS,
ADDITIONAL_REQUIRED_DOCUMENTS, MINIMUM_AGE_REQUIREMENTS). All of that is now
config-driven data owned by the Official Service Registry
(`official_service_registry/data/services.json`) and fetched over HTTP via
`services/registry_client.py`, so this engine works unmodified for ANY
service (Aadhaar update, SBI KYC, Passport, PAN, Pension, LIC, ...).
"""

from enum import Enum


class DocumentType(str, Enum):
    AADHAAR = "aadhaar"
    PAN_CARD = "pan_card"
    INCOME_CERTIFICATE = "income_certificate"
    AGE_PROOF = "age_proof"
    ADDRESS_PROOF = "address_proof"
    BANK_PASSBOOK = "bank_passbook"
    PASSPORT_PHOTO = "passport_photo"
    DISABILITY_CERTIFICATE = "disability_certificate"
    DEATH_CERTIFICATE = "death_certificate"
    LIFE_CERTIFICATE = "life_certificate"
    POLICY_DOCUMENT = "policy_document"


SUPPORTED_DOCUMENT_TYPES: frozenset[str] = frozenset(item.value for item in DocumentType)

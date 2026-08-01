from typing import Any

from ..models.schemas import (
    EligibilityCheckResponse,
    MissingDocumentsResponse,
    RedirectInfoResponse,
    ServiceDefinition,
    WorkflowStepsResponse,
)
from .eligibility_engine import EligibilityEngine
from .repository import ServiceRepository


class WorkflowEngine:
    """Orchestrates the repository + eligibility engine into the responses
    the rest of Sahaay.AI (Input Validation & Security Engine, System
    Orchestrator, AI Guidance Engine) consumes over HTTP.

    Adding a brand-new government/banking service to Sahaay.AI never touches
    this class - it only ever needs a new entry in services.json. This is
    what makes the platform config-driven: User Intent -> Official Service
    Detection (this engine) -> Official Website Verification -> Redirect ->
    AI Step-by-Step Guidance, for ANY service.
    """

    def __init__(self, repository: ServiceRepository | None = None, eligibility_engine: EligibilityEngine | None = None) -> None:
        self.repository = repository or ServiceRepository()
        self.eligibility_engine = eligibility_engine or EligibilityEngine()

    def list_services(self) -> list[ServiceDefinition]:
        return self.repository.list_services()

    def get_service(self, service_id: str) -> ServiceDefinition:
        return self.repository.get_service(service_id)

    def missing_documents(self, service_id: str, submitted_document_types: list[str]) -> MissingDocumentsResponse:
        service = self.repository.get_service(service_id)
        submitted = {doc.strip().lower() for doc in submitted_document_types}
        required = service.required_documents
        missing = [doc for doc in required if doc not in submitted]
        return MissingDocumentsResponse(
            service_id=service_id,
            required_documents=required,
            missing_documents=missing,
        )

    def check_eligibility(self, service_id: str, applicant_context: dict[str, Any]) -> EligibilityCheckResponse:
        service = self.repository.get_service(service_id)
        is_eligible, rule_results = self.eligibility_engine.evaluate(service.eligibility_rules, applicant_context)

        notes: list[str] = []
        if not service.eligibility_rules:
            notes.append("No eligibility rules configured for this service.")
        elif is_eligible is None:
            notes.append("One or more eligibility fields were missing; eligibility could not be fully evaluated.")
        elif not is_eligible:
            notes.append("Applicant does not meet one or more eligibility rules for this service.")

        return EligibilityCheckResponse(
            service_id=service_id,
            is_eligible=is_eligible,
            rule_results=rule_results,
            notes=notes,
        )

    def redirect_info(self, service_id: str) -> RedirectInfoResponse:
        service = self.repository.get_service(service_id)
        return RedirectInfoResponse(
            service_id=service.service_id,
            service_name=service.service_name,
            official_url=service.official_url,
            allowed_domains=service.allowed_domains,
        )

    def workflow_steps(self, service_id: str) -> WorkflowStepsResponse:
        service = self.repository.get_service(service_id)
        return WorkflowStepsResponse(service_id=service_id, workflow_steps=service.workflow_steps)

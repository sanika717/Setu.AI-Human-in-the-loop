from typing import Any

from ..models.response_models import EligibilityPreCheck, EligibilityRuleResult
from .registry_client import RegistryClient


class EligibilityPreValidationService:
    """Runs lightweight, non-authoritative eligibility pre-checks.

    This exists to surface obvious disqualifiers (e.g. an Old Age Pension
    applicant below the minimum age) as early as possible. It never makes a
    final eligibility decision - that responsibility belongs to the Trust &
    Governance Engine. Eligibility rules themselves are generic, data-driven
    config owned by the Official Service Registry
    (`official_service_registry/services/eligibility_engine.py`), so this
    service never branches on a specific service's criteria.
    """

    def __init__(self, registry_client: RegistryClient | None = None) -> None:
        self.registry_client = registry_client or RegistryClient()

    def check(self, service_id: str, applicant_context: dict[str, Any]) -> EligibilityPreCheck | None:
        result = self.registry_client.check_eligibility(service_id, applicant_context)
        if result is None:
            return None

        rule_results = [
            EligibilityRuleResult(
                field=item.get("field", ""),
                operator=item.get("operator", ""),
                passed=item.get("passed"),
                message=item.get("message", ""),
            )
            for item in result.get("rule_results", [])
        ]

        return EligibilityPreCheck(
            service_id=service_id,
            is_eligible=result.get("is_eligible"),
            rule_results=rule_results,
            notes=result.get("notes", []),
        )

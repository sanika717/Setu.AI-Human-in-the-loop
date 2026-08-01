from ..services.registry_client import RegistryClient
from ..services.validation_orchestrator import ValidationOrchestrator


def get_validation_orchestrator() -> ValidationOrchestrator:
    return ValidationOrchestrator()


def get_registry_client() -> RegistryClient:
    return RegistryClient()

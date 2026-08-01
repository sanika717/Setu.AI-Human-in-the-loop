from .registry_client import RegistryClient


class RequiredDocumentService:
    """Checks whether all documents required for a service were submitted.

    Required-document lists are no longer hardcoded here - they are owned
    by the Official Service Registry (`official_service_registry/data/services.json`)
    and fetched over HTTP, so this service works unmodified for ANY
    registered service.
    """

    def __init__(self, registry_client: RegistryClient | None = None) -> None:
        self.registry_client = registry_client or RegistryClient()

    def missing_documents(self, service_id: str, submitted_types: set[str]) -> list[str]:
        missing = self.registry_client.missing_documents(service_id, sorted(submitted_types))
        return sorted(missing)

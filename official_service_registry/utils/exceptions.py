class RegistryError(Exception):
    """Base exception for Official Service Registry failures."""


class ServiceNotFoundError(RegistryError):
    """Raised when a `service_id` does not exist in the registry."""


class RegistryConfigError(RegistryError):
    """Raised when the underlying services.json fails to load or validate."""

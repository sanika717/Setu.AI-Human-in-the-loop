import json
import threading

from ..config import settings
from ..models.schemas import ServiceDefinition
from ..utils.exceptions import RegistryConfigError, ServiceNotFoundError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ServiceRepository:
    """Loads the canonical `services.json` catalog and serves it from memory.

    This is the ONLY place that reads the config file. Every other component
    (eligibility engine, workflow engine, API routes) goes through this
    repository, so adding/editing a service is purely a data change to
    `services.json` (or whatever file SERVICES_CONFIG_PATH points at) -
    never a code change.
    """

    def __init__(self, config_path: str | None = None) -> None:
        self._config_path = config_path or settings.services_config_path
        self._lock = threading.Lock()
        self._services: dict[str, ServiceDefinition] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self._config_path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise RegistryConfigError(f"Unable to load services config from '{self._config_path}': {exc}") from exc

        services: dict[str, ServiceDefinition] = {}
        for entry in raw.get("services", []):
            definition = ServiceDefinition(**entry)
            services[definition.service_id] = definition

        with self._lock:
            self._services = services
        logger.info("Loaded %d service definitions from %s", len(services), self._config_path)

    def reload(self) -> None:
        """Re-read the config file from disk. Useful after an out-of-band edit."""
        self._load()

    def list_services(self) -> list[ServiceDefinition]:
        with self._lock:
            return list(self._services.values())

    def get_service(self, service_id: str) -> ServiceDefinition:
        with self._lock:
            service = self._services.get(service_id)
        if service is None:
            raise ServiceNotFoundError(f"Service '{service_id}' is not registered.")
        return service

    def exists(self, service_id: str) -> bool:
        with self._lock:
            return service_id in self._services

from functools import lru_cache

from ..services.eligibility_engine import EligibilityEngine
from ..services.repository import ServiceRepository
from ..services.workflow_engine import WorkflowEngine


@lru_cache()
def get_repository() -> ServiceRepository:
    # Cached so the services.json file is parsed once per process, not once
    # per request - reload() can still be called explicitly (e.g. via the
    # /admin/reload endpoint) to pick up out-of-band edits.
    return ServiceRepository()


def get_workflow_engine() -> WorkflowEngine:
    return WorkflowEngine(repository=get_repository(), eligibility_engine=EligibilityEngine())

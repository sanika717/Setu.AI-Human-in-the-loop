class IntentServiceError(Exception):
    """Base exception for the Intent Service."""


class ClassifierError(IntentServiceError):
    """Raised when an IntentClassifier implementation fails to produce a result."""


class UnsupportedClassifierError(IntentServiceError):
    """Raised when config.settings.classifier_name doesn't match a registered classifier."""


class RegistryUnavailableError(IntentServiceError):
    """Raised when the Official Service Registry cannot be reached at all.

    Callers (ServiceLookupService) degrade gracefully on this - POST
    /api/v1/intent/resolve still returns the classified intent with an
    empty, clearly-flagged match list rather than failing outright, per
    the Phase A "every microservice runs independently" requirement.
    """

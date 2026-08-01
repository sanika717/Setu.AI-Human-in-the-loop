class RiskEngineError(Exception):
    """Base exception for the Risk Engine."""


class RegistryUnavailableError(RiskEngineError):
    """Raised when the Official Service Registry cannot be reached at all.

    Callers degrade gracefully on this (mark the domain-whitelist check as
    unknown rather than failing outright) - the Risk Engine still runs
    independently even if the registry is down, per the Phase A "every
    microservice runs independently" requirement.
    """

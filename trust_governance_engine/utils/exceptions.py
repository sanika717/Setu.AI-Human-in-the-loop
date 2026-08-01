class GovernanceError(Exception):
    """Base exception for the Trust & Governance Engine."""


class ApplicationNotFoundError(GovernanceError):
    """Raised when an application_id does not exist."""


class FieldNotFoundError(GovernanceError):
    """Raised when a field name does not exist on the given application."""


class ApplicationLockedError(GovernanceError):
    """Raised when a mutation is attempted on an already-submitted application."""


class InvalidApplicationStateError(GovernanceError):
    """Raised when an action is attempted while the application isn't in a
    state that allows it (e.g. requesting an OTP before every field has been
    approved)."""


class DuplicateFieldError(GovernanceError):
    """Raised when application intake includes the same field name twice."""


class OTPNotFoundError(GovernanceError):
    """Raised when there is no active (unconsumed, unexpired) OTP challenge."""


class OTPExpiredError(GovernanceError):
    """Raised when the active OTP challenge has passed its expiry time."""


class OTPInvalidError(GovernanceError):
    """Raised when a submitted OTP code does not match the active challenge."""


class OTPLockedError(GovernanceError):
    """Raised when the active OTP challenge has exhausted its attempt budget."""


class TrustedDelegateNotFoundError(GovernanceError):
    """Raised when no active Trusted Delegate is registered for the application."""


class SubmissionBlockedError(GovernanceError):
    """Raised when final submission is attempted but validation fails.

    Carries the list of human-readable blocking reasons so the API layer can
    surface all of them at once instead of one at a time.
    """

    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons) or "Submission is blocked")


class AuditChainTamperedError(GovernanceError):
    """Raised by the audit integrity check when the hash chain doesn't verify."""

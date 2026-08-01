import enum


class FieldDecisionStatus(str, enum.Enum):
    """Decision state of a single governed field."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApplicationStatus(str, enum.Enum):
    """Overall governance status of an application.

    Transitions are driven entirely by field decisions (see
    services/decision_service.py::_recompute_status) plus the two terminal
    actions OTP verification and final submission:

        DRAFT --(any field decided)--> UNDER_REVIEW
        UNDER_REVIEW --(a required field rejected)--> VALIDATION_FAILED
        UNDER_REVIEW --(every field approved)--> READY_FOR_SUBMISSION
        VALIDATION_FAILED --(rejected field edited/approved)--> UNDER_REVIEW or READY_FOR_SUBMISSION
        READY_FOR_SUBMISSION --(POST /submit, after OTP verified)--> SUBMITTED

    SUBMITTED is terminal: no further field decisions are accepted once an
    application has been submitted (see ApplicationLockedError).
    """

    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    VALIDATION_FAILED = "validation_failed"
    READY_FOR_SUBMISSION = "ready_for_submission"
    SUBMITTED = "submitted"


class AuditAction(str, enum.Enum):
    APPLICATION_CREATED = "application_created"
    FIELD_APPROVED = "field_approved"
    FIELD_REJECTED = "field_rejected"
    FIELD_EDITED = "field_edited"
    OTP_REQUESTED = "otp_requested"
    OTP_VERIFIED = "otp_verified"
    OTP_FAILED = "otp_failed"
    OTP_LOCKED = "otp_locked"
    TRUSTED_DELEGATE_REGISTERED = "trusted_delegate_registered"
    TRUSTED_DELEGATE_APPROVED = "trusted_delegate_approved"
    TRUSTED_DELEGATE_REVOKED = "trusted_delegate_revoked"
    SUBMISSION_VALIDATED = "submission_validated"
    SUBMISSION_BLOCKED = "submission_blocked"
    APPLICATION_SUBMITTED = "application_submitted"
    REPORT_GENERATED = "report_generated"


class ReportFormat(str, enum.Enum):
    CSV = "csv"
    JSON = "json"
    PDF = "pdf"

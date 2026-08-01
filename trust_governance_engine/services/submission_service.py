from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Application, FinalSubmission
from ..models.enums import ApplicationStatus, AuditAction, FieldDecisionStatus
from ..utils.exceptions import ApplicationLockedError, SubmissionBlockedError
from ..utils.hashing import canonical_json, sha256_hex
from .audit_service import AuditService


class SubmissionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    def _blocking_reasons(self, application: Application) -> list[str]:
        reasons: list[str] = []

        if application.status == ApplicationStatus.SUBMITTED.value:
            reasons.append("Application has already been submitted.")
            return reasons

        pending = [f.field_name for f in application.fields if f.decision_status == FieldDecisionStatus.PENDING.value]
        if pending:
            reasons.append(f"{len(pending)} field(s) still awaiting a decision: {sorted(pending)}.")

        rejected_required = [
            f.field_name
            for f in application.fields
            if f.decision_status == FieldDecisionStatus.REJECTED.value and f.is_required
        ]
        if rejected_required:
            reasons.append(
                f"{len(rejected_required)} required field(s) are rejected and must be edited or "
                f"approved before submission: {sorted(rejected_required)}."
            )

        if not application.otp_verified:
            reasons.append("OTP has not been verified for this submission.")

        active_delegate = next((d for d in application.trusted_delegates if d.revoked_at is None), None)
        if active_delegate is not None and active_delegate.approval_required and not active_delegate.approved:
            reasons.append(
                f"Trusted Delegate '{active_delegate.delegate_name}' has not yet approved this submission."
            )

        return reasons

    def validate(self, application: Application) -> list[str]:
        """Non-mutating check. Returns a list of blocking reasons (empty = can submit)."""

        return self._blocking_reasons(application)

    async def submit(self, application: Application, actor: str) -> FinalSubmission:
        if application.status == ApplicationStatus.SUBMITTED.value:
            raise ApplicationLockedError(f"Application '{application.application_id}' has already been submitted.")

        reasons = self._blocking_reasons(application)
        if reasons:
            await self.audit.record(
                application.id,
                AuditAction.SUBMISSION_BLOCKED,
                actor=actor,
                details={"reasons": reasons},
            )
            await self.session.commit()
            raise SubmissionBlockedError(reasons)

        # Only approved fields make it into the final submitted record —
        # a rejected *optional* field is treated as intentionally dropped.
        snapshot = {
            f.field_name: {
                "value": f.current_value,
                "confidence": f.confidence,
                "source_document": f.source_document,
                "is_edited": f.is_edited,
                "decided_by": f.decided_by,
            }
            for f in application.fields
            if f.decision_status == FieldDecisionStatus.APPROVED.value
        }

        submitted_at = datetime.now(timezone.utc)
        submission_hash = sha256_hex(
            canonical_json(
                {
                    "application_id": application.application_id,
                    "applicant_id": application.applicant_id,
                    "fields": snapshot,
                    "submitted_at": submitted_at.isoformat(),
                }
            )
        )

        await self.audit.record(
            application.id,
            AuditAction.SUBMISSION_VALIDATED,
            actor=actor,
            details={"field_count": len(snapshot)},
        )

        final_submission = FinalSubmission(
            application_id=application.id,
            submitted_by=actor,
            submission_hash=submission_hash,
            field_snapshot=canonical_json(snapshot),
            submitted_at=submitted_at,
        )
        self.session.add(final_submission)

        application.status = ApplicationStatus.SUBMITTED.value
        application.submitted_at = submitted_at
        application.submission_hash = submission_hash

        await self.audit.record(
            application.id,
            AuditAction.APPLICATION_SUBMITTED,
            actor=actor,
            details={"submission_hash": submission_hash},
        )

        await self.session.commit()
        await self.session.refresh(final_submission)
        await self.session.refresh(application)
        return final_submission

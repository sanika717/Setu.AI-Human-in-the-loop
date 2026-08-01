import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import Application, GovernedField
from ..models.enums import ApplicationStatus, AuditAction, FieldDecisionStatus
from ..models.request_models import ApplicationCreateRequest
from ..utils.exceptions import (
    ApplicationLockedError,
    ApplicationNotFoundError,
    FieldNotFoundError,
)
from .audit_service import AuditService


class DecisionService:
    """Application intake plus the approve / reject / edit field workflow.

    This is the core of Phase 4: every mutation here is recorded to the
    immutable audit log in the same DB transaction as the state change, and
    the application's overall status is recomputed after every field
    decision so `ApplicationStatus` always reflects the true state of its
    fields.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def _get_or_404(self, application_id: str) -> Application:
        result = await self.session.execute(
            select(Application).where(Application.application_id == application_id)
        )
        application = result.scalars().first()
        if application is None:
            raise ApplicationNotFoundError(f"Application '{application_id}' not found")
        return application

    async def get_application(self, application_id: str) -> Application:
        return await self._get_or_404(application_id)

    async def list_applications(self, status: str | None = None) -> list[Application]:
        query = select(Application)
        if status:
            query = query.where(Application.status == status)
        query = query.order_by(Application.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_application(self, payload: ApplicationCreateRequest) -> Application:
        application = Application(
            application_id=str(uuid.uuid4()),
            applicant_id=payload.applicant_id,
            service_id=payload.service_id,
            status=ApplicationStatus.DRAFT.value,
            otp_verified=False,
        )
        self.session.add(application)
        await self.session.flush()  # assign application.id

        for item in payload.fields:
            field = GovernedField(
                application_id=application.id,
                field_name=item.field,
                original_value=item.value,
                current_value=item.value,
                confidence=item.confidence,
                confidence_level=item.confidence_level,
                source_document=item.source_document,
                reason=item.reason,
                is_required=item.required if item.required is not None else settings.field_required_by_default,
                decision_status=FieldDecisionStatus.PENDING.value,
            )
            self.session.add(field)

        await self.session.flush()

        await self.audit.record(
            application.id,
            AuditAction.APPLICATION_CREATED,
            actor="system:intake",
            details={
                "applicant_id": payload.applicant_id,
                "service_id": payload.service_id,
                "field_count": len(payload.fields),
                "fields": [item.field for item in payload.fields],
            },
        )
        await self.session.commit()
        await self.session.refresh(application)
        return application

    def _get_field(self, application: Application, field_name: str) -> GovernedField:
        for field in application.fields:
            if field.field_name == field_name:
                return field
        raise FieldNotFoundError(f"Field '{field_name}' not found on application '{application.application_id}'")

    def _assert_mutable(self, application: Application) -> None:
        if application.status == ApplicationStatus.SUBMITTED.value:
            raise ApplicationLockedError(
                f"Application '{application.application_id}' has already been submitted and is immutable."
            )

    def _recompute_status(self, application: Application) -> None:
        if application.status == ApplicationStatus.SUBMITTED.value:
            return  # terminal, never recomputed

        fields = application.fields
        any_pending = any(f.decision_status == FieldDecisionStatus.PENDING.value for f in fields)
        any_required_rejected = any(
            f.decision_status == FieldDecisionStatus.REJECTED.value and f.is_required for f in fields
        )
        any_decided = any(f.decision_status != FieldDecisionStatus.PENDING.value for f in fields)

        if any_pending:
            new_status = ApplicationStatus.UNDER_REVIEW if any_decided else ApplicationStatus.DRAFT
        elif any_required_rejected:
            new_status = ApplicationStatus.VALIDATION_FAILED
        else:
            new_status = ApplicationStatus.READY_FOR_SUBMISSION

        if new_status.value != application.status:
            # Any change to field decisions after OTP verification invalidates
            # that verification — the applicant must re-verify before the
            # (possibly changed) data can be submitted.
            if application.status == ApplicationStatus.READY_FOR_SUBMISSION.value and application.otp_verified:
                application.otp_verified = False
            application.status = new_status.value

    async def approve_field(self, application_id: str, field_name: str, actor: str, note: str | None) -> Application:
        application = await self._get_or_404(application_id)
        self._assert_mutable(application)
        field = self._get_field(application, field_name)

        field.decision_status = FieldDecisionStatus.APPROVED.value
        field.decision_note = note
        field.decided_by = actor
        field.decided_at = datetime.now(timezone.utc)

        self._recompute_status(application)

        await self.audit.record(
            application.id,
            AuditAction.FIELD_APPROVED,
            actor=actor,
            field_name=field_name,
            details={"note": note, "value": field.current_value},
        )
        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def reject_field(self, application_id: str, field_name: str, actor: str, reason: str) -> Application:
        application = await self._get_or_404(application_id)
        self._assert_mutable(application)
        field = self._get_field(application, field_name)

        field.decision_status = FieldDecisionStatus.REJECTED.value
        field.decision_note = reason
        field.decided_by = actor
        field.decided_at = datetime.now(timezone.utc)

        self._recompute_status(application)

        await self.audit.record(
            application.id,
            AuditAction.FIELD_REJECTED,
            actor=actor,
            field_name=field_name,
            details={"reason": reason, "value": field.current_value},
        )
        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def edit_field(
        self, application_id: str, field_name: str, actor: str, new_value: str, reason: str
    ) -> Application:
        application = await self._get_or_404(application_id)
        self._assert_mutable(application)
        field = self._get_field(application, field_name)

        previous_value = field.current_value
        field.current_value = new_value
        field.is_edited = True
        # A reviewer editing a field is, implicitly, approving the corrected
        # value — there is no separate approval step required after an edit.
        field.decision_status = FieldDecisionStatus.APPROVED.value
        field.decision_note = reason
        field.decided_by = actor
        field.decided_at = datetime.now(timezone.utc)

        self._recompute_status(application)

        await self.audit.record(
            application.id,
            AuditAction.FIELD_EDITED,
            actor=actor,
            field_name=field_name,
            details={"previous_value": previous_value, "new_value": new_value, "reason": reason},
        )
        await self.session.commit()
        await self.session.refresh(application)
        return application

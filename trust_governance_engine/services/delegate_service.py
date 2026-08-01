from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Application, TrustedDelegate
from ..models.enums import AuditAction
from ..models.request_models import TrustedDelegateRegisterRequest
from ..utils.exceptions import ApplicationLockedError, TrustedDelegateNotFoundError
from .audit_service import AuditService
from .notification_service import ConsoleDelegateNotificationProvider, DelegateNotificationProvider


class DelegateService:
    """Phase F (Human-in-the-Loop) Trusted Person support, and Phase G
    scoped-consent bookkeeping for that delegate relationship.

    Registering, approving, and revoking a delegate are all audited the
    same way every other governance mutation is - through AuditService, in
    the same DB transaction as the state change - so the immutable audit
    log is a complete record of who was ever trusted with this application
    and when/whether they approved it. Each of those events also fires a
    DelegateNotificationProvider call (default: log-only, same as OTP
    delivery) and records the channel used alongside the audit entry.
    """

    def __init__(self, session: AsyncSession, notification_provider: DelegateNotificationProvider | None = None):
        self.session = session
        self.audit = AuditService(session)
        self.notifier = notification_provider or ConsoleDelegateNotificationProvider()

    async def _active_delegate(self, application_pk: int) -> TrustedDelegate | None:
        result = await self.session.execute(
            select(TrustedDelegate)
            .where(TrustedDelegate.application_id == application_pk, TrustedDelegate.revoked_at.is_(None))
            .order_by(TrustedDelegate.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def get_active_delegate(self, application: Application) -> TrustedDelegate | None:
        return await self._active_delegate(application.id)

    async def register_delegate(
        self, application: Application, payload: TrustedDelegateRegisterRequest
    ) -> TrustedDelegate:
        if application.status == "submitted":
            raise ApplicationLockedError(
                f"Application '{application.application_id}' has already been submitted; "
                "a Trusted Delegate can no longer be registered."
            )

        # Registering a new delegate revokes whichever one was previously
        # active - only one delegate can gate submission at a time - but
        # the previous row is kept (revoked_at set), never deleted, so the
        # audit trail of who was ever trusted stays intact.
        previous = await self._active_delegate(application.id)
        now = datetime.now(timezone.utc)
        if previous is not None:
            previous.revoked_at = now
            revoke_channel = await self.notifier.notify(
                application.application_id,
                previous.delegate_name,
                previous.contact,
                event="revoked",
                message=(
                    f"You are no longer the Trusted Delegate for application "
                    f"{application.application_id} (superseded by a new registration)."
                ),
            )
            await self.audit.record(
                application.id,
                AuditAction.TRUSTED_DELEGATE_REVOKED,
                actor=payload.consent_given_by,
                details={
                    "delegate_name": previous.delegate_name,
                    "reason": "superseded_by_new_registration",
                    "notification_channel": revoke_channel,
                },
            )

        delegate = TrustedDelegate(
            application_id=application.id,
            delegate_name=payload.delegate_name,
            relationship_to_applicant=payload.relationship_to_applicant,
            contact=payload.contact,
            approval_required=payload.approval_required,
            consent_given_by=payload.consent_given_by,
            consent_given_at=now,
            approved=False,
        )
        self.session.add(delegate)
        await self.session.flush()

        notify_channel = await self.notifier.notify(
            application.application_id,
            delegate.delegate_name,
            delegate.contact,
            event="registered",
            message=(
                f"You have been registered as the Trusted Delegate for application "
                f"{application.application_id}."
                + (" Your approval is required before submission." if delegate.approval_required else "")
            ),
        )

        await self.audit.record(
            application.id,
            AuditAction.TRUSTED_DELEGATE_REGISTERED,
            actor=payload.consent_given_by,
            details={
                "delegate_name": delegate.delegate_name,
                "relationship_to_applicant": delegate.relationship_to_applicant,
                "approval_required": delegate.approval_required,
                "notification_channel": notify_channel,
            },
        )
        await self.session.commit()
        await self.session.refresh(delegate)
        return delegate

    async def approve(self, application: Application, actor: str) -> TrustedDelegate:
        delegate = await self._active_delegate(application.id)
        if delegate is None:
            raise TrustedDelegateNotFoundError(
                f"No active Trusted Delegate is registered for application '{application.application_id}'."
            )

        delegate.approved = True
        delegate.approved_at = datetime.now(timezone.utc)

        notify_channel = await self.notifier.notify(
            application.application_id,
            delegate.delegate_name,
            delegate.contact,
            event="approved",
            message=f"Your approval for application {application.application_id} has been recorded.",
        )

        await self.audit.record(
            application.id,
            AuditAction.TRUSTED_DELEGATE_APPROVED,
            actor=actor,
            details={"delegate_name": delegate.delegate_name, "notification_channel": notify_channel},
        )
        await self.session.commit()
        await self.session.refresh(delegate)
        return delegate

    async def revoke(self, application: Application, actor: str) -> TrustedDelegate:
        delegate = await self._active_delegate(application.id)
        if delegate is None:
            raise TrustedDelegateNotFoundError(
                f"No active Trusted Delegate is registered for application '{application.application_id}'."
            )

        delegate.revoked_at = datetime.now(timezone.utc)

        notify_channel = await self.notifier.notify(
            application.application_id,
            delegate.delegate_name,
            delegate.contact,
            event="revoked",
            message=f"You are no longer the Trusted Delegate for application {application.application_id}.",
        )

        await self.audit.record(
            application.id,
            AuditAction.TRUSTED_DELEGATE_REVOKED,
            actor=actor,
            details={
                "delegate_name": delegate.delegate_name,
                "reason": "explicit_revocation",
                "notification_channel": notify_channel,
            },
        )
        await self.session.commit()
        await self.session.refresh(delegate)
        return delegate

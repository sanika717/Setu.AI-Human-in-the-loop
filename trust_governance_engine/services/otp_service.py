from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import Application, OtpChallenge
from ..models.enums import ApplicationStatus, AuditAction
from ..utils.exceptions import (
    InvalidApplicationStateError,
    OTPExpiredError,
    OTPInvalidError,
    OTPLockedError,
    OTPNotFoundError,
)
from ..utils.hashing import constant_time_equals, generate_numeric_code, generate_salt, hash_otp_code
from ..utils.logger import get_logger
from .audit_service import AuditService

logger = get_logger(__name__)


class OTPDeliveryProvider(ABC):
    """Delivery hook for OTP codes.

    This is the seam Phase 5 (or a future iteration) hangs a real SMS/e-mail
    gateway off of, following the same provider-pattern philosophy as
    ai_guidance_engine's AI providers: business logic (generation, hashing,
    expiry, attempt-limiting) never changes when the delivery mechanism does.
    """

    @abstractmethod
    async def deliver(self, application_id: str, destination: str | None, code: str) -> str:
        """Deliver the code. Returns the delivery channel name used."""


class ConsoleOTPDeliveryProvider(OTPDeliveryProvider):
    """Default provider: logs the OTP server-side instead of sending it
    anywhere. This is what runs until a real SMS/e-mail provider is
    configured — there is no such provider anywhere else in this codebase to
    integrate with yet, so pretending to "send" one would be exactly the
    kind of mock logic Phase 4 rules out.
    """

    async def deliver(self, application_id: str, destination: str | None, code: str) -> str:
        logger.info(
            "[OTP] application_id=%s destination=%s code=%s "
            "(console delivery — no SMS/e-mail provider configured)",
            application_id,
            destination or "<not provided>",
            code,
        )
        return "console"


class OTPService:
    def __init__(self, session: AsyncSession, delivery_provider: OTPDeliveryProvider | None = None):
        self.session = session
        self.audit = AuditService(session)
        self.delivery_provider = delivery_provider or ConsoleOTPDeliveryProvider()

    async def _active_challenge(self, application_pk: int) -> OtpChallenge | None:
        result = await self.session.execute(
            select(OtpChallenge)
            .where(OtpChallenge.application_id == application_pk, OtpChallenge.consumed_at.is_(None))
            .order_by(OtpChallenge.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def request_otp(self, application: Application, destination: str | None) -> tuple[OtpChallenge, str]:
        if application.status != ApplicationStatus.READY_FOR_SUBMISSION.value:
            raise InvalidApplicationStateError(
                "OTP can only be requested once every field has been approved "
                f"(current status: '{application.status}')."
            )

        # Invalidate any previous unconsumed challenge for this application —
        # only one OTP is live at a time.
        previous = await self._active_challenge(application.id)
        if previous is not None:
            previous.consumed_at = datetime.now(timezone.utc)

        code = generate_numeric_code(settings.otp_code_length)
        salt = generate_salt()
        otp_hash = hash_otp_code(code, salt, settings.otp_hash_pepper)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.otp_expiry_seconds)

        channel = await self.delivery_provider.deliver(application.application_id, destination, code)

        challenge = OtpChallenge(
            application_id=application.id,
            destination=destination,
            otp_hash=otp_hash,
            salt=salt,
            delivery_channel=channel,
            attempts_remaining=settings.otp_max_attempts,
            expires_at=expires_at,
            verified=False,
        )
        self.session.add(challenge)
        await self.session.flush()

        # The OTP code itself is never written to the audit log — only the
        # fact that one was requested and how it was (attempted to be)
        # delivered.
        await self.audit.record(
            application.id,
            AuditAction.OTP_REQUESTED,
            actor="system:otp",
            details={"destination": destination, "delivery_channel": channel, "expires_at": expires_at.isoformat()},
        )
        await self.session.commit()
        await self.session.refresh(challenge)

        exposed_code = code if settings.otp_dev_mode_expose_code else None
        return challenge, exposed_code

    async def verify_otp(self, application: Application, code: str) -> OtpChallenge:
        challenge = await self._active_challenge(application.id)
        if challenge is None:
            raise OTPNotFoundError("No active OTP challenge for this application. Request one first.")

        now = datetime.now(timezone.utc)
        expires_at = challenge.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if now > expires_at:
            challenge.consumed_at = now
            await self.audit.record(
                application.id, AuditAction.OTP_FAILED, actor="system:otp", details={"reason": "expired"}
            )
            await self.session.commit()
            raise OTPExpiredError("OTP has expired. Request a new one.")

        if challenge.attempts_remaining <= 0:
            challenge.consumed_at = now
            await self.audit.record(
                application.id, AuditAction.OTP_LOCKED, actor="system:otp",
                details={"reason": "attempts_exhausted"},
            )
            await self.session.commit()
            raise OTPLockedError("Too many incorrect attempts. Request a new OTP.")

        candidate_hash = hash_otp_code(code, challenge.salt, settings.otp_hash_pepper)
        if not constant_time_equals(candidate_hash, challenge.otp_hash):
            challenge.attempts_remaining -= 1
            await self.audit.record(
                application.id,
                AuditAction.OTP_FAILED,
                actor="system:otp",
                details={"reason": "mismatch", "attempts_remaining": challenge.attempts_remaining},
            )
            await self.session.commit()
            raise OTPInvalidError(
                f"Incorrect OTP. {challenge.attempts_remaining} attempt(s) remaining."
            )

        challenge.verified = True
        challenge.consumed_at = now
        application.otp_verified = True

        await self.audit.record(
            application.id, AuditAction.OTP_VERIFIED, actor="system:otp", details={}
        )
        await self.session.commit()
        await self.session.refresh(challenge)
        return challenge

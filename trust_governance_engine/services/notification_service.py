from abc import ABC, abstractmethod

from ..utils.logger import get_logger

logger = get_logger(__name__)


class DelegateNotificationProvider(ABC):
    """Delivery hook for Trusted Delegate (Phase F) notifications.

    Same seam philosophy as trust_governance_engine.services.otp_service.
    OTPDeliveryProvider and ai_guidance_engine's AI providers: the business
    logic that decides *when* a delegate needs to be told something
    (registered, approved, revoked) never changes when the delivery
    mechanism does. Drop in a real SMS/e-mail provider here later without
    touching DelegateService.
    """

    @abstractmethod
    async def notify(self, application_id: str, delegate_name: str, contact: str, event: str, message: str) -> str:
        """Notify the delegate (or, for revocation, whoever needs to know).

        Returns the delivery channel name used, so callers can record it on
        the audit trail the same way OTP delivery does.
        """


class ConsoleDelegateNotificationProvider(DelegateNotificationProvider):
    """Default provider: logs the notification server-side instead of
    sending it anywhere. This is what runs until a real SMS/e-mail provider
    is configured — there is no such provider anywhere else in this codebase
    to integrate with yet (the exact same gap OTP delivery has, by design),
    so pretending to actually send one would be mock logic Phase 4 rules
    out. The dedicated channel name ("log_only") makes that limitation
    visible in the audit trail rather than implying delivery happened.
    """

    async def notify(self, application_id: str, delegate_name: str, contact: str, event: str, message: str) -> str:
        logger.info(
            "[Delegate Notification] application_id=%s delegate=%s contact=%s event=%s message=%s "
            "(log-only delivery — no SMS/e-mail provider configured)",
            application_id,
            delegate_name,
            contact,
            event,
            message,
        )
        return "log_only"

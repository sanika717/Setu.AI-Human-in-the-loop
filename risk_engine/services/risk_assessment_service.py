from ..models.response_models import ContentRiskScanResponse, RedirectRiskCheckResponse, RiskFinding
from ..utils.exceptions import RegistryUnavailableError
from ..utils.logger import get_logger
from .domain_verifier import is_domain_allowed, is_https
from .redirect_analyzer import analyze_redirect_chain
from .registry_client import RegistryClient
from .sensitive_field_scanner import scan_for_sensitive_fields

logger = get_logger(__name__)


class RiskAssessmentService:
    """Phase D (Security Shield), minimal but real implementation:
    HTTPS enforcement, official-domain-whitelist verification (sourced live
    from the Official Service Registry), redirect-chain hop checking, and
    sensitive-field-label detection. Stateless - every check is computed
    fresh per request; nothing is persisted here (audit logging of the
    *outcome* of a redirect confirmation happens in system_orchestrator,
    which is the caller).
    """

    def __init__(self, registry_client: RegistryClient | None = None):
        self.registry_client = registry_client or RegistryClient()

    async def check_redirect(
        self, service_id: str, target_url: str, redirect_chain: list[str]
    ) -> RedirectRiskCheckResponse:
        findings: list[RiskFinding] = []

        https_ok = is_https(target_url)
        if not https_ok:
            findings.append(
                RiskFinding(
                    code="INSECURE_SCHEME",
                    message=f"{target_url} is not served over HTTPS.",
                    severity="error",
                )
            )

        try:
            redirect_info = await self.registry_client.redirect_info(service_id)
        except RegistryUnavailableError:
            logger.warning(
                "Official Service Registry unreachable; cannot verify domain whitelist for service_id=%s",
                service_id,
            )
            redirect_info = None
            domain_ok = None
            findings.append(
                RiskFinding(
                    code="REGISTRY_UNAVAILABLE",
                    message=(
                        "Could not verify the official domain whitelist because the Official "
                        "Service Registry is unreachable."
                    ),
                    severity="warning",
                )
            )
        else:
            if redirect_info is None:
                domain_ok = False
                findings.append(
                    RiskFinding(
                        code="UNKNOWN_SERVICE",
                        message=f"'{service_id}' is not a registered service; no whitelist to verify against.",
                        severity="error",
                    )
                )
            else:
                allowed_domains: list[str] = redirect_info.get("allowed_domains", [])
                domain_ok = is_domain_allowed(target_url, allowed_domains)
                if not domain_ok:
                    findings.append(
                        RiskFinding(
                            code="DOMAIN_NOT_WHITELISTED",
                            message=f"{target_url} is not on the official domain whitelist for '{service_id}'.",
                            severity="error",
                        )
                    )
                for hop_message in analyze_redirect_chain(redirect_chain, allowed_domains):
                    findings.append(
                        RiskFinding(code="SUSPICIOUS_REDIRECT_HOP", message=hop_message, severity="error")
                    )

        has_error = any(finding.severity == "error" for finding in findings)
        if domain_ok is None and not has_error:
            risk_level = "unknown"
        elif has_error:
            risk_level = "high"
        else:
            risk_level = "none"

        return RedirectRiskCheckResponse(
            service_id=service_id,
            target_url=target_url,
            https_verified=https_ok,
            domain_whitelist_verified=domain_ok,
            risk_level=risk_level,
            should_pause_guidance=has_error,
            findings=findings,
        )

    def scan_content(self, page_text: str) -> ContentRiskScanResponse:
        detected = scan_for_sensitive_fields(page_text)
        findings = [
            RiskFinding(
                code="SENSITIVE_FIELD_DETECTED",
                message=(
                    f"This step appears to ask for a {category.upper()}. Sahaay.AI pauses guidance "
                    "here - never type this anywhere except the official site itself."
                ),
                severity="warning",
            )
            for category in detected
        ]
        return ContentRiskScanResponse(
            sensitive_fields_detected=detected,
            should_pause_guidance=bool(detected),
            findings=findings,
        )

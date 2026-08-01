from pydantic import BaseModel, Field


class RiskFinding(BaseModel):
    code: str = Field(..., description="Machine-readable finding code, e.g. DOMAIN_NOT_WHITELISTED")
    message: str = Field(..., description="Human-readable explanation of the finding")
    severity: str = Field(..., description="'error' should pause guidance, 'warning' does not by itself")


class RedirectRiskCheckResponse(BaseModel):
    """Response for POST /api/v1/risk/redirect-check."""

    engine: str = "Risk Engine"
    service_id: str
    target_url: str
    https_verified: bool
    domain_whitelist_verified: bool | None = Field(
        None,
        description="None only when the Official Service Registry could not be reached to fetch the whitelist",
    )
    risk_level: str = Field(..., description="'none', 'high', or 'unknown' (registry unreachable)")
    should_pause_guidance: bool = Field(
        ..., description="True if AI Guidance / redirect should be paused pending human review"
    )
    findings: list[RiskFinding] = Field(default_factory=list)


class ContentRiskScanResponse(BaseModel):
    """Response for POST /api/v1/risk/content-scan."""

    engine: str = "Risk Engine"
    sensitive_fields_detected: list[str] = Field(default_factory=list)
    should_pause_guidance: bool
    findings: list[RiskFinding] = Field(default_factory=list)

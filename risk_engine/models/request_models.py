from pydantic import BaseModel, Field


class RedirectRiskCheckRequest(BaseModel):
    """Request payload for POST /api/v1/risk/redirect-check.

    Called by system_orchestrator's POST /api/v1/portals/confirm right
    before it would hand the user off to an official site, so the Security
    Shield check happens on the actual redirect path, not just once at
    catalog-listing time.
    """

    service_id: str = Field(..., min_length=1, description="Official Service Registry service_id being navigated to")
    target_url: str = Field(..., min_length=1, description="The URL Sahaay.AI is about to redirect the user to")
    redirect_chain: list[str] = Field(
        default_factory=list,
        description=(
            "Optional intermediate hop URLs observed before target_url, oldest first. Leave "
            "empty if the caller only knows the final destination."
        ),
    )


class ContentRiskScanRequest(BaseModel):
    """Request payload for POST /api/v1/risk/content-scan.

    `page_text` must be descriptive text ONLY (a form's field labels,
    the current guidance step's instructions, etc.) - never a value a user
    actually typed into a field. Sahaay.AI never sends real
    passwords/OTPs/PINs/CVVs to any service, including this one.
    """

    page_text: str = Field(
        ...,
        min_length=1,
        description="Field labels / step instructions to scan for sensitive-field indicators",
    )

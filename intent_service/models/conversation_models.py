from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .request_models import IntentClassifyRequest
from .response_models import ServiceMatch


class ConversationState(str, Enum):
    """Where a conversation currently stands. Purely data - every transition
    is driven by ConversationManager reading registry data (eligibility
    rules) and classifier output, never by a hardcoded per-service branch.
    """

    COLLECTING_INTENT = "collecting_intent"
    DISAMBIGUATING_SERVICE = "disambiguating_service"
    COLLECTING_INFO = "collecting_info"
    COMPLETED = "completed"
    NEEDS_HUMAN_HELP = "needs_human_help"


class ConversationMessageRequest(IntentClassifyRequest):
    """Same `text`/`applicant_id`/`language` shape as Phase C1's
    `IntentClassifyRequest` (reused here rather than re-declared, so the
    two request contracts can never silently drift apart) plus the one
    field genuinely new to a multi-turn conversation: `conversation_id`.
    """

    conversation_id: str | None = Field(
        None,
        description=(
            "Omit on the first message of a new conversation - one is generated and returned. "
            "Pass it back on every subsequent message to continue the same conversation."
        ),
    )
    language: str | None = Field(
        None,
        description=(
            "Optional ISO 639-1 language override for this turn. Only meaningful while the "
            "conversation is still in 'collecting_intent' (see ConversationManager) - once a "
            "language is established for a conversation it is reused for every later turn, "
            "since short follow-up answers (e.g. a bare number) don't carry enough script "
            "information to auto-detect reliably."
        ),
    )


class EligibilityRuleOutcome(BaseModel):
    field: str
    operator: str
    passed: bool | None = None
    message: str


class EligibilityOutcome(BaseModel):
    """Mirrors official_service_registry's EligibilityCheckResponse - kept as
    a separate model (rather than importing across the service boundary,
    which this architecture never does) so intent_service's contract is
    self-contained even though the shape happens to match today.
    """

    service_id: str
    is_eligible: bool | None = None
    rule_results: list[EligibilityRuleOutcome] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ConversationTurnResponse(BaseModel):
    engine: str = "Intent Service"
    conversation_id: str
    state: ConversationState
    turn_count: int
    message: str = Field(..., description="What to show the citizen next - a question, or a final summary")

    language: str
    language_name: str

    detected_intent: str | None = None
    label: str | None = None
    confidence: float | None = None
    service_category: str | None = None

    candidate_matches: list[ServiceMatch] = Field(
        default_factory=list, description="Populated only while state == disambiguating_service"
    )
    resolved_service: ServiceMatch | None = Field(
        None, description="Set once a single service has been identified (collecting_info onward)"
    )

    collected_context: dict[str, Any] = Field(
        default_factory=dict, description="Every piece of information gathered so far this conversation"
    )
    missing_fields: list[str] = Field(default_factory=list)
    pending_field: str | None = Field(None, description="The field the current `message` question is asking about")

    eligibility_result: EligibilityOutcome | None = None
    is_complete: bool = False
    registry_available: bool = True
    notes: list[str] = Field(default_factory=list)


class ConversationStateResponse(ConversationTurnResponse):
    """Same shape as a turn response - returned by GET (read-only, no new turn)."""

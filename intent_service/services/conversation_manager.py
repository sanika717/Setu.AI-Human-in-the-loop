from typing import Any

from ..config import settings
from ..models.conversation_models import (
    ConversationState,
    ConversationTurnResponse,
    EligibilityOutcome,
    EligibilityRuleOutcome,
)
from ..models.response_models import ServiceMatch
from ..utils.exceptions import RegistryUnavailableError
from ..utils.logger import get_logger
from . import answer_parser, field_prompt_service
from .conversation_store import ConversationSession, ConversationStore
from .intent_service import UNCLASSIFIED_INTENT_ID
from .registry_client import RegistryClient
from .service_lookup_service import ServiceLookupService

logger = get_logger(__name__)


class ConversationManager:
    """Phase C4: a modular conversation layer on top of Phase C1/C2/C3's
    IntentService and ServiceLookupService.

    Deliberately built as a NEW class that composes the existing
    ServiceLookupService/IntentService/RegistryClient rather than modifying
    them - `/intent/classify` and `/intent/resolve` are completely
    untouched, so this can be dropped into `intent_service` (or removed)
    without affecting anything already shipped in Phases C1-C3.

    Input here is always plain text plus an optional language code -
    exactly what `POST /intent/classify` already takes. A future C5 voice
    layer only needs to transcribe audio to text and call
    `handle_message()` with the result; nothing in this class or its
    contracts assumes the text came from typing.

    State transitions (see ConversationState):
      collecting_intent -> disambiguating_service (multiple close-scoring
        service matches) or collecting_info (single clear match) or stays
        in collecting_intent (unclassified/unsupported language) or
        needs_human_help (too many failed clarification attempts)
      disambiguating_service -> collecting_info (candidate picked, or
        attempts exhausted and the top candidate is used) or stays
      collecting_info -> collecting_info (more fields still missing) or
        completed (every field collected, eligibility resolved
        automatically - requirement 5)
      completed / needs_human_help -> terminal; a new conversation_id
        starts fresh rather than reopening one of these.
    """

    def __init__(
        self,
        store: ConversationStore,
        service_lookup_service: ServiceLookupService,
        registry_client: RegistryClient | None = None,
    ) -> None:
        self.store = store
        self.service_lookup_service = service_lookup_service
        self.registry_client = registry_client or RegistryClient()

    async def handle_message(
        self, conversation_id: str | None, text: str, language: str | None, applicant_id: str | None = None
    ) -> ConversationTurnResponse:
        session = self.store.get(conversation_id) if conversation_id else None
        if session is None:
            session = self.store.create()

        session.turn_count += 1
        session.history.append({"role": "user", "text": text})

        if session.state == ConversationState.COMPLETED:
            response = self._respond(session, field_prompt_service.get_message("already_completed", session.language))
            self.store.save(session)
            return response
        if session.state == ConversationState.NEEDS_HUMAN_HELP:
            response = self._respond(session, field_prompt_service.get_message("needs_human_help", session.language))
            self.store.save(session)
            return response

        if session.state == ConversationState.COLLECTING_INTENT:
            response_text = await self._handle_collecting_intent(session, text, language)
        elif session.state == ConversationState.DISAMBIGUATING_SERVICE:
            response_text = await self._handle_disambiguation(session, text)
        elif session.state == ConversationState.COLLECTING_INFO:
            response_text = await self._handle_collecting_info(session, text)
        else:  # pragma: no cover - defensive, unreachable with current states
            response_text = field_prompt_service.get_message("ask_clarify_intent", session.language)

        self.store.save(session)
        return self._respond(session, response_text)

    def get_state(self, conversation_id: str) -> ConversationTurnResponse | None:
        session = self.store.get(conversation_id)
        if session is None:
            return None
        last_message = session.history[-1]["text"] if session.history and session.history[-1]["role"] == "assistant" else ""
        return self._respond(session, last_message)

    def reset(self, conversation_id: str) -> bool:
        return self.store.delete(conversation_id)

    # -- collecting_intent ------------------------------------------------

    async def _handle_collecting_intent(self, session: ConversationSession, text: str, language: str | None) -> str:
        # Once a language is established for this conversation, later turns
        # in collecting_intent reuse it unless the caller explicitly
        # overrides - a short clarifying reply ("pension") shouldn't
        # re-trigger script detection against a possibly-empty signal.
        effective_language = language or (session.language if session.turn_count > 1 else None)

        resolution = await self.service_lookup_service.resolve(text, language=effective_language)
        session.language = resolution.language
        session.language_name = resolution.language_name

        if not resolution.language_supported:
            session.clarification_attempts += 1
            if session.clarification_attempts > settings.conversation_max_clarification_attempts:
                session.state = ConversationState.NEEDS_HUMAN_HELP
                return field_prompt_service.get_message("needs_human_help", session.language)
            return field_prompt_service.get_message("unsupported_language", session.language)

        session.detected_intent = resolution.detected_intent
        session.label = resolution.label
        session.confidence = resolution.confidence
        session.registry_available = resolution.registry_available

        if resolution.detected_intent == UNCLASSIFIED_INTENT_ID or not resolution.matches:
            session.clarification_attempts += 1
            if session.clarification_attempts > settings.conversation_max_clarification_attempts:
                session.state = ConversationState.NEEDS_HUMAN_HELP
                return field_prompt_service.get_message("needs_human_help", session.language)
            return field_prompt_service.get_message("ask_clarify_intent", session.language)

        session.service_category = resolution.service_category
        session.clarification_attempts = 0

        matches = [match.model_dump() for match in resolution.matches]
        if self._has_clear_winner(matches):
            return await self._lock_in_service(session, matches[0], original_text=text)

        session.candidate_matches = matches
        session.state = ConversationState.DISAMBIGUATING_SERVICE
        return self._disambiguation_prompt(session)

    @staticmethod
    def _has_clear_winner(matches: list[dict[str, Any]]) -> bool:
        if len(matches) <= 1:
            return True
        top, second = matches[0]["match_confidence"], matches[1]["match_confidence"]
        return (top - second) >= settings.conversation_disambiguation_confidence_gap

    def _disambiguation_prompt(self, session: ConversationSession) -> str:
        intro = field_prompt_service.get_message("disambiguation_intro", session.language)
        options = "\n".join(
            f"{i + 1}. {match['service_name']}" for i, match in enumerate(session.candidate_matches)
        )
        return f"{intro}\n{options}"

    # -- disambiguating_service --------------------------------------------

    async def _handle_disambiguation(self, session: ConversationSession, text: str) -> str:
        chosen = self._match_candidate(text, session.candidate_matches)

        if chosen is None:
            session.disambiguation_attempts += 1
            if session.disambiguation_attempts > settings.conversation_max_disambiguation_attempts:
                chosen = session.candidate_matches[0]
                message = field_prompt_service.get_message(
                    "disambiguation_gave_up", session.language, service_name=chosen["service_name"]
                )
                lock_message = await self._lock_in_service(session, chosen, original_text=text)
                return f"{message} {lock_message}"
            return field_prompt_service.get_message("disambiguation_could_not_match", session.language)

        session.disambiguation_attempts = 0
        return await self._lock_in_service(session, chosen, original_text=text)

    @staticmethod
    def _match_candidate(text: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        stripped = text.strip().lower()

        number = answer_parser.parse_number(stripped)
        if number is not None:
            index = int(number) - 1
            if 0 <= index < len(candidates):
                return candidates[index]

        matches = [
            candidate
            for candidate in candidates
            if stripped in candidate["service_name"].lower() or stripped in candidate["service_id"].lower()
            or candidate["service_id"].lower() in stripped
        ]
        if len(matches) == 1:
            return matches[0]
        return None

    # -- collecting_info / finalize -----------------------------------------

    async def _lock_in_service(
        self, session: ConversationSession, match: dict[str, Any], original_text: str
    ) -> str:
        session.resolved_service = match
        session.candidate_matches = []

        try:
            definition = await self.registry_client.get_service(match["service_id"])
        except RegistryUnavailableError:
            session.registry_available = False
            definition = None

        rules = (definition or {}).get("eligibility_rules", [])
        session.notes.append(f"resolved_service={match['service_id']}")

        # Opportunistic autofill (requirement 4/5): a numeric answer already
        # present in the very first message (e.g. "I am 65 and want the old
        # age pension") shouldn't be asked again. Only numeric fields are
        # autofilled this way - free-text boolean autofill from an intent
        # sentence is too error-prone to do reliably, so those are always
        # asked explicitly.
        autofilled_number = answer_parser.parse_number(original_text)
        for rule in rules:
            field = rule["field"]
            if field in session.collected_context:
                continue
            if autofilled_number is not None and answer_parser.infer_field_type(rule) == "numeric":
                session.collected_context[field] = autofilled_number

        prompt = self._advance_collecting_info(session, rules)
        if prompt is not None:
            return prompt
        return await self._finalize(session, rules)

    def _advance_collecting_info(self, session: ConversationSession, rules: list[dict[str, Any]]) -> str | None:
        session.missing_fields = [
            rule["field"] for rule in rules if rule["field"] not in session.collected_context
        ]

        if not session.missing_fields:
            session.pending_field = None
            return None  # signals "finalize" to the async caller below

        session.state = ConversationState.COLLECTING_INFO
        session.pending_field = session.missing_fields[0]
        rule = next(r for r in rules if r["field"] == session.pending_field)
        field_type = answer_parser.infer_field_type(rule)
        return field_prompt_service.get_field_prompt(session.pending_field, session.language, field_type)

    async def _handle_collecting_info(self, session: ConversationSession, text: str) -> str:
        assert session.resolved_service is not None
        service_id = session.resolved_service["service_id"]

        try:
            definition = await self.registry_client.get_service(service_id)
        except RegistryUnavailableError:
            session.registry_available = False
            definition = None
        rules = (definition or {}).get("eligibility_rules", [])

        pending = session.pending_field
        rule = next((r for r in rules if r["field"] == pending), None) if pending else None

        if rule is not None:
            field_type = answer_parser.infer_field_type(rule)
            parsed_ok, value = answer_parser.parse_answer(text, field_type, session.language)

            if parsed_ok:
                session.collected_context[pending] = value
                session.field_attempts[pending] = 0
            else:
                session.field_attempts[pending] = session.field_attempts.get(pending, 0) + 1
                if session.field_attempts[pending] > settings.conversation_max_field_attempts:
                    # Give up on this one field rather than looping forever;
                    # record it as unknown and move on (requirement: never
                    # hard-fail / never loop indefinitely).
                    session.collected_context[pending] = None
                    session.notes.append(f"field_skipped_after_retries={pending}")
                else:
                    key = "could_not_parse_yes_no" if field_type == "boolean" else "could_not_parse_number"
                    return field_prompt_service.get_message(key, session.language)

        prompt = self._advance_collecting_info(session, rules)
        if prompt is not None:
            return prompt

        return await self._finalize(session, rules)

    async def _finalize(self, session: ConversationSession, rules: list[dict[str, Any]]) -> str:
        service_id = session.resolved_service["service_id"]
        service_name = session.resolved_service["service_name"]
        official_url = session.resolved_service["official_url"]

        if not rules:
            session.state = ConversationState.COMPLETED
            session.eligibility_result = None
            return field_prompt_service.get_message(
                "completed_no_rules_summary", session.language, service_name=service_name, official_url=official_url
            )

        try:
            result = await self.registry_client.check_eligibility(service_id, session.collected_context)
        except RegistryUnavailableError:
            session.registry_available = False
            session.state = ConversationState.COMPLETED
            return field_prompt_service.get_message(
                "completed_registry_unavailable", session.language, service_name=service_name
            )

        session.eligibility_result = result
        session.state = ConversationState.COMPLETED

        summary = "; ".join(note["message"] for note in (result or {}).get("rule_results", []) if note.get("message"))
        return field_prompt_service.get_message(
            "completed_summary",
            session.language,
            service_name=service_name,
            official_url=official_url,
            eligibility_summary=summary,
        )

    # -- response assembly ---------------------------------------------------

    def _respond(self, session: ConversationSession, message: str) -> ConversationTurnResponse:
        if message and (not session.history or session.history[-1] != {"role": "assistant", "text": message}):
            session.history.append({"role": "assistant", "text": message})

        eligibility = None
        if session.eligibility_result is not None:
            eligibility = EligibilityOutcome(
                service_id=session.eligibility_result["service_id"],
                is_eligible=session.eligibility_result.get("is_eligible"),
                rule_results=[
                    EligibilityRuleOutcome(**r) for r in session.eligibility_result.get("rule_results", [])
                ],
                notes=session.eligibility_result.get("notes", []),
            )

        return ConversationTurnResponse(
            conversation_id=session.conversation_id,
            state=session.state,
            turn_count=session.turn_count,
            message=message,
            language=session.language,
            language_name=session.language_name,
            detected_intent=session.detected_intent,
            label=session.label,
            confidence=session.confidence,
            service_category=session.service_category,
            candidate_matches=[ServiceMatch(**m) for m in session.candidate_matches],
            resolved_service=ServiceMatch(**session.resolved_service) if session.resolved_service else None,
            collected_context=dict(session.collected_context),
            missing_fields=list(session.missing_fields),
            pending_field=session.pending_field,
            eligibility_result=eligibility,
            is_complete=session.state == ConversationState.COMPLETED,
            registry_available=session.registry_available,
            notes=list(session.notes),
        )

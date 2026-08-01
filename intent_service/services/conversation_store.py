import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..models.conversation_models import ConversationState


@dataclass
class ConversationSession:
    """All state ConversationManager needs to resume a conversation. This is
    the ONLY place conversation state lives - ConversationManager itself is
    stateless between calls, same shape as every other service/manager
    class in this codebase.
    """

    conversation_id: str
    state: ConversationState = ConversationState.COLLECTING_INTENT
    language: str = "en"
    language_name: str = "English"

    turn_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    detected_intent: str | None = None
    label: str | None = None
    confidence: float | None = None
    service_category: str | None = None

    candidate_matches: list[dict[str, Any]] = field(default_factory=list)
    resolved_service: dict[str, Any] | None = None

    collected_context: dict[str, Any] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    pending_field: str | None = None
    field_attempts: dict[str, int] = field(default_factory=dict)

    clarification_attempts: int = 0
    disambiguation_attempts: int = 0

    eligibility_result: dict[str, Any] | None = None
    registry_available: bool = True
    notes: list[str] = field(default_factory=list)

    history: list[dict[str, str]] = field(default_factory=list)


class ConversationStore(Protocol):
    """Interface every conversation store implementation must satisfy.

    This is the seam a future persistent backend (Redis, a database - see
    the root README's "Redis for temporary session cache" note, which this
    was always meant to plug into) swaps in behind, without
    ConversationManager or the API layer changing at all.
    """

    def get(self, conversation_id: str) -> ConversationSession | None: ...

    def create(self) -> ConversationSession: ...

    def save(self, session: ConversationSession) -> None: ...

    def delete(self, conversation_id: str) -> bool: ...


class InMemoryConversationStore:
    """Process-local dict-backed store. Sessions are lost on restart and are
    not shared across multiple running instances of this service - fine for
    a single local/demo deployment, and exactly the gap the ConversationStore
    protocol above exists to let a later phase close (e.g. a Redis-backed
    implementation with the exact same three methods) without touching
    ConversationManager or the API routes.

    Idle sessions older than `ttl_seconds` are dropped lazily (on the next
    `get`/`create` call that happens to touch them) rather than via a
    background task, keeping this dependency-free.
    """

    def __init__(self, ttl_seconds: float) -> None:
        self.ttl_seconds = ttl_seconds
        self._sessions: dict[str, ConversationSession] = {}

    def _is_expired(self, session: ConversationSession) -> bool:
        return (time.time() - session.updated_at) > self.ttl_seconds

    def _evict_expired(self) -> None:
        expired = [cid for cid, session in self._sessions.items() if self._is_expired(session)]
        for cid in expired:
            del self._sessions[cid]

    def get(self, conversation_id: str) -> ConversationSession | None:
        self._evict_expired()
        return self._sessions.get(conversation_id)

    def create(self) -> ConversationSession:
        self._evict_expired()
        session = ConversationSession(conversation_id=str(uuid.uuid4()))
        self._sessions[session.conversation_id] = session
        return session

    def save(self, session: ConversationSession) -> None:
        session.updated_at = time.time()
        self._sessions[session.conversation_id] = session

    def delete(self, conversation_id: str) -> bool:
        return self._sessions.pop(conversation_id, None) is not None

    def __len__(self) -> int:  # pragma: no cover - debug convenience only
        return len(self._sessions)


_default_store: InMemoryConversationStore | None = None


def get_default_store(ttl_seconds: float) -> InMemoryConversationStore:
    """Process-wide singleton so every request in this running service shares
    the same in-memory sessions. Tests construct their own
    InMemoryConversationStore instances directly instead of using this, so
    they never share state with each other or with a running app.
    """

    global _default_store
    if _default_store is None:
        _default_store = InMemoryConversationStore(ttl_seconds=ttl_seconds)
    return _default_store

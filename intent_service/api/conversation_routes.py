from fastapi import APIRouter, Depends, HTTPException

from ..models.conversation_models import ConversationMessageRequest, ConversationStateResponse, ConversationTurnResponse
from ..services.conversation_manager import ConversationManager
from .dependencies import get_conversation_manager

router = APIRouter()


@router.post("/conversation/message", response_model=ConversationTurnResponse, tags=["Conversation"])
async def send_message(
    request: ConversationMessageRequest,
    manager: ConversationManager = Depends(get_conversation_manager),
) -> ConversationTurnResponse:
    """Phase C4: send one turn of a conversation.

    Omit `conversation_id` to start a new conversation - one is generated
    and returned in the response; pass it back on every subsequent call to
    continue that same conversation. Internally this reuses Phase C2/C3's
    `/intent/resolve` logic for the first turn(s), then asks follow-up
    questions for whatever eligibility information is still missing for
    the resolved service, and automatically finishes (calling the Official
    Service Registry's eligibility check) the moment nothing is missing -
    no separate "finalize" call needed.
    """

    return await manager.handle_message(
        conversation_id=request.conversation_id,
        text=request.text,
        language=request.language,
        applicant_id=request.applicant_id,
    )


@router.get("/conversation/{conversation_id}", response_model=ConversationStateResponse, tags=["Conversation"])
async def get_conversation_state(
    conversation_id: str,
    manager: ConversationManager = Depends(get_conversation_manager),
) -> ConversationStateResponse:
    """Read-only: returns the current state of an existing conversation
    without advancing it (no new turn, no new question asked).
    """

    state = manager.get_state(conversation_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"No conversation found with id '{conversation_id}'")
    return ConversationStateResponse(**state.model_dump())


@router.delete("/conversation/{conversation_id}", tags=["Conversation"])
async def reset_conversation(
    conversation_id: str,
    manager: ConversationManager = Depends(get_conversation_manager),
) -> dict:
    """Discards a conversation's state. Not required between conversations
    (an idle session expires on its own - see CONVERSATION_SESSION_TTL_SECONDS)
    but useful for tests and for a client that wants to explicitly restart.
    """

    deleted = manager.reset(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No conversation found with id '{conversation_id}'")
    return {"status": "ok", "conversation_id": conversation_id, "deleted": True}

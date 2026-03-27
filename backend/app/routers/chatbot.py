"""Chatbot endpoint for cooperative AI advisor."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_member, require_coop_exco
from app.core.responses import ApiResponse
from app.models.member import Member
from app.schemas.chatbot import ChatRequest, ChatResponse
from app.services.chatbot_service import answer_chatbot_question

router = APIRouter(prefix="/cooperatives", tags=["chatbot"])


@router.post("/{coop_id}/chat")
async def cooperative_chat(
    coop_id: UUID,
    body: ChatRequest,
    current_member: Member = Depends(get_current_member),
    _exco=Depends(require_coop_exco),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    answer = await answer_chatbot_question(
        question=body.question,
        coop_id=coop_id,
    )
    return ApiResponse.success(
        data=ChatResponse(answer=answer),
        message="OK",
    )
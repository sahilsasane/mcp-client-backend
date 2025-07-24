"""
Chat-related API endpoints
"""

from fastapi import APIRouter, HTTPException

from ..core.config import get_chatbot_service
from ..models.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["Chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a chat message and get response with memory persistence"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    try:
        result = await chatbot_service.process_query(request.query, request.session_id)

        return ChatResponse(
            response=result["response"],
            session_id=result["session_id"],
            session_title=result["session_title"],
            tool_calls=result["tool_calls"],
            timestamp=result["timestamp"],
            message_count=result["message_count"],
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.options("/chat")
async def chat_options():
    """Handle CORS preflight for chat endpoint"""
    return {"message": "OK"}

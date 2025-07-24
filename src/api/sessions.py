"""
Session management API endpoints
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException

from ..core.config import get_chatbot_service
from ..models.schemas import SessionCreateRequest, SessionResponse

router = APIRouter(tags=["Sessions"])


@router.post("/sessions")
async def create_session(request: SessionCreateRequest):
    """Create a new chat session"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    try:
        session_id = chatbot_service.chatbot.memory.create_session(request.title)
        session = chatbot_service.chatbot.memory.get_current_session()

        return {
            "session_id": session_id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "message": "✅ Session created successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.options("/sessions")
async def sessions_options():
    """Handle CORS preflight for sessions endpoint"""
    return {"message": "OK"}


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions():
    """List all chat sessions with metadata"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    try:
        sessions_data = chatbot_service.chatbot.memory.list_sessions()
        return [
            SessionResponse(
                id=session["id"],
                title=session["title"],
                created_at=session["created_at"],
                last_activity=session["last_activity"],
                message_count=session["message_count"],
                is_current=session["is_current"],
            )
            for session in sessions_data
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}")
async def get_session_details(session_id: str):
    """Get detailed information about a specific session"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    session = chatbot_service.chatbot.memory.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "last_activity": session.last_activity.isoformat(),
        "message_count": len(session.messages),
        "context": session.context,
        "is_current": session.id == chatbot_service.chatbot.memory.current_session_id,
    }


@router.post("/{session_id}/switch")
async def switch_session(session_id: str):
    """Switch to a specific session"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    if chatbot_service.chatbot.memory.switch_session(session_id):
        session = chatbot_service.chatbot.memory.get_current_session()
        return {
            "message": f"✅ Switched to session: {session.title}",
            "session_id": session_id,
            "session_title": session.title,
            "message_count": len(session.messages),
        }
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete a specific session"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    if chatbot_service.chatbot.memory.delete_session(session_id):
        return {"message": "✅ Session deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/{session_id}/clear")
async def clear_session(session_id: str):
    """Clear all messages in a specific session"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    # Switch to session first
    if not chatbot_service.chatbot.memory.switch_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    chatbot_service.chatbot.memory.clear_current_session()
    return {"message": "✅ Session messages cleared successfully"}


@router.patch("/{session_id}/title")
async def update_session_title(session_id: str, title: str):
    """Update session title"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    # Switch to session first
    if not chatbot_service.chatbot.memory.switch_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    chatbot_service.chatbot.memory.update_session_title(title)
    return {"message": "✅ Session title updated successfully", "new_title": title}


@router.get("/{session_id}/messages")
async def get_session_messages(session_id: str, limit: Optional[int] = 50):
    """Get messages from a specific session"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    session = chatbot_service.chatbot.memory.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = session.messages
    if limit:
        messages = messages[-limit:]

    return {
        "session_id": session_id,
        "session_title": session.title,
        "total_messages": len(session.messages),
        "returned_messages": len(messages),
        "messages": [
            {
                "id": msg.id,
                "role": msg.role.value,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "tool_calls": msg.tool_calls,
                "tool_call_id": msg.tool_call_id,
            }
            for msg in messages
        ],
    }


@router.get("/{session_id}/stats")
async def get_session_stats(session_id: str):
    """Get statistics for a specific session"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    # Switch to session to get stats
    if not chatbot_service.chatbot.memory.switch_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    stats = chatbot_service.chatbot.memory.get_session_stats()
    if "error" in stats:
        raise HTTPException(status_code=404, detail=stats["error"])

    return stats

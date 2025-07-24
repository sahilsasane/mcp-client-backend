"""
Memory management and health check API endpoints
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException

from ..core.config import get_chatbot_service
from ..models.schemas import MemoryStatsResponse

router = APIRouter(tags=["System"])


@router.get("/memory/stats", response_model=MemoryStatsResponse)
async def get_memory_stats():
    """Get comprehensive memory and system statistics"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    total_messages = sum(
        len(session.messages)
        for session in chatbot_service.chatbot.memory.sessions.values()
    )
    resources = chatbot_service.get_available_resources()
    total_resources = sum(len(res_list) for res_list in resources.values())

    return MemoryStatsResponse(
        total_sessions=len(chatbot_service.chatbot.memory.sessions),
        current_session_id=chatbot_service.chatbot.memory.current_session_id,
        total_messages=total_messages,
        active_tools=len(chatbot_service.chatbot.available_tools),
        active_prompts=len(chatbot_service.chatbot.available_prompts),
        active_resources=total_resources,
    )


@router.post("/memory/save")
async def save_memory():
    """Manually trigger memory save to disk"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    try:
        chatbot_service.chatbot.memory.save_memory()
        return {
            "message": "💾 Memory saved successfully",
            "timestamp": datetime.now().isoformat(),
            "sessions_saved": len(chatbot_service.chatbot.memory.sessions),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Comprehensive health check endpoint"""
    chatbot_service = get_chatbot_service()

    if not chatbot_service:
        return {
            "status": "unhealthy",
            "chatbot_initialized": False,
            "message": "ChatBot not initialized",
            "timestamp": datetime.now().isoformat(),
        }

    try:
        current_session = chatbot_service.chatbot.memory.get_current_session()
        resources = chatbot_service.get_available_resources()

        return {
            "status": "healthy",
            "chatbot_initialized": chatbot_service.is_initialized,
            "memory": {
                "total_sessions": len(chatbot_service.chatbot.memory.sessions),
                "current_session_id": chatbot_service.chatbot.memory.current_session_id,
                "current_session_title": current_session.title
                if current_session
                else None,
            },
            "mcp": {
                "available_tools": len(chatbot_service.chatbot.available_tools),
                "available_prompts": len(chatbot_service.chatbot.available_prompts),
                "available_resources": sum(
                    len(res_list) for res_list in resources.values()
                ),
            },
            "uptime": "Available via /health endpoint",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "status": "degraded",
            "chatbot_initialized": True,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@router.options("/health")
async def health_options():
    """Handle CORS preflight for health endpoint"""
    return {"message": "OK"}

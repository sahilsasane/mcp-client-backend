import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import the enhanced MCP client
from enhanced_mcp_client import EnhancedMCPChatBot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pydantic models for API requests/responses
class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    session_title: str
    tool_calls: List[Dict[str, Any]]
    timestamp: str
    message_count: int


class SessionCreateRequest(BaseModel):
    title: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: str
    last_activity: str
    message_count: int
    is_current: bool


class ResourceRequest(BaseModel):
    resource_uri: str


class ResourceResponse(BaseModel):
    resource_uri: str
    content: List[str]
    timestamp: str
    success: bool
    error: Optional[str] = None


class PromptRequest(BaseModel):
    prompt_name: str
    args: Dict[str, Any] = {}


class PromptResponse(BaseModel):
    prompt_name: str
    result: Optional[str]
    args_used: Dict[str, Any]
    timestamp: str
    success: bool
    error: Optional[str] = None


class MemoryStatsResponse(BaseModel):
    total_sessions: int
    current_session_id: Optional[str]
    total_messages: int
    active_tools: int
    active_prompts: int
    active_resources: int


# Global chatbot instance
chatbot: Optional[EnhancedMCPChatBot] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events using lifespan context manager"""
    global chatbot

    # Startup
    try:
        logger.info("🚀 Initializing Enhanced MCP ChatBot...")
        chatbot = EnhancedMCPChatBot()
        await chatbot.initialize()
        logger.info("✅ Enhanced MCP ChatBot initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize chatbot: {e}")
        # Don't raise here - let the app start but mark as unhealthy

    yield

    # Shutdown
    if chatbot:
        await chatbot.cleanup()
    logger.info("👋 FastAPI app shutdown and resources cleaned up")


# FastAPI app
app = FastAPI(
    title="Enhanced MCP ChatBot API",
    description="FastAPI backend for the Enhanced MCP ChatBot with persistent memory and session management",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Enhanced MCP ChatBot API",
        "version": "2.0.0",
        "status": "running",
        "description": "FastAPI backend for MCP ChatBot with persistent memory",
        "features": [
            "🧠 Persistent memory across sessions",
            "💬 Multiple chat sessions management",
            "🔧 MCP tool integration",
            "📚 Resource access",
            "💡 Prompt execution",
            "📊 Session analytics",
            "⚡ WebSocket real-time chat",
            "🔍 Health monitoring",
        ],
        "documentation": {"swagger_ui": "/docs", "redoc": "/redoc"},
        "key_endpoints": {
            "chat": "POST /chat",
            "sessions": "GET /sessions",
            "websocket": "WS /ws",
            "health": "GET /health",
        },
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a chat message and get response with memory persistence"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    try:
        result = await chatbot.process_query(request.query, request.session_id)

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
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.options("/chat")
async def chat_options():
    """Handle CORS preflight for chat endpoint"""
    return {"message": "OK"}


@app.post("/sessions")
async def create_session(request: SessionCreateRequest):
    """Create a new chat session"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    try:
        session_id = chatbot.memory.create_session(request.title)
        session = chatbot.memory.get_current_session()

        return {
            "session_id": session_id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "message": "✅ Session created successfully",
        }
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.options("/sessions")
async def sessions_options():
    """Handle CORS preflight for sessions endpoint"""
    return {"message": "OK"}


@app.get("/sessions", response_model=List[SessionResponse])
async def list_sessions():
    """List all chat sessions with metadata"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    try:
        sessions_data = chatbot.memory.list_sessions()
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
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}")
async def get_session_details(session_id: str):
    """Get detailed information about a specific session"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    session = chatbot.memory.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "last_activity": session.last_activity.isoformat(),
        "message_count": len(session.messages),
        "context": session.context,
        "is_current": session.id == chatbot.memory.current_session_id,
    }


@app.post("/sessions/{session_id}/switch")
async def switch_session(session_id: str):
    """Switch to a specific session"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    if chatbot.memory.switch_session(session_id):
        session = chatbot.memory.get_current_session()
        return {
            "message": f"✅ Switched to session: {session.title}",
            "session_id": session_id,
            "session_title": session.title,
            "message_count": len(session.messages),
        }
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a specific session"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    if chatbot.memory.delete_session(session_id):
        return {"message": "✅ Session deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@app.post("/sessions/{session_id}/clear")
async def clear_session(session_id: str):
    """Clear all messages in a specific session"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    # Switch to session first
    if not chatbot.memory.switch_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    chatbot.memory.clear_current_session()
    return {"message": "✅ Session messages cleared successfully"}


@app.patch("/sessions/{session_id}/title")
async def update_session_title(session_id: str, title: str):
    """Update session title"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    # Switch to session first
    if not chatbot.memory.switch_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    chatbot.memory.update_session_title(title)
    return {"message": "✅ Session title updated successfully", "new_title": title}


@app.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, limit: Optional[int] = 50):
    """Get messages from a specific session"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    session = chatbot.memory.sessions.get(session_id)
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


@app.get("/sessions/{session_id}/stats")
async def get_session_stats(session_id: str):
    """Get statistics for a specific session"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    # Switch to session to get stats
    if not chatbot.memory.switch_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    stats = chatbot.memory.get_session_stats()
    if "error" in stats:
        raise HTTPException(status_code=404, detail=stats["error"])

    return stats


@app.post("/resource", response_model=ResourceResponse)
async def get_resource(request: ResourceRequest):
    """Get content from a specific MCP resource"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    try:
        result = await chatbot.get_resource(request.resource_uri)
        return ResourceResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting resource: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/prompt", response_model=PromptResponse)
async def execute_prompt(request: PromptRequest):
    """Execute an MCP prompt with given arguments"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    try:
        result = await chatbot.execute_prompt(request.prompt_name, request.args)
        return PromptResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error executing prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools")
async def get_available_tools():
    """Get list of available MCP tools"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    tools = chatbot.get_available_tools()
    return {
        "tools": tools,
        "count": len(tools),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/prompts")
async def get_available_prompts():
    """Get list of available MCP prompts"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    prompts = chatbot.get_available_prompts()
    return {
        "prompts": prompts,
        "count": len(prompts),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/resources")
async def get_available_resources():
    """Get list of available MCP resources grouped by type"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    resources = chatbot.get_available_resources()
    total_count = sum(len(res_list) for res_list in resources.values())

    return {
        "resources": resources,
        "counts": {
            "gmail": len(resources["gmail"]),
            "project": len(resources["project"]),
            "company": len(resources["company"]),
            "total": total_count,
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/memory/stats", response_model=MemoryStatsResponse)
async def get_memory_stats():
    """Get comprehensive memory and system statistics"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    total_messages = sum(
        len(session.messages) for session in chatbot.memory.sessions.values()
    )
    resources = chatbot.get_available_resources()
    total_resources = sum(len(res_list) for res_list in resources.values())

    return MemoryStatsResponse(
        total_sessions=len(chatbot.memory.sessions),
        current_session_id=chatbot.memory.current_session_id,
        total_messages=total_messages,
        active_tools=len(chatbot.available_tools),
        active_prompts=len(chatbot.available_prompts),
        active_resources=total_resources,
    )


@app.post("/memory/save")
async def save_memory():
    """Manually trigger memory save to disk"""
    if not chatbot:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    try:
        chatbot.memory.save_memory()
        return {
            "message": "💾 Memory saved successfully",
            "timestamp": datetime.now().isoformat(),
            "sessions_saved": len(chatbot.memory.sessions),
        }
    except Exception as e:
        logger.error(f"Error saving memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint"""
    if not chatbot:
        return {
            "status": "unhealthy",
            "chatbot_initialized": False,
            "message": "ChatBot not initialized",
            "timestamp": datetime.now().isoformat(),
        }

    try:
        current_session = chatbot.memory.get_current_session()
        resources = chatbot.get_available_resources()

        return {
            "status": "healthy",
            "chatbot_initialized": chatbot._initialized,
            "memory": {
                "total_sessions": len(chatbot.memory.sessions),
                "current_session_id": chatbot.memory.current_session_id,
                "current_session_title": current_session.title
                if current_session
                else None,
            },
            "mcp": {
                "available_tools": len(chatbot.available_tools),
                "available_prompts": len(chatbot.available_prompts),
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


@app.options("/health")
async def health_options():
    """Handle CORS preflight for health endpoint"""
    return {"message": "OK"}


# WebSocket endpoint for real-time chat
@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat with full feature support"""
    await websocket.accept()

    if not chatbot:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "error",
                    "error": "ChatBot not initialized",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )
        await websocket.close()
        return

    logger.info("New WebSocket connection established")

    try:
        # Send welcome message
        await websocket.send_text(
            json.dumps(
                {
                    "type": "welcome",
                    "message": "🤖 Connected to Enhanced MCP ChatBot",
                    "features": [
                        "chat",
                        "session_management",
                        "tool_calls",
                        "resources",
                    ],
                    "current_session": {
                        "id": chatbot.memory.current_session_id,
                        "title": chatbot.memory.get_current_session().title
                        if chatbot.memory.get_current_session()
                        else None,
                    },
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                message_data = json.loads(data)
                message_type = message_data.get("type", "chat")

                if message_type == "chat":
                    query = message_data.get("query", "")
                    session_id = message_data.get("session_id")

                    if not query:
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "error",
                                    "error": "No query provided",
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )
                        )
                        continue

                    # Process the chat query
                    result = await chatbot.process_query(query, session_id)

                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "chat_response",
                                "response": result["response"],
                                "session_id": result["session_id"],
                                "session_title": result["session_title"],
                                "tool_calls": result["tool_calls"],
                                "message_count": result["message_count"],
                                "timestamp": result["timestamp"],
                            }
                        )
                    )

                elif message_type == "create_session":
                    title = message_data.get("title")
                    session_id = chatbot.memory.create_session(title)
                    session = chatbot.memory.get_current_session()

                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "session_created",
                                "session_id": session_id,
                                "title": session.title,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    )

                elif message_type == "switch_session":
                    session_id = message_data.get("session_id")
                    if chatbot.memory.switch_session(session_id):
                        session = chatbot.memory.get_current_session()
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "session_switched",
                                    "session_id": session_id,
                                    "title": session.title,
                                    "message_count": len(session.messages),
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )
                        )
                    else:
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "error",
                                    "error": "Session not found",
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )
                        )

                elif message_type == "list_sessions":
                    sessions = chatbot.memory.list_sessions()
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "sessions_list",
                                "sessions": sessions,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    )

                elif message_type == "get_resource":
                    resource_uri = message_data.get("resource_uri")
                    if resource_uri:
                        result = await chatbot.get_resource(resource_uri)
                        await websocket.send_text(
                            json.dumps({"type": "resource_response", **result})
                        )
                    else:
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "error",
                                    "error": "No resource_uri provided",
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )
                        )

                elif message_type == "ping":
                    await websocket.send_text(
                        json.dumps(
                            {"type": "pong", "timestamp": datetime.now().isoformat()}
                        )
                    )

                else:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "error": f"Unknown message type: {message_type}",
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    )

            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "error": "Invalid JSON format",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                )
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "error": str(e),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                )

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")


if __name__ == "__main__":
    uvicorn.run("server:app", port=8000, reload=True, log_level="info")

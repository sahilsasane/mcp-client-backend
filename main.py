"""
Enhanced MCP ChatBot API Server
Main entry point for the FastAPI application with organized structure.
"""

import uvicorn
from fastapi import WebSocket

from src.api.legacy import legacy_router
from src.api.routes import api_router
from src.core.config import create_app
from src.websocket.handler import WebSocketManager

# Create the FastAPI app
app = create_app()

# Include API routes (new versioned API)
app.include_router(api_router)

# Include legacy routes for backward compatibility
app.include_router(legacy_router)

# Create WebSocket manager
websocket_manager = WebSocketManager()


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
            "chat": "POST /api/v1/chat/",
            "sessions": "GET /api/v1/sessions/",
            "websocket": "WS /ws",
            "health": "GET /api/v1/health",
        },
    }


@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat with full feature support"""
    await websocket_manager.handle_websocket(websocket)


if __name__ == "__main__":
    uvicorn.run("main:app", port=8000, reload=True, log_level="info")

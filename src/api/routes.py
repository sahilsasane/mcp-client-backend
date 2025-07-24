"""
Main API router that includes all endpoint modules
"""

from fastapi import APIRouter

from .chat import router as chat_router
from .mcp import router as mcp_router
from .sessions import router as sessions_router
from .system import router as system_router

# Create main API router for versioned API
api_router = APIRouter(prefix="/api/v1")

# Include all sub-routers for the versioned API
api_router.include_router(chat_router)
api_router.include_router(sessions_router)
api_router.include_router(mcp_router)
api_router.include_router(system_router)

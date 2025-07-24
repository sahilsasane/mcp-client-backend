"""
Legacy API routes for backward compatibility
"""

from fastapi import APIRouter

from .chat import router as chat_router
from .mcp import router as mcp_router
from .sessions import router as sessions_router
from .system import router as system_router

# Create legacy router without prefix for backward compatibility
legacy_router = APIRouter()

# Include legacy routes directly (they already have the correct paths)
legacy_router.include_router(chat_router)
legacy_router.include_router(sessions_router)
legacy_router.include_router(mcp_router)
legacy_router.include_router(system_router)

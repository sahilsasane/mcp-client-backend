"""
Core application configuration and settings
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..services.chatbot_service import ChatBotService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global chatbot service instance
chatbot_service: Optional[ChatBotService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events using lifespan context manager"""
    global chatbot_service

    # Startup
    try:
        logger.info("🚀 Initializing Enhanced MCP ChatBot...")
        chatbot_service = ChatBotService()
        await chatbot_service.initialize()
        logger.info("✅ Enhanced MCP ChatBot initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize chatbot: {e}")
        # Don't raise here - let the app start but mark as unhealthy

    yield

    # Shutdown
    if chatbot_service:
        await chatbot_service.cleanup()
    logger.info("👋 FastAPI app shutdown and resources cleaned up")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
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

    return app


def get_chatbot_service() -> Optional[ChatBotService]:
    """Get the global chatbot service instance"""
    return chatbot_service

"""
WebSocket handler for real-time chat
"""

import json
import logging
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

from ..core.config import get_chatbot_service

logger = logging.getLogger(__name__)


class WebSocketManager:
    """WebSocket connection manager for real-time chat"""

    async def handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connection for real-time chat with full feature support"""
        await websocket.accept()

        chatbot_service = get_chatbot_service()
        if not chatbot_service or not chatbot_service.is_initialized:
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
                            "id": chatbot_service.chatbot.memory.current_session_id,
                            "title": chatbot_service.chatbot.memory.get_current_session().title
                            if chatbot_service.chatbot.memory.get_current_session()
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
                    await self._handle_message(websocket, message_data, chatbot_service)

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

    async def _handle_message(
        self, websocket: WebSocket, message_data: dict, chatbot_service
    ):
        """Handle individual WebSocket messages"""
        message_type = message_data.get("type", "chat")

        if message_type == "chat":
            await self._handle_chat_message(websocket, message_data, chatbot_service)
        elif message_type == "create_session":
            await self._handle_create_session(websocket, message_data, chatbot_service)
        elif message_type == "switch_session":
            await self._handle_switch_session(websocket, message_data, chatbot_service)
        elif message_type == "list_sessions":
            await self._handle_list_sessions(websocket, chatbot_service)
        elif message_type == "get_resource":
            await self._handle_get_resource(websocket, message_data, chatbot_service)
        elif message_type == "ping":
            await self._handle_ping(websocket)
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

    async def _handle_chat_message(
        self, websocket: WebSocket, message_data: dict, chatbot_service
    ):
        """Handle chat messages"""
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
            return

        # Process the chat query
        result = await chatbot_service.process_query(query, session_id)

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

    async def _handle_create_session(
        self, websocket: WebSocket, message_data: dict, chatbot_service
    ):
        """Handle session creation"""
        title = message_data.get("title")
        session_id = chatbot_service.chatbot.memory.create_session(title)
        session = chatbot_service.chatbot.memory.get_current_session()

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

    async def _handle_switch_session(
        self, websocket: WebSocket, message_data: dict, chatbot_service
    ):
        """Handle session switching"""
        session_id = message_data.get("session_id")
        if chatbot_service.chatbot.memory.switch_session(session_id):
            session = chatbot_service.chatbot.memory.get_current_session()
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

    async def _handle_list_sessions(self, websocket: WebSocket, chatbot_service):
        """Handle session listing"""
        sessions = chatbot_service.chatbot.memory.list_sessions()
        await websocket.send_text(
            json.dumps(
                {
                    "type": "sessions_list",
                    "sessions": sessions,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

    async def _handle_get_resource(
        self, websocket: WebSocket, message_data: dict, chatbot_service
    ):
        """Handle resource requests"""
        resource_uri = message_data.get("resource_uri")
        if resource_uri:
            result = await chatbot_service.get_resource(resource_uri)
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

    async def _handle_ping(self, websocket: WebSocket):
        """Handle ping messages"""
        await websocket.send_text(
            json.dumps({"type": "pong", "timestamp": datetime.now().isoformat()})
        )

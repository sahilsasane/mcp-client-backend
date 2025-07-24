"""
ChatBot service wrapper for the Enhanced MCP ChatBot
"""

import os

# Import from the root level (relative to project root)
import sys
from typing import Any, Dict, List, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from enhanced_mcp_client import EnhancedMCPChatBot


class ChatBotService:
    """Service wrapper for EnhancedMCPChatBot with additional functionality"""

    def __init__(self):
        self._chatbot: Optional[EnhancedMCPChatBot] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the MCP ChatBot"""
        self._chatbot = EnhancedMCPChatBot()
        await self._chatbot.initialize()
        self._initialized = True

    async def cleanup(self) -> None:
        """Cleanup the MCP ChatBot resources"""
        if self._chatbot:
            await self._chatbot.cleanup()
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if the chatbot is initialized"""
        return self._initialized and self._chatbot is not None

    @property
    def chatbot(self) -> EnhancedMCPChatBot:
        """Get the underlying chatbot instance"""
        if not self._chatbot:
            raise RuntimeError("ChatBot not initialized")
        return self._chatbot

    async def process_query(
        self, query: str, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a chat query"""
        return await self.chatbot.process_query(query, session_id)

    async def get_resource(self, resource_uri: str) -> Dict[str, Any]:
        """Get content from a specific MCP resource"""
        return await self.chatbot.get_resource(resource_uri)

    async def execute_prompt(
        self, prompt_name: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an MCP prompt with given arguments"""
        return await self.chatbot.execute_prompt(prompt_name, args)

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available MCP tools"""
        return self.chatbot.get_available_tools()

    def get_available_prompts(self) -> List[Dict[str, Any]]:
        """Get list of available MCP prompts"""
        return self.chatbot.get_available_prompts()

    def get_available_resources(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get list of available MCP resources grouped by type"""
        return self.chatbot.get_available_resources()

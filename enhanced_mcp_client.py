import asyncio
import json
import os
import pickle
import uuid
from contextlib import AsyncExitStack
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import nest_asyncio
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

nest_asyncio.apply()
load_dotenv()


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class ChatMessage:
    id: str
    role: MessageRole
    content: str
    timestamp: datetime
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ConversationSession:
    id: str
    title: str
    created_at: datetime
    last_activity: datetime
    messages: List[ChatMessage]
    context: Dict[str, Any]


class MemoryManager:
    def __init__(self, storage_file: str = "chat_memory.pkl", max_sessions: int = 50):
        self.storage_file = storage_file
        self.max_sessions = max_sessions
        self.sessions: Dict[str, ConversationSession] = {}
        self.current_session_id: Optional[str] = None
        self.load_memory()

    def create_session(self, title: str = None) -> str:
        session_id = str(uuid.uuid4())
        now = datetime.now()

        session = ConversationSession(
            id=session_id,
            title=title or f"Chat {now.strftime('%Y-%m-%d %H:%M')}",
            created_at=now,
            last_activity=now,
            messages=[],
            context={},
        )

        self.sessions[session_id] = session
        self.current_session_id = session_id
        self._cleanup_old_sessions()
        self.save_memory()

        return session_id

    def get_current_session(self) -> Optional[ConversationSession]:
        if not self.current_session_id:
            return None
        return self.sessions.get(self.current_session_id)

    def switch_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            self.current_session_id = session_id
            self.sessions[session_id].last_activity = datetime.now()
            self.save_memory()
            return True
        return False

    def add_message(self, message: ChatMessage):
        if not self.current_session_id:
            self.create_session()

        session = self.sessions.get(self.current_session_id)
        if session:
            session.messages.append(message)
            session.last_activity = datetime.now()
            self.save_memory()

    def get_conversation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        session = self.get_current_session()
        if not session:
            return []

        messages = []
        for msg in session.messages[-limit:]:
            if msg.role == MessageRole.TOOL:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                )
            else:
                message_dict = {"role": msg.role.value, "content": msg.content}
                if msg.tool_calls:
                    message_dict["tool_calls"] = msg.tool_calls
                messages.append(message_dict)

        return messages

    def list_sessions(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": session.id,
                "title": session.title,
                "created_at": session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "last_activity": session.last_activity.strftime("%Y-%m-%d %H:%M:%S"),
                "message_count": len(session.messages),
                "is_current": session.id == self.current_session_id,
            }
            for session in sorted(
                self.sessions.values(), key=lambda s: s.last_activity, reverse=True
            )
        ]

    def delete_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            if self.current_session_id == session_id:
                # Switch to most recent session or create new one
                recent_sessions = sorted(
                    self.sessions.values(), key=lambda s: s.last_activity, reverse=True
                )
                self.current_session_id = (
                    recent_sessions[0].id if recent_sessions else None
                )
            self.save_memory()
            return True
        return False

    def clear_current_session(self):
        session = self.get_current_session()
        if session:
            session.messages.clear()
            self.save_memory()

    def update_session_title(self, title: str):
        session = self.get_current_session()
        if session:
            session.title = title
            self.save_memory()

    def get_session_stats(self) -> Dict[str, Any]:
        session = self.get_current_session()
        if not session:
            return {"error": "No active session"}

        tool_calls = sum(1 for msg in session.messages if msg.role == MessageRole.TOOL)
        user_messages = sum(
            1 for msg in session.messages if msg.role == MessageRole.USER
        )
        assistant_messages = sum(
            1 for msg in session.messages if msg.role == MessageRole.ASSISTANT
        )

        return {
            "session_id": session.id,
            "title": session.title,
            "total_messages": len(session.messages),
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "tool_calls": tool_calls,
            "created_at": session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "duration": str(datetime.now() - session.created_at).split(".")[0],
        }

    def save_memory(self):
        try:
            # Convert to serializable format
            data = {}
            for session_id, session in self.sessions.items():
                data[session_id] = {
                    "id": session.id,
                    "title": session.title,
                    "created_at": session.created_at.isoformat(),
                    "last_activity": session.last_activity.isoformat(),
                    "context": session.context,
                    "messages": [
                        {
                            "id": msg.id,
                            "role": msg.role.value,
                            "content": msg.content,
                            "timestamp": msg.timestamp.isoformat(),
                            "tool_calls": msg.tool_calls,
                            "tool_call_id": msg.tool_call_id,
                        }
                        for msg in session.messages
                    ],
                }

            save_data = {
                "sessions": data,
                "current_session_id": self.current_session_id,
            }

            with open(self.storage_file, "wb") as f:
                pickle.dump(save_data, f)
        except Exception as e:
            print(f"Error saving memory: {e}")

    def load_memory(self):
        try:
            if not os.path.exists(self.storage_file):
                return

            with open(self.storage_file, "rb") as f:
                data = pickle.load(f)

            # Restore sessions
            for session_id, session_data in data.get("sessions", {}).items():
                messages = []
                for msg_data in session_data["messages"]:
                    messages.append(
                        ChatMessage(
                            id=msg_data["id"],
                            role=MessageRole(msg_data["role"]),
                            content=msg_data["content"],
                            timestamp=datetime.fromisoformat(msg_data["timestamp"]),
                            tool_calls=msg_data.get("tool_calls"),
                            tool_call_id=msg_data.get("tool_call_id"),
                        )
                    )

                self.sessions[session_id] = ConversationSession(
                    id=session_data["id"],
                    title=session_data["title"],
                    created_at=datetime.fromisoformat(session_data["created_at"]),
                    last_activity=datetime.fromisoformat(session_data["last_activity"]),
                    messages=messages,
                    context=session_data.get("context", {}),
                )

            self.current_session_id = data.get("current_session_id")

        except Exception as e:
            print(f"Error loading memory: {e}")
            self.sessions = {}
            self.current_session_id = None

    def _cleanup_old_sessions(self):
        if len(self.sessions) > self.max_sessions:
            # Keep the most recent sessions
            sorted_sessions = sorted(
                self.sessions.items(), key=lambda x: x[1].last_activity, reverse=True
            )
            sessions_to_keep = dict(sorted_sessions[: self.max_sessions])
            self.sessions = sessions_to_keep


class EnhancedMCPChatBot:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.openai = OpenAI()
        self.available_tools = []
        self.available_prompts = []
        self.sessions = {}
        self.memory = MemoryManager()
        self._initialized = False

    async def initialize(self):
        """Initialize the chatbot by connecting to MCP servers"""
        if self._initialized:
            return

        try:
            await self.connect_to_servers()
            # Auto-create session if none exists
            if not self.memory.current_session_id:
                self.memory.create_session("New Chat")
            self._initialized = True
        except Exception as e:
            print(f"Failed to initialize MCP ChatBot: {e}")
            raise

    async def connect_to_server(self, server_name: str, server_config: Dict):
        try:
            server_params = StdioServerParameters(**server_config)
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()

            try:
                # List available tools
                response = await session.list_tools()
                for tool in response.tools:
                    self.sessions[tool.name] = session
                    self.available_tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.inputSchema,
                            },
                        }
                    )

                # List available prompts
                prompts_response = await session.list_prompts()
                if prompts_response and prompts_response.prompts:
                    for prompt in prompts_response.prompts:
                        self.sessions[prompt.name] = session
                        self.available_prompts.append(
                            {
                                "name": prompt.name,
                                "description": prompt.description,
                                "arguments": prompt.arguments,
                            }
                        )

                # List available resources
                resources_response = await session.list_resources()
                if resources_response and resources_response.resources:
                    for resource in resources_response.resources:
                        resource_uri = str(resource.uri)
                        self.sessions[resource_uri] = session

            except Exception as e:
                print(f"Error listing tools/prompts/resources for {server_name}: {e}")

        except Exception as e:
            print(f"Error connecting to {server_name}: {e}")
            raise

    async def connect_to_servers(self):
        try:
            with open("server_config.json", "r") as file:
                data = json.load(file)
            servers = data.get("mcpServers", {})
            for server_name, server_config in servers.items():
                await self.connect_to_server(server_name, server_config)
        except FileNotFoundError:
            print(
                "Warning: server_config.json not found. No MCP servers will be connected."
            )
        except Exception as e:
            print(f"Error loading server config: {e}")
            raise

    async def process_query(
        self, query: str, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a query and return the response data"""
        if not self._initialized:
            await self.initialize()

        # Handle session switching
        if session_id:
            if not self.memory.switch_session(session_id):
                raise ValueError(f"Session {session_id} not found")
        elif not self.memory.current_session_id:
            self.memory.create_session()

        query = query.strip()
        if not query:
            return {
                "response": "Empty query received",
                "session_id": self.memory.current_session_id,
                "session_title": self.memory.get_current_session().title
                if self.memory.get_current_session()
                else None,
                "tool_calls": [],
                "timestamp": datetime.now().isoformat(),
                "message_count": len(self.memory.get_current_session().messages)
                if self.memory.get_current_session()
                else 0,
                "command_type": "empty",
            }

        # Handle memory management commands
        if query.startswith("/"):
            return await self._handle_memory_commands(query)

        # Handle resource commands
        if query.startswith("@"):
            return await self._handle_resource_commands(query)

        # Handle regular chat query
        return await self._process_chat_query(query)

    async def _handle_memory_commands(self, query: str) -> Dict[str, Any]:
        """Handle memory management commands"""
        parts = query.split()
        command = parts[0].lower()
        current_session = self.memory.get_current_session()

        try:
            if command == "/sessions":
                sessions = self.memory.list_sessions()
                if not sessions:
                    response = "No sessions found."
                else:
                    response = "📋 Chat Sessions:\n"
                    for i, session in enumerate(sessions[:10], 1):
                        current_marker = "👉 " if session["is_current"] else "   "
                        response += f"{current_marker}{i}. {session['title']}\n"
                        response += f"     ID: {session['id'][:8]}... | Messages: {session['message_count']} | Last: {session['last_activity']}\n"

            elif command == "/new":
                title = " ".join(parts[1:]) if len(parts) > 1 else None
                session_id = self.memory.create_session(title)
                response = (
                    f"✅ Created new session: {self.memory.get_current_session().title}"
                )

            elif command == "/switch":
                if len(parts) < 2:
                    response = "❌ Usage: /switch <session_id>"
                else:
                    session_id = parts[1]
                    matching_sessions = [
                        s
                        for s in self.memory.sessions.keys()
                        if s.startswith(session_id)
                    ]
                    if len(matching_sessions) == 1:
                        if self.memory.switch_session(matching_sessions[0]):
                            session = self.memory.get_current_session()
                            response = f"✅ Switched to: {session.title}"
                        else:
                            response = "❌ Failed to switch session"
                    elif len(matching_sessions) > 1:
                        response = f"❌ Multiple sessions match '{session_id}'. Be more specific."
                    else:
                        response = f"❌ Session '{session_id}' not found"

            elif command == "/delete":
                if len(parts) < 2:
                    response = "❌ Usage: /delete <session_id>"
                else:
                    session_id = parts[1]
                    matching_sessions = [
                        s
                        for s in self.memory.sessions.keys()
                        if s.startswith(session_id)
                    ]
                    if len(matching_sessions) == 1:
                        if self.memory.delete_session(matching_sessions[0]):
                            response = "✅ Session deleted"
                        else:
                            response = "❌ Failed to delete session"
                    else:
                        response = f"❌ Session '{session_id}' not found or ambiguous"

            elif command == "/clear":
                self.memory.clear_current_session()
                response = "✅ Current session cleared"

            elif command == "/title":
                if len(parts) < 2:
                    response = "❌ Usage: /title <new_title>"
                else:
                    title = " ".join(parts[1:])
                    self.memory.update_session_title(title)
                    response = f"✅ Session title updated to: {title}"

            elif command == "/stats":
                stats = self.memory.get_session_stats()
                if "error" in stats:
                    response = f"❌ {stats['error']}"
                else:
                    response = f"""📊 Session Statistics:
    Title: {stats["title"]}
    Total Messages: {stats["total_messages"]}
    User Messages: {stats["user_messages"]}
    Assistant Messages: {stats["assistant_messages"]}
    Tool Calls: {stats["tool_calls"]}
    Created: {stats["created_at"]}
    Duration: {stats["duration"]}"""

            elif command == "/history":
                limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
                session = self.memory.get_current_session()
                if session:
                    response = f"📜 Last {limit} messages:\n"
                    for msg in session.messages[-limit:]:
                        role_emoji = {
                            "user": "👤",
                            "assistant": "🤖",
                            "tool": "🔧",
                        }.get(msg.role.value, "❓")
                        timestamp = msg.timestamp.strftime("%H:%M:%S")
                        content_preview = msg.content[:100] + (
                            "..." if len(msg.content) > 100 else ""
                        )
                        response += f"{role_emoji} [{timestamp}] {content_preview}\n"
                else:
                    response = "❌ No active session"

            elif command == "/tools":
                if self.available_tools:
                    response = f"🔧 Available Tools ({len(self.available_tools)}):\n"
                    for tool in self.available_tools:
                        func = tool["function"]
                        response += f"- {func['name']}: {func['description']}\n"
                else:
                    response = "No tools available."

            elif command == "/resources":
                resources = self.get_available_resources()
                if not any(resources.values()):
                    response = "No resources available."
                else:
                    response = "📚 Available resources:\n"
                    if resources["gmail"]:
                        response += "\n📧 Gmail resources:\n"
                        response += (
                            "- meeting-emails: Get recent meeting-related emails\n"
                        )
                        response += "- processed-meetings: Get processed meeting data\n"
                        response += "- meeting-emails/{email_id}: Get specific meeting email by ID\n"

                    if resources["project"]:
                        response += "\n📋 Project resources:\n"
                        response += "- info: Get project information from the knowledge repository\n"
                        response += "- feature-updates: Get feature updates from the knowledge repository\n"
                        response += "- status: Get project status from the knowledge repository\n"

                    if resources["company"]:
                        response += "\n🏢 Company resources:\n"
                        response += "- info: Get company information from the knowledge repository\n"
                        response += "- solution-info: Get solution information from the knowledge repository\n"
                        response += "- all-info: Get all company information from the knowledge repository\n"
                        response += "- docs: Get company documents from the knowledge repository\n"

            elif command == "/prompts":
                if self.available_prompts:
                    response = "💡 Available prompts:\n"
                    for prompt in self.available_prompts:
                        response += f"- {prompt['name']}: {prompt['description']}\n"
                        if prompt["arguments"]:
                            response += "  Arguments:\n"
                            for arg in prompt["arguments"]:
                                arg_name = (
                                    arg.name
                                    if hasattr(arg, "name")
                                    else arg.get("name", "")
                                )
                                response += f"    - {arg_name}\n"
                else:
                    response = "No prompts available."

            elif command == "/prompt":
                if len(parts) < 2:
                    response = "❌ Usage: /prompt <name> <arg1=value1> <arg2=value2>"
                else:
                    prompt_name = parts[1]
                    args = {}
                    for arg in parts[2:]:
                        if "=" in arg:
                            key, value = arg.split("=", 1)
                            args[key] = value

                    result = await self.execute_prompt(prompt_name, args)
                    if result["success"]:
                        # Process the prompt result as a chat query
                        return await self._process_chat_query(result["result"])
                    else:
                        response = f"❌ Error executing prompt: {result.get('error', 'Unknown error')}"

            elif command == "/help":
                response = self._get_help_text()

            else:
                response = f"❌ Unknown command: {command}. Type '/help' for available commands."

        except Exception as e:
            response = f"❌ Error processing command: {str(e)}"

        return {
            "response": response,
            "session_id": current_session.id if current_session else None,
            "session_title": current_session.title if current_session else None,
            "tool_calls": [],
            "timestamp": datetime.now().isoformat(),
            "message_count": len(current_session.messages) if current_session else 0,
            "command_type": "memory_command",
        }

    async def _handle_resource_commands(self, query: str) -> Dict[str, Any]:
        """Handle resource commands"""
        resource_uri = self._parse_resource_command(query)
        current_session = self.memory.get_current_session()

        if resource_uri:
            result = await self.get_resource(resource_uri)
            if result["success"]:
                # Format the resource content as response
                content_text = (
                    "\n".join(result["content"])
                    if isinstance(result["content"], list)
                    else str(result["content"])
                )
                response = f"📄 Resource: {resource_uri}\n\nContent:\n{content_text}"
            else:
                response = f"❌ Error accessing resource: {result.get('error', 'Unknown error')}"
        else:
            response = f"❌ Unknown resource: {query[1:]}\nUse '/resources' to see all available resources"

        return {
            "response": response,
            "session_id": current_session.id if current_session else None,
            "session_title": current_session.title if current_session else None,
            "tool_calls": [],
            "timestamp": datetime.now().isoformat(),
            "message_count": len(current_session.messages) if current_session else 0,
            "command_type": "resource_command",
        }

    def _parse_resource_command(self, query: str) -> Optional[str]:
        """Parse @resource command and return appropriate URI"""
        resource_identifier = query[1:]

        # Gmail resources
        if resource_identifier == "meeting-emails":
            return "gmail://meeting-emails"
        elif resource_identifier == "processed-meetings":
            return "gmail://processed-meetings"
        elif resource_identifier.startswith("meeting-emails/"):
            email_id = resource_identifier.split("/", 1)[1]
            return f"gmail://meeting-emails/{email_id}"

        # Project resources
        elif resource_identifier == "project-info":
            return "project://info"
        elif resource_identifier == "feature-updates":
            return "project://feature-updates"
        elif resource_identifier == "project-status":
            return "project://status"

        # Company resources
        elif resource_identifier == "company-info":
            return "company://info"
        elif resource_identifier == "solution-info":
            return "company://solution-info"
        elif resource_identifier == "company-all-info":
            return "company://all-info"
        elif resource_identifier == "company-docs":
            return "company://docs"

        return None

    def _get_help_text(self) -> str:
        """Return help text"""
        return """🤖 ENHANCED MCP CHATBOT - HELP
    ════════════════════════════════════════════════════════════

    📝 MEMORY COMMANDS:
    /sessions          - List all chat sessions
    /new [title]       - Create new session
    /switch <id>       - Switch to session
    /delete <id>       - Delete session
    /clear             - Clear current session
    /title <title>     - Set session title
    /stats             - Show session statistics
    /history [n]       - Show last n messages

    📚 RESOURCE COMMANDS:
    @meeting-emails           - Get recent meeting emails
    @processed-meetings       - Get processed meeting data
    @meeting-emails/<id>      - Get specific meeting email
    @project-info             - Get project information
    @feature-updates          - Get feature updates
    @project-status           - Get project status
    @company-info             - Get company information
    @solution-info            - Get solution information
    @company-all-info         - Get all company info
    @company-docs             - Get company documents

    🔧 SYSTEM COMMANDS:
    /resources         - List available resources
    /prompts           - List available prompts
    /prompt <name>     - Execute a prompt
    /tools             - List available tools
    /help              - Show this help

    💬 CHAT:
    Just type your message to chat normally!
    ════════════════════════════════════════════════════════════"""

    async def _process_chat_query(self, query: str) -> Dict[str, Any]:
        """Process a regular chat query (the original process_query logic)"""
        # Add user message to memory
        user_message = ChatMessage(
            id=str(uuid.uuid4()),
            role=MessageRole.USER,
            content=query,
            timestamp=datetime.now(),
        )
        self.memory.add_message(user_message)

        # Get conversation history
        messages = self.memory.get_conversation_history(limit=10)
        messages.append({"role": "user", "content": query})

        assistant_responses = []
        tool_calls_made = []
        process_query = True

        while process_query:
            try:
                response = self.openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=self.available_tools if self.available_tools else None,
                    tool_choice="auto" if self.available_tools else None,
                    max_tokens=2024,
                )

                response_message = response.choices[0].message

                # Add assistant message to memory
                assistant_message = ChatMessage(
                    id=str(uuid.uuid4()),
                    role=MessageRole.ASSISTANT,
                    content=response_message.content or "",
                    timestamp=datetime.now(),
                    tool_calls=[
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in response_message.tool_calls
                    ]
                    if response_message.tool_calls
                    else None,
                )
                self.memory.add_message(assistant_message)

                messages.append(response_message.model_dump())

                if response_message.content:
                    assistant_responses.append(response_message.content)

                if response_message.tool_calls:
                    for tool_call in response_message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        tool_id = tool_call.id

                        tool_call_info = {
                            "tool_name": tool_name,
                            "tool_args": tool_args,
                            "tool_id": tool_id,
                            "success": False,
                            "result": None,
                            "error": None,
                        }

                        session = self.sessions.get(tool_name)

                        if not session:
                            error_msg = f"Tool '{tool_name}' not found."
                            tool_call_info["error"] = error_msg

                            tool_result = ChatMessage(
                                id=str(uuid.uuid4()),
                                role=MessageRole.TOOL,
                                content=error_msg,
                                timestamp=datetime.now(),
                                tool_call_id=tool_id,
                            )
                            self.memory.add_message(tool_result)

                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_id,
                                    "content": error_msg,
                                }
                            )
                        else:
                            try:
                                result = await session.call_tool(
                                    tool_name, arguments=tool_args
                                )
                                tool_content = (
                                    result.content
                                    if hasattr(result, "content")
                                    else str(result)
                                )

                                tool_call_info["success"] = True
                                tool_call_info["result"] = tool_content

                                tool_result = ChatMessage(
                                    id=str(uuid.uuid4()),
                                    role=MessageRole.TOOL,
                                    content=tool_content,
                                    timestamp=datetime.now(),
                                    tool_call_id=tool_id,
                                )
                                self.memory.add_message(tool_result)

                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tool_id,
                                        "content": tool_content,
                                    }
                                )
                            except Exception as e:
                                error_msg = f"Error calling tool {tool_name}: {str(e)}"
                                tool_call_info["error"] = error_msg

                                tool_result = ChatMessage(
                                    id=str(uuid.uuid4()),
                                    role=MessageRole.TOOL,
                                    content=error_msg,
                                    timestamp=datetime.now(),
                                    tool_call_id=tool_id,
                                )
                                self.memory.add_message(tool_result)

                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": tool_id,
                                        "content": error_msg,
                                    }
                                )

                        tool_calls_made.append(tool_call_info)
                else:
                    process_query = False

            except Exception as e:
                raise Exception(f"Error in process_query: {str(e)}")

        # Get current session info
        current_session = self.memory.get_current_session()

        return {
            "response": "\n".join(assistant_responses)
            if assistant_responses
            else "Query processed successfully",
            "session_id": current_session.id if current_session else None,
            "session_title": current_session.title if current_session else None,
            "tool_calls": tool_calls_made,
            "timestamp": datetime.now().isoformat(),
            "message_count": len(current_session.messages) if current_session else 0,
            "command_type": "chat",
        }

    async def get_resource(self, resource_uri: str) -> Dict[str, Any]:
        """Get a resource and return the content"""
        if not self._initialized:
            await self.initialize()

        session = self.sessions.get(resource_uri)

        # Fallback logic for different resource types
        if not session:
            for uri, sess in self.sessions.items():
                if (
                    (resource_uri.startswith("gmail://") and uri.startswith("gmail://"))
                    or (
                        resource_uri.startswith("project://")
                        and uri.startswith("project://")
                    )
                    or (
                        resource_uri.startswith("company://")
                        and uri.startswith("company://")
                    )
                ):
                    session = sess
                    break

        if not session:
            raise ValueError(f"Resource '{resource_uri}' not found")

        try:
            result = await session.read_resource(uri=resource_uri)
            content_list = []

            if result and result.contents:
                for content in result.contents:
                    if hasattr(content, "text"):
                        content_list.append(content.text)
                    else:
                        content_list.append(str(content))
            else:
                content_list.append("No content available.")

            return {
                "resource_uri": resource_uri,
                "content": content_list,
                "timestamp": datetime.now().isoformat(),
                "success": True,
            }

        except Exception as e:
            return {
                "resource_uri": resource_uri,
                "content": [],
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "success": False,
            }

    async def execute_prompt(
        self, prompt_name: str, args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a prompt and return the result"""
        if not self._initialized:
            await self.initialize()

        session = self.sessions.get(prompt_name)
        if not session:
            raise ValueError(f"Prompt '{prompt_name}' not found")

        try:
            result = await session.get_prompt(prompt_name, arguments=args)

            if result and result.messages:
                prompt_content = result.messages[0].content

                # Extract text from content
                if isinstance(prompt_content, str):
                    text_content = prompt_content
                elif hasattr(prompt_content, "text"):
                    text_content = prompt_content.text
                else:
                    text_content = " ".join(
                        item.text if hasattr(item, "text") else str(item)
                        for item in prompt_content
                    )

                return {
                    "prompt_name": prompt_name,
                    "result": text_content,
                    "args_used": args,
                    "timestamp": datetime.now().isoformat(),
                    "success": True,
                }
            else:
                return {
                    "prompt_name": prompt_name,
                    "result": "No content generated from prompt",
                    "args_used": args,
                    "timestamp": datetime.now().isoformat(),
                    "success": True,
                }

        except Exception as e:
            return {
                "prompt_name": prompt_name,
                "result": None,
                "args_used": args,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "success": False,
            }

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Return available tools"""
        return self.available_tools

    def get_available_prompts(self) -> List[Dict[str, Any]]:
        """Return available prompts"""
        return self.available_prompts

    def get_available_resources(self) -> Dict[str, List[str]]:
        """Return available resources grouped by type"""
        gmail_resources = [
            uri for uri in self.sessions.keys() if uri.startswith("gmail://")
        ]
        project_resources = [
            uri for uri in self.sessions.keys() if uri.startswith("project://")
        ]
        company_resources = [
            uri for uri in self.sessions.keys() if uri.startswith("company://")
        ]

        return {
            "gmail": gmail_resources,
            "project": project_resources,
            "company": company_resources,
        }

    async def cleanup(self):
        """Cleanup resources"""
        await self.exit_stack.aclose()

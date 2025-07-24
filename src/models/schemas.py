"""
Pydantic models for API requests and responses
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


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

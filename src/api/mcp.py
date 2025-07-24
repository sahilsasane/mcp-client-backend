"""
MCP (Model Context Protocol) related API endpoints
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException

from ..core.config import get_chatbot_service
from ..models.schemas import (
    PromptRequest,
    PromptResponse,
    ResourceRequest,
    ResourceResponse,
)

router = APIRouter(tags=["MCP"])


@router.post("/resource", response_model=ResourceResponse)
async def get_resource(request: ResourceRequest):
    """Get content from a specific MCP resource"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    try:
        result = await chatbot_service.get_resource(request.resource_uri)
        return ResourceResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prompt", response_model=PromptResponse)
async def execute_prompt(request: PromptRequest):
    """Execute an MCP prompt with given arguments"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    try:
        result = await chatbot_service.execute_prompt(request.prompt_name, request.args)
        return PromptResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools")
async def get_available_tools():
    """Get list of available MCP tools"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    tools = chatbot_service.get_available_tools()
    return {
        "tools": tools,
        "count": len(tools),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/prompts")
async def get_available_prompts():
    """Get list of available MCP prompts"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    prompts = chatbot_service.get_available_prompts()
    return {
        "prompts": prompts,
        "count": len(prompts),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/resources")
async def get_available_resources():
    """Get list of available MCP resources grouped by type"""
    chatbot_service = get_chatbot_service()
    if not chatbot_service or not chatbot_service.is_initialized:
        raise HTTPException(status_code=503, detail="ChatBot not initialized")

    resources = chatbot_service.get_available_resources()
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

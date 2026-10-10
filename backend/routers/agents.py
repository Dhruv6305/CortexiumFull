"""
Cortexium 2.0 — Agents Router
Handles AI agent queries with LLM + context injection.
Improved: WS broadcast, better system prompt, LLM status endpoint.
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..ai.llm_client import llm_client
from ..auth.supabase_auth import get_current_user
from ..routers.ws_hub import connection_manager
from ..core.session_manager import session_manager

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentQuery(BaseModel):
    query: str
    context: dict = {}
    session_id: Optional[str] = "global"
    agent: Optional[str] = "orchestrator"  # navigation | social | environment | orchestrator


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

@router.get("/status")
async def agents_status():
    stats = session_manager.get_stats()
    return {
        "status": "online",
        "active_agents": ["navigation", "social", "environment", "memory", "adaptive"],
        "llm": llm_client.status,
        "session_stats": stats,
    }


# ------------------------------------------------------------------
# Agent Query
# ------------------------------------------------------------------

@router.post("/ask")
async def ask_agent(data: AgentQuery, current_user=Depends(get_current_user)):
    """
    Routes a query to the appropriate AI agent.
    Provides scene context from the active session automatically.
    """
    # Build session context
    session = session_manager.get_session(data.session_id) if data.session_id else None
    session_ctx = {}
    if session:
        session_ctx = {
            "persons_seen": session.persons_seen,
            "objects_in_scene": session.objects_seen,
            "total_events": session.total_events,
        }

    merged_context = {**session_ctx, **data.context}

    # Pick system prompt based on agent type
    system_prompts = {
        "navigation": (
            "You are Cortexium's Navigation Agent. Analyze scene context and provide "
            "concise, actionable navigation guidance. Focus on spatial awareness, "
            "hazard detection, and route suggestions. Keep responses under 2 sentences."
        ),
        "social": (
            "You are Cortexium's Social Context Agent. Analyze face recognition events "
            "and conversation context. Provide relationship insights, name tags, and "
            "conversation starters. Keep responses under 2 sentences."
        ),
        "environment": (
            "You are Cortexium's Environment Agent. Analyze detected objects and scene "
            "context. Flag hazards, identify locations, and provide environmental alerts. "
            "Keep responses under 2 sentences."
        ),
        "orchestrator": (
            "You are the Cortexium 2.0 Agentic AI Orchestrator. "
            "Analyze CV events (objects, faces, locations) and provide helpful, "
            "action-oriented reasoning for an XR overlay. Keep responses concise and direct."
        ),
    }
    system_prompt = system_prompts.get(data.agent, system_prompts["orchestrator"])

    prompt = (
        f"User Query: {data.query}\nScene Context: {json.dumps(merged_context)}"
        if merged_context else data.query
    )

    response = await llm_client.generate_response(prompt, system_prompt)

    # Broadcast agent response to WS
    await connection_manager.broadcast({
        "event_type": "agent_response",
        "timestamp": datetime.utcnow().timestamp(),
        "session_id": data.session_id,
        "data": {
            "agent": data.agent,
            "query": data.query,
            "response": response,
        },
    })

    return {
        "agent": data.agent,
        "response": response,
        "user_id": current_user.id,
        "context_used": bool(merged_context),
        "llm_mode": llm_client.status.get("mode"),
    }


# ------------------------------------------------------------------
# LLM Health
# ------------------------------------------------------------------

@router.get("/llm/status")
async def llm_status():
    """Check the current LLM connectivity and provider information."""
    # Trigger a connectivity check (works for any provider)
    await llm_client._check_ollama()
    return llm_client.status


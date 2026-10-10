"""
Cortexium 2.0 — Memory Router
Manages encounter logs and person history.
Data is persisted locally via SessionManager — no Supabase required.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

from ..auth.supabase_auth import get_current_user
from ..core.session_manager import session_manager
from ..models.events import EncounterRecord

router = APIRouter(prefix="/api/memory", tags=["memory"])


class NewEncounterPayload(BaseModel):
    person_name: str
    session_id: str
    context: Optional[str] = None
    location: Optional[str] = None
    emotion: Optional[str] = None


# ------------------------------------------------------------------
# Encounters
# ------------------------------------------------------------------

@router.get("/encounters")
async def get_encounters(
    limit: int = Query(default=20, le=100),
    person_name: Optional[str] = Query(default=None),
    current_user=Depends(get_current_user),
):
    """
    Returns recent encounter records across all sessions.
    Optionally filter by person_name.
    """
    encounters = session_manager.get_all_encounters(limit=limit * 3)  # over-fetch for filter
    if person_name:
        encounters = [e for e in encounters if e.person_name.lower() == person_name.lower()]
    return {
        "encounters": [e.model_dump() for e in encounters[:limit]],
        "total": len(encounters[:limit]),
    }


@router.post("/encounters")
async def log_encounter(
    data: NewEncounterPayload,
    current_user=Depends(get_current_user),
):
    """Manually log an encounter record."""
    encounter = EncounterRecord(
        person_name=data.person_name,
        session_id=data.session_id,
        context=data.context,
        location=data.location,
        emotion=data.emotion,
        timestamp=datetime.utcnow().timestamp(),
    )
    session_manager.record_encounter(data.session_id, encounter)
    return {"success": True, "encounter": encounter.model_dump()}


# ------------------------------------------------------------------
# Persons
# ------------------------------------------------------------------

@router.get("/persons")
async def get_persons(current_user=Depends(get_current_user)):
    """Returns all unique persons seen across all sessions + in the face DB."""
    persons = session_manager.get_registered_persons()
    return {"persons": persons, "total": len(persons)}


# ------------------------------------------------------------------
# Session History
# ------------------------------------------------------------------

@router.get("/sessions")
async def get_sessions(current_user=Depends(get_current_user)):
    """Returns stats for all currently active sessions."""
    stats = session_manager.get_stats()
    return stats


@router.get("/sessions/history")
async def get_sessions_history(
    limit: int = Query(default=20, le=50),
    current_user=Depends(get_current_user),
):
    """Returns all persisted + active sessions sorted newest first, for the History tab."""
    sessions = session_manager.get_all_sessions(limit=limit)
    return {"sessions": sessions, "total": len(sessions)}


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: str, current_user=Depends(get_current_user)):
    """Ends a session: sets ended_at and persists it to disk."""
    session = session_manager.end_session(session_id)
    if not session:
        return {"success": True, "session_id": session_id, "already_ended": True}
    return {"success": True, "session_id": session_id, "ended_at": session.ended_at}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, current_user=Depends(get_current_user)):
    """Returns full summary for a specific session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return session.model_dump()


"""
Cortexium 2.0 — Local DB Router
Exposes the on-disk JSON store to the frontend for settings and profile management.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from ..db.database import local_db

router = APIRouter(prefix="/api/db", tags=["database"])


class SetValuePayload(BaseModel):
    key: str
    value: Any


# ------------------------------------------------------------------
# Settings
# ------------------------------------------------------------------

@router.get("/settings")
async def get_settings():
    """Return all current app settings."""
    return local_db.get_all("settings")


@router.patch("/settings")
async def update_settings(updates: dict):
    """Update one or more settings keys."""
    local_db.update("settings", updates)
    return {"success": True, "settings": local_db.get_all("settings")}


# ------------------------------------------------------------------
# User Profile
# ------------------------------------------------------------------

@router.get("/profile")
async def get_profile():
    """Return the local user profile."""
    return local_db.get_all("user_profile")


@router.patch("/profile")
async def update_profile(updates: dict):
    """Update user profile fields."""
    local_db.update("user_profile", updates)
    return {"success": True, "profile": local_db.get_all("user_profile")}


# ------------------------------------------------------------------
# Known Persons
# ------------------------------------------------------------------

@router.get("/persons")
async def get_known_persons():
    """Return the curated list of known persons."""
    return local_db.get("known_persons", "persons", default=[])


@router.post("/persons/{name}")
async def add_known_person(name: str):
    """Add a person to the known persons list."""
    persons = local_db.get("known_persons", "persons", default=[])
    if name not in persons:
        persons.append(name)
        local_db.set("known_persons", "persons", persons)
    return {"success": True, "persons": persons}


@router.delete("/persons/{name}")
async def remove_known_person(name: str):
    """Remove a person from the known persons list."""
    persons = local_db.get("known_persons", "persons", default=[])
    persons = [p for p in persons if p != name]
    local_db.set("known_persons", "persons", persons)
    return {"success": True, "persons": persons}


# ------------------------------------------------------------------
# DB info
# ------------------------------------------------------------------

@router.get("/status")
async def db_status():
    return {
        "type": "local-json",
        "path": local_db.db_path,
        "tables": ["settings", "user_profile", "known_persons"],
        "supabase": False,
        "redis": False,
    }

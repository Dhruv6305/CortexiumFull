"""
Cortexium 2.0 — Pydantic Event Schemas
All structured payloads flowing through the system use these models.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
import uuid


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class DetectedObject(BaseModel):
    cls: str = Field(..., alias="class")
    confidence: float
    bbox: List[float]

    class Config:
        populate_by_name = True


class FaceAnalysis(BaseModel):
    dominant_emotion: Optional[str] = None
    age: Optional[int] = None
    dominant_gender: Optional[str] = None
    emotion: Optional[Dict[str, float]] = None


class SceneEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str  # object_detected | face_recognized | face_unknown | intro_detected | agent_response
    session_id: str
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    data: Dict[str, Any] = {}
    confidence: Optional[float] = None


class EncounterRecord(BaseModel):
    encounter_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    person_name: str
    session_id: str
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    emotion: Optional[str] = None
    context: Optional[str] = None
    location: Optional[str] = None


class SessionSummary(BaseModel):
    session_id: str
    started_at: float
    ended_at: Optional[float] = None
    total_events: int = 0
    persons_seen: List[str] = []
    objects_seen: List[str] = []
    encounters: List[EncounterRecord] = []
    # Rich attributed transcript — each line tracks speaker, text, timestamp, emotion
    # Format: {"timestamp": "ISO", "speaker": "Name", "text": "...", "emotion": "neutral"}
    conversation_lines: List[Dict[str, Any]] = []


"""
Cortexium 2.0 — Session Manager (Singleton)
Tracks all active sessions in-memory and persists summaries to disk.
Sessions accumulate CV events and encounter records throughout their lifetime.
"""
import os
import json
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..models.events import SessionSummary, EncounterRecord, SceneEvent


# Base data directory — always relative to THIS file, not CWD
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SESSIONS_DIR = DATA_DIR / "sessions"


class SessionManager:
    """Singleton that manages all active and archived Cortexium sessions."""

    _instance: Optional["SessionManager"] = None
    _sessions: Dict[str, SessionSummary] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
            print(f"[SessionManager] Initialized. Sessions dir: {SESSIONS_DIR}")
        return cls._instance

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, session_id: Optional[str] = None) -> SessionSummary:
        sid = session_id or str(uuid.uuid4())
        session = SessionSummary(
            session_id=sid,
            started_at=datetime.utcnow().timestamp(),
        )
        self._sessions[sid] = session
        print(f"[SessionManager] Created session: {sid}")
        return session

    def get_or_create(self, session_id: str) -> SessionSummary:
        if session_id not in self._sessions:
            return self.create_session(session_id)
        return self._sessions[session_id]

    def get_session(self, session_id: str) -> Optional[SessionSummary]:
        return self._sessions.get(session_id)

    def end_session(self, session_id: str):
        session = self._sessions.get(session_id)
        if session:
            session.ended_at = datetime.utcnow().timestamp()
            self._persist_session(session)
            print(f"[SessionManager] Ended session: {session_id}")
            return session
        return None


    # ------------------------------------------------------------------
    # Event accumulation
    # ------------------------------------------------------------------

    def record_event(self, session_id: str, event: SceneEvent):
        session = self.get_or_create(session_id)
        session.total_events += 1

        if event.event_type == "object_detected":
            for obj in event.data.get("objects", []):
                cls = obj.get("class", "unknown")
                if cls not in session.objects_seen:
                    session.objects_seen.append(cls)

        elif event.event_type in ("face_recognized",):
            name = event.data.get("identity")
            if name and name not in session.persons_seen:
                session.persons_seen.append(name)

    def record_encounter(self, session_id: str, encounter: EncounterRecord):
        session = self.get_or_create(session_id)
        session.encounters.append(encounter)
        if encounter.person_name not in session.persons_seen:
            session.persons_seen.append(encounter.person_name)

    def add_attributed_line(
        self,
        session_id: str,
        speaker: str,
        text: str,
        emotion: str | None = None,
    ):
        """
        Append an attributed conversation line to the session transcript.
        Speaker should be the recognized person's name, or 'Unknown'.
        """
        session = self.get_or_create(session_id)
        line = {
            "timestamp": datetime.utcnow().isoformat(),
            "speaker": speaker.strip() if speaker else "Unknown",
            "text": text.strip(),
            "emotion": emotion or "neutral",
        }
        session.conversation_lines.append(line)
        # Auto-persist immediately so conversation lines are never lost
        self._persist_session(session)

    def add_conversation_line(self, session_id: str, speaker: str, text: str):
        """Legacy alias — redirects to add_attributed_line."""
        self.add_attributed_line(session_id, speaker, text)

    def get_session_transcript(self, session_id: str) -> str:
        """
        Returns the full attributed transcript for a session as a readable string.
        Handles both new dict format and old string format gracefully.
        """
        session = self.get_or_create(session_id)
        lines = []
        for line in session.conversation_lines:
            if isinstance(line, dict):
                speaker = line.get("speaker", "Unknown")
                text    = line.get("text", "")
                lines.append(f"{speaker}: {text}")
            elif isinstance(line, str):
                lines.append(line)  # legacy format
        return "\n".join(lines)


    # ------------------------------------------------------------------
    # Encounter history across sessions
    # ------------------------------------------------------------------

    def get_all_encounters(self, limit: int = 50) -> List[EncounterRecord]:
        """Returns recent encounters from all active sessions + persisted sessions."""
        encounters = []
        # From live sessions
        for session in self._sessions.values():
            encounters.extend(session.encounters)

        # From persisted sessions
        if SESSIONS_DIR.exists():
            for f in sorted(SESSIONS_DIR.glob("*.json"), reverse=True)[:10]:
                try:
                    data = json.loads(f.read_text())
                    session = SessionSummary(**data)
                    encounters.extend(session.encounters)
                except Exception:
                    pass

        # Deduplicate and sort by timestamp desc
        seen_ids = set()
        unique = []
        for e in sorted(encounters, key=lambda x: x.timestamp, reverse=True):
            if e.encounter_id not in seen_ids:
                seen_ids.add(e.encounter_id)
                unique.append(e)
        return unique[:limit]

    def get_registered_persons(self) -> List[str]:
        """Returns unique person names seen across all sessions."""
        persons = set()
        for session in self._sessions.values():
            persons.update(session.persons_seen)
        if SESSIONS_DIR.exists():
            for f in SESSIONS_DIR.glob("*.json"):
                try:
                    data = json.loads(f.read_text())
                    persons.update(data.get("persons_seen", []))
                except Exception:
                    pass
        return sorted(list(persons))

    def get_all_sessions(self, limit: int = 30) -> List[dict]:
        """Returns all persisted sessions sorted by start time (newest first)."""
        sessions = []
        if SESSIONS_DIR.exists():
            for f in sorted(SESSIONS_DIR.glob("*.json"), reverse=True)[:limit]:
                try:
                    data = json.loads(f.read_text())
                    sessions.append(data)
                except Exception:
                    pass
        # Also include live sessions that haven't been persisted yet
        for sid, session in self._sessions.items():
            if not any(s.get("session_id") == sid for s in sessions):
                sessions.append(session.model_dump())
        # Sort newest first
        sessions.sort(key=lambda s: s.get("started_at", 0), reverse=True)
        return sessions[:limit]


    # ------------------------------------------------------------------
    # Stats for adaptive insights
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        active_count = len(self._sessions)
        total_events = sum(s.total_events for s in self._sessions.values())
        all_persons = set()
        all_objects = set()
        for s in self._sessions.values():
            all_persons.update(s.persons_seen)
            all_objects.update(s.objects_seen)
        return {
            "active_sessions": active_count,
            "total_events_this_run": total_events,
            "unique_persons_seen": len(all_persons),
            "unique_objects_seen": len(all_objects),
            "persons": list(all_persons),
            "objects": list(all_objects),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_session(self, session: SessionSummary):
        try:
            fname = SESSIONS_DIR / f"{session.session_id}.json"
            fname.write_text(session.model_dump_json(indent=2))
        except Exception as e:
            print(f"[SessionManager] Persist error: {e}")


# Module-level singleton
session_manager = SessionManager()

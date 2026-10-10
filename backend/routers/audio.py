"""
Cortexium 2.0 — Audio / NLP Router
Processes transcribed speech to extract names and detect intents.
Uses LLM (Ollama) with regex fallback for offline operation.

Conversation saving:
  - When one or more recognized persons are present during transcription,
    the transcript is saved to EACH person's conversation file with
    the current session_id so summaries can be filtered per-session.
  - The session log receives a speaker-attributed line using the primary
    (first detected) person's name, or 'Unknown' if no face is recognized.
"""
import json
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict

from ..ai.llm_client import llm_client
from ..auth.supabase_auth import get_current_user
from ..routers.ws_hub import connection_manager
from ..core.session_manager import session_manager


router = APIRouter(prefix="/api/audio", tags=["audio"])


class TranscriptionData(BaseModel):
    text: str
    session_id: str
    language: Optional[str] = "en-US"

    # ── Multi-person fields (new) ──────────────────────────────────────────────
    # Full list of currently recognized persons (all visible faces)
    detected_persons: Optional[List[str]] = []
    # Per-person emotion: { "Aarya": "neutral", "Bob": "happy" }
    detected_emotions: Optional[Dict[str, str]] = {}

    # ── Legacy single-person fields (kept for backward compat) ────────────────
    detected_person: Optional[str] = None
    detected_emotion: Optional[str] = None


# ------------------------------------------------------------------
# Process Transcription (Name Extraction + Conversation Saving)
# ------------------------------------------------------------------

@router.post("/process-text")
async def process_transcription(data: TranscriptionData, current_user=Depends(get_current_user)):
    """
    Analyzes transcribed text to extract:
    - Person names from introductions
    - Navigation intent (e.g., "let's go to the lab")
    - Question intent (for agent routing)

    Additionally, saves the transcription as a conversation entry for every
    currently recognized person (all visible faces, not just the primary one).
    Each entry is tagged with session_id so the summary endpoint can filter
    to the current session only.
    """
    system_prompt = (
        "You are the Cortexium 2.0 NLP engine. "
        "Analyze the transcription and return ONLY a JSON object with these fields:\n"
        '- "name": string or null — person name if someone is introducing themselves\n'
        '- "intent": string or null — one of: "navigation", "question", "greeting", "registration", "other"\n'
        '- "confidence": float 0-1 — your confidence in the name extraction\n'
        "Examples:\n"
        "'I am John' -> {\"name\": \"John\", \"intent\": \"greeting\", \"confidence\": 0.95}\n"
        "'Hello, my name is Dr. Sarah' -> {\"name\": \"Sarah\", \"intent\": \"greeting\", \"confidence\": 0.9}\n"
        "'The weather is nice' -> {\"name\": null, \"intent\": \"other\", \"confidence\": 0.0}\n"
        "'Let\\'s go to the library' -> {\"name\": null, \"intent\": \"navigation\", \"confidence\": 0.85}\n"
        "Return ONLY the JSON object, no additional text."
    )

    prompt = f"Transcription: {data.text}"
    response_text = await llm_client.generate_response(prompt, system_prompt)

    # Parse LLM / fallback response
    extracted_name = None
    intent = "other"
    confidence = 0.0

    try:
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            extracted_name = parsed.get("name")
            intent = parsed.get("intent", "other")
            confidence = float(parsed.get("confidence", 0.0))
    except Exception as e:
        print(f"[Audio] LLM parse error: {e}. Raw: {response_text}")

    # ── Build the full list of persons to save to ────────────────────────────
    # Merge multi-person list + legacy single-person field, deduplicated
    all_persons: List[str] = []
    seen_names: set = set()
    for n in (data.detected_persons or []):
        key = n.strip().lower()
        if n.strip() and key not in seen_names:
            seen_names.add(key)
            all_persons.append(n.strip())
    if data.detected_person and data.detected_person.strip().lower() not in seen_names:
        all_persons.append(data.detected_person.strip())

    # If an introduction name was extracted, auto-register camera face image and notify WS
    if extracted_name:
        try:
            from ..cv.model_loader import model_loader
            latest = getattr(model_loader, "latest_frame", None)
            if latest is not None:
                print(f"[Audio] Auto-registering camera face image for voice intro '{extracted_name}'")
                reg_res = model_loader.register_person(latest, extracted_name)
                if reg_res.get("success"):
                    await connection_manager.broadcast({
                        "event_type": "person_registered",
                        "timestamp": datetime.utcnow().timestamp(),
                        "session_id": data.session_id,
                        "data": {"name": extracted_name},
                    })
        except Exception as err:
            print(f"[Audio] Failed to auto-register face image for '{extracted_name}': {err}")

    # If an introduction name was extracted and no face is recognized yet, use it
    if extracted_name and not all_persons:
        all_persons.append(extracted_name)

    # ── Session fallback if face detection flickered during speech ───────────
    if not all_persons and data.session_id:
        session = session_manager.get_session(data.session_id)
        if session and session.persons_seen:
            for n in session.persons_seen:
                if n.strip() and n.strip().lower() not in seen_names:
                    seen_names.add(n.strip().lower())
                    all_persons.append(n.strip())

    # ── Save transcript to EACH recognized person's conversation file ─────────
    saved_persons: List[str] = []
    if not data.text.strip():
        pass  # empty transcription, skip
    elif not all_persons:
        # No face recognized and no name extracted — speech cannot be attributed
        print(f"[Audio] No person detected — text NOT saved to any person file: '{data.text[:60]}'")
        print(f"[Audio]   detected_persons={data.detected_persons}  detected_person={data.detected_person}")
    else:
        try:
            from ..routers.persons import append_conversation_entry
            for person_name in all_persons:
                # Get this person's emotion (from dict, or legacy field)
                emotion = (data.detected_emotions or {}).get(person_name) or data.detected_emotion
                saved = append_conversation_entry(
                    name=person_name,
                    text=data.text,
                    source="voice",
                    emotion=emotion,
                    session_id=data.session_id,   # ← critical: ties entry to session
                )
                if saved:
                    saved_persons.append(person_name)
                    print(f"[Audio] ✓ Saved '{data.text[:50]}' → {person_name} (session={data.session_id})")
                else:
                    print(f"[Audio] '{person_name}' not in known_persons — not saved. Register face first.")
        except Exception as e:
            import traceback
            print(f"[Audio] Conversation save ERROR: {e}")
            traceback.print_exc()

    # ── Save attributed line to session transcript ────────────────────────────
    # Use primary (first) detected person as the speaker label, else 'Unknown'
    speaker = all_persons[0] if all_persons else "Unknown"
    primary_emotion = (data.detected_emotions or {}).get(speaker) or data.detected_emotion
    session_manager.add_attributed_line(
        session_id=data.session_id,
        speaker=speaker,
        text=data.text,
        emotion=primary_emotion,
    )

    # ── Broadcast introduction detection to WS ────────────────────────────────
    if extracted_name:
        await connection_manager.broadcast({
            "event_type": "intro_detected",
            "timestamp": datetime.utcnow().timestamp(),
            "session_id": data.session_id,
            "data": {
                "name": extracted_name,
                "transcription": data.text,
                "intent": intent,
                "confidence": confidence,
            },
        })

    # ── Broadcast conversation saved event (for UI refresh) ───────────────────
    if saved_persons and data.text.strip():
        await connection_manager.broadcast({
            "event_type": "conversation_saved",
            "timestamp": datetime.utcnow().timestamp(),
            "session_id": data.session_id,
            "data": {
                "persons": saved_persons,
                "text": data.text,
                "source": "voice",
                "session_id": data.session_id,
            },
        })

    return {
        "extracted_name": extracted_name,
        "intent": intent,
        "confidence": confidence,
        "raw_transcription": data.text,
        "llm_mode": llm_client.status.get("mode"),
        "saved_to_persons": saved_persons,      # list (replaces saved_to_person)
        "saved_to_person": saved_persons[0] if saved_persons else None,  # backward compat
    }


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

@router.get("/status")
async def audio_status():
    return {
        "status": "active",
        "llm": llm_client.status,
        "speech_recognition": "browser-native WebSpeech API",
        "features": [
            "name_extraction",
            "intent_classification",
            "per_person_conversation_save",
            "session_id_tagging",
            "multi_speaker_attribution",
        ],
    }

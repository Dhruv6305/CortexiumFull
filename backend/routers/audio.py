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

from ..ai.llm_client import llm_client, is_valid_person_name
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


# ── Offline Recall Detection (works with zero network / all LLMs down) ────────
_RECALL_PATTERNS = [
    r"\b(?:what\s+(?:did\s+we|was)\s+(?:talk\s+about|discuss(?:ed)?|cover(?:ed)?))\b",
    r"\b(?:what\s+was\s+(?:the|our)\s+(?:last|previous)\s+(?:session|meeting|conversation|talk))\b",
    r"\b(?:remind\s+me\s+what\s+(?:we|i)\s+(?:discussed|talked\s+about|spoke\s+about|said))\b",
    r"\b(?:tell\s+me\s+about\s+(?:the|our)\s+(?:last|previous)\s+(?:session|meeting|conversation))\b",
    r"\b(?:recall|summarize)\s+(?:the|our|last|previous)\s+(?:conversation|session|meeting)\b",
    r"\bwhat\s+did\s+(?:we|i)\s+(?:discuss|talk\s+about)\b",
    r"\b(?:last|previous)\s+(?:conversation|session)\s+about\b",
]

def _is_recall_query(text: str) -> bool:
    """Detect if utterance is asking to recall a previous conversation."""
    lower = text.lower().strip()
    # Conversational remarks with past times or planning are NOT recall queries
    if any(phrase in lower for phrase in ["last week", "last month", "last year", "last night", "last weekend", "timeline", "review the project", "review the code"]):
        if not any(k in lower for k in ["talk about", "discussed", "what was the last session", "remind me what we"]):
            return False
    return any(re.search(pat, lower) for pat in _RECALL_PATTERNS)


def _filter_transcript_lines(lines: list[str]) -> list[str]:
    """Filter out recall questions, empty lines, and very short filler fragments (e.g. single words)."""
    kept = []
    for line in lines:
        t = line.strip()
        if not t:
            continue
        if _is_recall_query(t):
            continue
        words = t.split()
        if len(words) <= 1:
            continue
        if len(t) < 4:
            continue
        kept.append(t)
    return kept


async def _resolve_and_recall_summary(
    target_person_candidate: Optional[str],
    current_persons: List[str],
    current_session_id: str,
    original_text: str = "",
) -> dict:
    """
    Person resolution and summary generation for recall queries:
      1. Explicit person named in the query.
      2. If ambiguous (multiple distinct names mentioned), ask clarification.
      3. Currently recognized person on camera.
      4. Person with most recent conversation across all records.
    """
    from ..routers.persons import _safe_name, _read_profile, _all_known_names
    from ..core.summary_manager import (
        get_last_summary,
        _clean_texts,
        _rule_based_summary,
        update_or_save_session_summary,
    )

    known_names = _all_known_names()

    # Check for multiple known names in the sentence (ambiguity check)
    mentioned_names = [n for n in known_names if re.search(rf"\b{re.escape(n)}\b", original_text, re.IGNORECASE)]
    if len(mentioned_names) > 1:
        return {
            "person": None,
            "summary": f"Did you mean {mentioned_names[0]} or {mentioned_names[1]}?",
            "session_code": None,
            "date": None,
            "summary_source": "system",
        }

    resolved_person = None

    # Priority 1: Explicit name candidate from query
    if target_person_candidate:
        for k in known_names:
            if k.lower() == target_person_candidate.lower():
                resolved_person = k
                break
        if not resolved_person:
            resolved_person = _safe_name(target_person_candidate)
    elif mentioned_names:
        resolved_person = mentioned_names[0]

    # Priority 2: Currently recognized person on camera
    if not resolved_person and current_persons:
        resolved_person = current_persons[0]

    # Priority 3: Person with most recent conversation across all profiles
    if not resolved_person:
        latest_ts = None
        latest_person = None
        for k in known_names:
            prof = _read_profile(k)
            entries = prof.get("entries", [])
            for e in entries:
                if e.get("session_id") == current_session_id:
                    continue  # exclude live session
                ts = e.get("timestamp")
                if ts and (latest_ts is None or ts > latest_ts):
                    latest_ts = ts
                    latest_person = k
        if latest_person:
            resolved_person = latest_person

    # If no person can be identified at all
    if not resolved_person:
        return {
            "person": None,
            "summary": "No previous conversation saved with anyone yet.",
            "session_code": None,
            "date": None,
            "summary_source": "fallback",
        }

    slug = _safe_name(resolved_person)
    profile = _read_profile(slug)
    entries = profile.get("entries", [])

    # Filter out entries from the current session so we recall the PREVIOUS conversation
    prev_entries = [e for e in entries if e.get("session_id") != current_session_id]

    # Check if a completed session summary file already exists
    last_sum = get_last_summary(slug, exclude_session_id=current_session_id)
    if last_sum and last_sum.get("summary") and last_sum.get("llm_used") is True:
        print(f"[Audio/Recall] Reusing stored LLM summary for '{slug}' ({last_sum.get('session_code')})")
        return {
            "person": slug,
            "summary": last_sum["summary"],
            "session_code": last_sum.get("session_code"),
            "date": last_sum.get("date"),
            "summary_source": "llm_cache",
        }

    # If no stored LLM summary exists, build lines from previous session
    from ..routers.persons import _get_last_session_entries
    target_session_entries = []
    target_session_id = None

    if last_sum and last_sum.get("session_id"):
        target_session_id = last_sum.get("session_id")
        target_session_entries = [e for e in prev_entries if e.get("session_id") == target_session_id]

    if not target_session_entries and prev_entries:
        target_session_entries = _get_last_session_entries(prev_entries)
        if target_session_entries and target_session_entries[0].get("session_id"):
            target_session_id = target_session_entries[0].get("session_id")

    raw_texts = [e["note"] for e in target_session_entries if e.get("note", "").strip()]
    if not raw_texts and last_sum and last_sum.get("transcript"):
        raw_texts = [t for t in last_sum["transcript"] if isinstance(t, str) and t.strip()]

    clean_texts = _clean_texts(raw_texts)
    filtered_texts = _filter_transcript_lines(clean_texts)

    if not clean_texts:
        return {
            "person": slug,
            "summary": f"No previous conversation saved with {slug} yet.",
            "session_code": None,
            "date": None,
            "summary_source": "fallback",
        }

    # Generate summary with LLM (pass filtered lines, or clean_texts if all were single words)
    input_lines = filtered_texts if filtered_texts else clean_texts
    summary_text = ""
    try:
        summary_text = await llm_client.generate_summary(slug, input_lines)
    except Exception as e:
        print(f"[Audio/Recall] LLM summary error: {e}")

    session_code = last_sum.get("session_code") if last_sum else None
    date_str = last_sum.get("date") if last_sum else None
    if not date_str and target_session_entries and target_session_entries[-1].get("timestamp"):
        date_str = target_session_entries[-1]["timestamp"][:10]

    if summary_text and len(summary_text.strip()) >= 10 and not summary_text.strip().startswith("{"):
        # LLM succeeded! Save/update summary file with llm_used=True
        target_sid = target_session_id or (last_sum.get("session_id") if last_sum else f"session_{int(datetime.utcnow().timestamp()*1000)}")
        saved = update_or_save_session_summary(
            slug,
            target_sid,
            summary_text,
            clean_texts,
            llm_used=True,
            session_entries=target_session_entries,
        )
        return {
            "person": slug,
            "summary": summary_text,
            "session_code": saved.get("session_code") or session_code,
            "date": saved.get("date") or date_str,
            "summary_source": "llm",
        }

    # Fallback path if every LLM fails
    fallback_text = (last_sum.get("summary") if last_sum else None) or _rule_based_summary(slug, clean_texts)
    return {
        "person": slug,
        "summary": fallback_text,
        "session_code": session_code,
        "date": date_str,
        "summary_source": "fallback",
    }


# ------------------------------------------------------------------
# Process Transcription (Name Extraction + Recall + Conversation Saving)
# ------------------------------------------------------------------

@router.post("/process-text")
async def process_transcription(data: TranscriptionData, current_user=Depends(get_current_user)):
    """
    Analyzes transcribed text:
    - If intent is RECALL ("what did we talk about last time?"):
        Loads previous conversation & summary, returns it for UI display,
        and DOES NOT save the question itself as a conversation note.
    - Otherwise (normal conversation):
        Extracts names / intent, and saves the text to recognized persons'
        conversation files and session logs as today.
    """
    system_prompt = (
        "You are the Cortexium 2.0 NLP engine.\n"
        "Analyze the transcription and return ONLY a JSON object with these fields:\n"
        '- "name": string or null — person name IF AND ONLY IF a human is explicitly introducing themselves by their personal name (e.g. "My name is Sarah", "Call me Alex").\n'
        '- "intent": string — one of: "recall", "navigation", "question", "greeting", "registration", "other"\n'
        '- "target_person": string or null — if the user is asking to recall past conversation with a specific named person (e.g. "what did we discuss with Sarah?" -> "Sarah")\n'
        '- "confidence": float 0-1 — confidence in the classification\n\n'
        "INTENT RULES:\n"
        "- 'recall': The user explicitly asks what was discussed in a PREVIOUS conversation, meeting, or session (e.g. 'what did we talk about last time?', 'what was the last session about?', 'remind me what we discussed', 'what did we talk about with Alex?').\n"
        "- 'navigation': The user asks to navigate somewhere ('take me to the lab').\n"
        "- 'greeting': Introduction or hello ('I am Alex', 'hi there').\n"
        "- 'question': General questions not about recalling past conversations ('what time is it?', 'how does this work?').\n"
        "- 'other': All conversational statements, project discussions, and future planning ('I saw him last week', 'let us review the project timeline', 'we agreed to deploy on Friday'). Statements with words like 'last week' or 'review the project' are 'other', NOT 'recall'.\n\n"
        "CRITICAL RULES:\n"
        "- NEVER extract names from questions, conversational statements, or status remarks (e.g. 'is this working good', 'this is working', 'I am doing well', 'this is great'). For all of these, 'name' MUST BE null.\n"
        "- Words like 'Working', 'Good', 'Fine', 'Great', 'Testing', 'Cool', 'Test' are NEVER names.\n\n"
        "Examples:\n"
        "'What did we talk about last time?' -> {\"name\": null, \"intent\": \"recall\", \"target_person\": null, \"confidence\": 0.95}\n"
        "'What was the last session about?' -> {\"name\": null, \"intent\": \"recall\", \"target_person\": null, \"confidence\": 0.95}\n"
        "'Remind me what we discussed with Sarah' -> {\"name\": null, \"intent\": \"recall\", \"target_person\": \"Sarah\", \"confidence\": 0.95}\n"
        "'Let us review the project timeline' -> {\"name\": null, \"intent\": \"other\", \"target_person\": null, \"confidence\": 0.0}\n"
        "'I saw him last week' -> {\"name\": null, \"intent\": \"other\", \"target_person\": null, \"confidence\": 0.0}\n"
        "'I am John' -> {\"name\": \"John\", \"intent\": \"greeting\", \"target_person\": null, \"confidence\": 0.95}\n"
        "Return ONLY the JSON object, no additional text."
    )

    prompt = f"Transcription: {data.text}"
    response_text = await llm_client.generate_response(prompt, system_prompt)

    # Parse LLM / fallback response
    extracted_name = None
    target_person_candidate = None
    intent = "other"
    confidence = 0.0

    try:
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            extracted_name = parsed.get("name")
            intent = parsed.get("intent", "other")
            target_person_candidate = parsed.get("target_person")
            confidence = float(parsed.get("confidence", 0.0))
    except Exception as e:
        print(f"[Audio] LLM parse error: {e}. Raw: {response_text}")

    # Offline safety check: if LLM failed or missed, detect recall via offline patterns
    if intent != "recall" and _is_recall_query(data.text):
        intent = "recall"
        confidence = 0.90
        # Check if an explicit name is in the sentence (e.g. "with Sarah")
        m_name = re.search(r"\bwith\s+([A-Z][a-z]+)\b", data.text)
        if m_name:
            target_person_candidate = m_name.group(1)

    # Validate that extracted name is a genuine human name
    if extracted_name and not is_valid_person_name(extracted_name, data.text):
        print(f"[Audio] Filtered out invalid name candidate '{extracted_name}' from input: '{data.text}'")
        extracted_name = None

    # ── Build the full list of persons on camera ─────────────────────────────
    all_persons: List[str] = []
    seen_names: set = set()
    for n in (data.detected_persons or []):
        key = n.strip().lower()
        if n.strip() and key not in seen_names:
            seen_names.add(key)
            all_persons.append(n.strip())
    if data.detected_person and data.detected_person.strip().lower() not in seen_names:
        all_persons.append(data.detected_person.strip())

    # ── BRANCH A: RECALL INTENT ──────────────────────────────────────────────
    # DO NOT save the recall question as a conversation entry!
    if intent == "recall":
        recall_res = await _resolve_and_recall_summary(
            target_person_candidate=target_person_candidate,
            current_persons=all_persons,
            current_session_id=data.session_id,
            original_text=data.text,
        )
        print(f"[Audio] [Recall] Person: '{recall_res.get('person')}' | Summary: '{str(recall_res.get('summary'))[:60]}...'")
        return {
            "extracted_name": None,
            "intent": "recall",
            "confidence": confidence,
            "raw_transcription": data.text,
            "llm_mode": llm_client.status.get("mode"),
            "saved_to_persons": [],
            "saved_to_person": None,
            "recall_person": recall_res.get("person"),
            "recall_summary": recall_res.get("summary"),
            "session_code": recall_res.get("session_code"),
            "session_date": recall_res.get("date"),
            "summary_source": recall_res.get("summary_source", "llm"),
        }

    # ── BRANCH B: STORE CONVERSATION (Everything else) ────────────────────────

    # If an introduction name was extracted, auto-register camera face image and notify WS
    # CRITICAL: ONLY auto-register if:
    # 1. We have a valid human name candidate with high confidence (>= 0.85)
    # 2. Intent is explicit greeting or registration
    # 3. AND NO KNOWN PERSON IS ALREADY DETECTED! If someone is already recognized in frame,
    #    their speech must NEVER auto-register a new person!
    if extracted_name and confidence >= 0.85 and intent in ("registration", "greeting"):
        if not all_persons:
            try:
                from ..cv.model_loader import model_loader
                latest = getattr(model_loader, "latest_frame", None)
                if latest is not None:
                    print(f"[Audio] Auto-registering camera face image for voice intro '{extracted_name}'")
                    reg_res = model_loader.register_person(latest, extracted_name)
                    if reg_res.get("success"):
                        all_persons.append(extracted_name)
                        await connection_manager.broadcast({
                            "event_type": "person_registered",
                            "timestamp": datetime.utcnow().timestamp(),
                            "session_id": data.session_id,
                            "data": {"name": extracted_name},
                        })
            except Exception as err:
                print(f"[Audio] Failed to auto-register face image for '{extracted_name}': {err}")
    else:
        extracted_name = None

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
                    print(f"[Audio] [OK] Saved '{data.text[:50]}' -> {person_name} (session={data.session_id})")
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

"""
Cortexium 2.0 — Persons Management Router
==========================================
Full CRUD for the people database:
  - List / create / update / delete persons
  - Upload multiple face images per person (improves DeepFace accuracy)
  - Serve face thumbnails to the frontend
  - Invalidates DeepFace .pkl index on any image change

Face images stored at: backend/data/faces/<Name>_<idx>.jpg
Person metadata:       backend/data/conversations/<Name>.json
"""
import shutil, re
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..db.database import local_db

router = APIRouter(prefix="/api/persons", tags=["persons"])

# ── Paths ─────────────────────────────────────────────────────────────────────
_DATA   = Path(__file__).resolve().parent.parent / "data"
FACES   = _DATA / "faces"
CONVOS  = _DATA / "conversations"
FACES.mkdir(parents=True, exist_ok=True)
CONVOS.mkdir(parents=True, exist_ok=True)

_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_name(name: str) -> str:
    """Sanitize person name for use as a filename slug."""
    return re.sub(r"[^\w\s-]", "", name).strip().title()


def _invalidate_deepface():
    """Remove DeepFace cached PKL index so it re-indexes on next call."""
    for pkl in FACES.glob("*.pkl"):
        pkl.unlink(missing_ok=True)


def _person_images(name: str) -> list[dict]:
    """Return list of all face images for a person, sorted."""
    slug = _safe_name(name)
    imgs = sorted(FACES.glob(f"{slug}*.jpg")) + \
           sorted(FACES.glob(f"{slug}*.jpeg")) + \
           sorted(FACES.glob(f"{slug}*.png"))
    return [{"filename": p.name, "url": f"/faces/{p.name}",
              "size": p.stat().st_size} for p in imgs]


def _load_profile(name: str) -> dict:
    slug = _safe_name(name)
    fp   = CONVOS / f"{slug}.json"
    if fp.exists():
        try:
            return fp.read_text(encoding="utf-8")
        except Exception:
            pass
    return None


def _read_profile(name: str) -> dict:
    import json
    slug = _safe_name(name)
    fp   = CONVOS / f"{slug}.json"
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"name": slug, "entries": [], "last_seen": None,
            "registered_via": None, "role": "", "notes": ""}


def _write_profile(data: dict):
    import json
    slug = _safe_name(data["name"])
    fp   = CONVOS / f"{slug}.json"
    fp.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def append_conversation_entry(
    name: str,
    text: str,
    source: str = "voice",
    emotion: str | None = None,
    session_id: str | None = None,
) -> bool:
    """
    Public utility: append a conversation entry to a person's profile.
    Called from audio.py when a voice transcription is associated with a recognized person.
    Returns True if successful, False if person not found.
    """
    slug = _safe_name(name)
    if not slug:
        return False
    has_profile = (CONVOS / f"{slug}.json").exists()
    profile = _read_profile(slug)
    if not has_profile:
        profile["name"] = slug
        profile["registered_via"] = "voice"
        profile["registered_at"] = datetime.now().isoformat()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "note": text.strip(),
        "source": source,
        "session_id": session_id,   # ← links this entry to its session
    }
    if emotion:
        entry["emotion"] = emotion
    profile.setdefault("entries", []).append(entry)
    profile["last_seen"] = datetime.now().isoformat()
    profile["name"] = slug
    _write_profile(profile)
    return True


def _all_known_names() -> list[str]:
    """Derive person names from existing face images + conversation files."""
    names = set()
    for img in FACES.glob("*.*"):
        if img.suffix.lower() in _ALLOWED_EXT:
            # Strip trailing _0, _1, _2 etc.
            stem = re.sub(r"_\d+$", "", img.stem)
            names.add(stem.title())
    for conv in CONVOS.glob("*.json"):
        names.add(conv.stem.title())
    return sorted(names)


def _last_seen_str(ts: str | None) -> str:
    if not ts:
        return "Never"
    try:
        from datetime import datetime
        delta = int((datetime.now() - datetime.fromisoformat(ts)).total_seconds())
        if delta < 60:    return f"{delta}s ago"
        if delta < 3600:  return f"{delta//60}m ago"
        if delta < 86400: return f"{delta//3600}h ago"
        return f"{delta//86400}d ago"
    except Exception:
        return "Unknown"


def _build_person_card(name: str) -> dict:
    slug    = _safe_name(name)
    profile = _read_profile(slug)
    images  = _person_images(slug)
    thumb   = images[0]["url"] if images else None
    return {
        "name":           slug,
        "role":           profile.get("role", ""),
        "notes":          profile.get("notes", ""),
        "registered_via": profile.get("registered_via"),
        "registered_at":  profile.get("registered_at"),
        "last_seen":      profile.get("last_seen"),
        "last_seen_str":  _last_seen_str(profile.get("last_seen")),
        "thumbnail":      thumb,
        "image_count":    len(images),
        "images":         images,
        "conversation_count": len(profile.get("entries", [])),
    }


# ════════════════════════════════════════════════�# ── LLM summarisation helper ─────────────────────────────────────────────────────

async def _llm_summarise(person_name: str, transcript: str) -> str:
    """
    Produces a plain-English 1-2 sentence summary using the LLM.
    Detects and rejects JSON-format responses with a clean fallback.
    """
    import re as _re

    def _fallback(text: str) -> str:
        text = text.strip()
        if len(text) <= 120:
            return text
        cut = text[:120].rsplit(" ", 1)[0]
        return cut + "."

    try:
        from ..ai.llm_client import llm_client
        system = (
            "You summarize spoken conversation transcripts into plain English. "
            "STRICT RULES: "
            "1. Output PLAIN ENGLISH ONLY. Never JSON, never curly braces, never bullet points. "
            "2. Write exactly 1-2 sentences about the main topics discussed. "
            "3. Maximum 120 characters total. "
            "4. Do NOT start with phrases like The person said or Summary: "
            "5. If the transcript is unclear fragments, describe what you can infer. "
            "GOOD example: Discussed issues with the conversation log and asked about detection. "
            "BAD example: {name: null, intent: other, confidence: 0.0}"
        )
        prompt = (
            f"Here is what {person_name} said during the session:\n"
            f"{transcript}\n\n"
            "Write a 1-2 sentence plain-English summary (max 120 chars, no JSON):"
        )
        result = await llm_client.generate_response(prompt, system)
        result = result.strip()

        # Reject JSON responses immediately
        if (result.startswith("{") or result.startswith("[")
                or '"intent"' in result or '"name":' in result
                or '"confidence"' in result):
            print(f"[PersonSummary] LLM returned JSON, using fallback")
            return _fallback(transcript)

        # Strip common unwanted prefixes
        for prefix in ("Summary:", "Summary -", f"{person_name}:", "Answer:", "Output:", "Here is"):
            if result.lower().startswith(prefix.lower()):
                result = result[len(prefix):].strip()

        # Remove markdown artifacts
        result = _re.sub(r"[*_`#]+", "", result).strip()

        if result and len(result) >= 8:
            return result[:150]
    except Exception as e:
        print(f"[PersonSummary] LLM error: {e}")

    return _fallback(transcript)


def _get_last_session_entries(entries: list) -> list:
    """
    Groups entries by 30-minute idle gaps and returns the most recent group.
    Used as fallback when no session_id is available.
    """
    if not entries:
        return []
    from datetime import datetime
    GAP = 30 * 60
    sessions, current = [], [entries[0]]
    for e in entries[1:]:
        try:
            prev_t = datetime.fromisoformat(current[-1]["timestamp"])
            curr_t = datetime.fromisoformat(e["timestamp"])
            if (curr_t - prev_t).total_seconds() > GAP:
                sessions.append(current)
                current = [e]
            else:
                current.append(e)
        except Exception:
            current.append(e)
    sessions.append(current)
    return sessions[-1]   # most recent group


@router.get("/{name}/summary")
async def get_person_summary(name: str, session_id: Optional[str] = None):
    """
    Returns a short LLM-generated summary of what this person said
    in the given session (or the most recent session if not specified).
    Instantly returns a loading state; LLM call is awaited.
    """
    slug = _safe_name(name)
    profile = _read_profile(slug)
    entries = profile.get("entries", [])

    if not entries:
        return {
            "summary": None,
            "last_seen_str": _last_seen_str(profile.get("last_seen")),
            "session_count": 0,
            "total_entries": 0,
            "role": profile.get("role", ""),
        }

    # ── Filter to target session ─────────────────────────────────────────────────────────────
    if session_id:
        session_entries = [e for e in entries if e.get("session_id") == session_id]
        # If no entries for this exact session yet, return 'not spoken yet'
        if not session_entries:
            return {
                "summary": "Nothing recorded for this session yet — speak while your face is recognized.",
                "last_seen_str": _last_seen_str(profile.get("last_seen")),
                "session_count": 0,
                "total_entries": len(entries),
                "role": profile.get("role", ""),
            }
    else:
        # Fallback: use 30-min gap heuristic to find last session
        session_entries = _get_last_session_entries(entries)

    # Count unique session_ids across all entries for session_count
    all_session_ids = {e.get("session_id") for e in entries if e.get("session_id")}
    session_count = len(all_session_ids)

    # ── Build transcript for LLM ────────────────────────────────────────────────────────────
    texts = [e["note"] for e in session_entries if e.get("note", "").strip()]
    if not texts:
        return {
            "summary": "No spoken content recorded for this session.",
            "last_seen_str": _last_seen_str(profile.get("last_seen")),
            "session_count": session_count,
            "total_entries": len(entries),
            "role": profile.get("role", ""),
        }

    # Deduplicate near-identical phrases before sending to LLM
    seen, deduped = set(), []
    for t in texts:
        key = t.lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(t)

    transcript = " ".join(deduped)

    # ── LLM summarise ───────────────────────────────────────────────────────────────────────
    summary = await _llm_summarise(slug, transcript)

    return {
        "summary": summary,
        "last_seen_str": _last_seen_str(profile.get("last_seen")),
        "session_count": session_count,
        "total_entries": len(entries),
        "role": profile.get("role", ""),
    }




@router.get("")
async def list_persons():
    """Return all known persons with full metadata and image list."""
    names = _all_known_names()
    return {
        "persons": [_build_person_card(n) for n in names],
        "total":   len(names),
    }

@router.get("/{name}")
async def get_person(name: str):
    slug = _safe_name(name)
    if not _person_images(slug) and not (CONVOS / f"{slug}.json").exists():
        raise HTTPException(404, f"Person '{slug}' not found")
    return _build_person_card(slug)



class UpdatePersonPayload(BaseModel):
    role:  Optional[str] = None
    notes: Optional[str] = None
    name:  Optional[str] = None   # rename support


@router.patch("/{name}")
async def update_person(name: str, payload: UpdatePersonPayload):
    """Update person role, notes, or rename."""
    slug    = _safe_name(name)
    profile = _read_profile(slug)

    if payload.role  is not None: profile["role"]  = payload.role
    if payload.notes is not None: profile["notes"] = payload.notes

    if payload.name and _safe_name(payload.name) != slug:
        new_slug = _safe_name(payload.name)
        # Rename face images
        for img in _person_images(slug):
            old = FACES / img["filename"]
            new_name = img["filename"].replace(slug, new_slug, 1)
            old.rename(FACES / new_name)
        # Rename conversation file
        old_conv = CONVOS / f"{slug}.json"
        if old_conv.exists():
            old_conv.rename(CONVOS / f"{new_slug}.json")
        profile["name"] = new_slug
        _invalidate_deepface()
        _write_profile(profile)
        return {"success": True, "person": _build_person_card(new_slug)}

    profile["name"] = slug
    _write_profile(profile)
    return {"success": True, "person": _build_person_card(slug)}


@router.post("")
async def create_person(
    name: str = Form(...),
    role: str = Form(""),
    notes: str = Form(""),
    image: Optional[UploadFile] = File(None),
):
    """Create a new person, optionally with an initial face image."""
    slug = _safe_name(name)
    if not slug:
        raise HTTPException(400, "Invalid name")

    # Build/update profile
    profile = _read_profile(slug)
    profile.update({
        "name":           slug,
        "role":           role,
        "notes":          notes,
        "registered_at":  profile.get("registered_at") or datetime.now().isoformat(),
        "registered_via": profile.get("registered_via") or "manual-ui",
    })
    _write_profile(profile)

    # Save image if provided
    if image and image.filename:
        ext = Path(image.filename).suffix.lower()
        if ext not in _ALLOWED_EXT:
            raise HTTPException(400, f"Unsupported image type: {ext}")
        existing = _person_images(slug)
        idx      = len(existing)
        dest     = FACES / f"{slug}{'_' + str(idx) if idx > 0 else ''}{ext}"
        dest.write_bytes(await image.read())
        _invalidate_deepface()

    return {"success": True, "person": _build_person_card(slug)}


@router.post("/{name}/images")
async def upload_image(name: str, image: UploadFile = File(...)):
    """Upload an additional face image for an existing person."""
    slug = _safe_name(name)
    ext  = Path(image.filename).suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(400, f"Unsupported image type: {ext}. Use JPG/PNG/WebP")

    existing = _person_images(slug)
    idx      = len(existing)
    # Primary image has no suffix index, extras have _1 _2 etc.
    filename = f"{slug}{'_' + str(idx) if idx > 0 else ''}{ext}"
    dest     = FACES / filename

    dest.write_bytes(await image.read())
    _invalidate_deepface()

    # Update conversation profile image count
    profile = _read_profile(slug)
    profile.setdefault("entries", []).append({
        "timestamp": datetime.now().isoformat(),
        "note":      f"Face image #{idx+1} added via UI upload",
        "source":    "ui-upload",
    })
    profile["name"] = slug
    _write_profile(profile)

    return {
        "success":  True,
        "filename": filename,
        "url":      f"/faces/{filename}",
        "images":   _person_images(slug),
    }


@router.delete("/{name}/images/{filename}")
async def delete_image(name: str, filename: str):
    """Delete a specific face image."""
    slug = _safe_name(name)
    # Security: ensure the filename belongs to this person
    if not filename.startswith(slug):
        raise HTTPException(403, "Image does not belong to this person")
    fp = FACES / filename
    if not fp.exists():
        raise HTTPException(404, f"Image '{filename}' not found")
    fp.unlink()
    _invalidate_deepface()
    return {"success": True, "images": _person_images(slug)}


@router.delete("/{name}")
async def delete_person(name: str):
    """Delete a person: removes all face images, thumbnails, summaries, and conversation data."""
    slug = _safe_name(name)
    deleted_images = 0

    # 1. Delete all matching images in FACES (e.g. slug.jpg, slug_1.jpg, slug.png)
    for p in FACES.glob(f"{slug}*"):
        if p.is_file():
            try:
                p.unlink()
                deleted_images += 1
            except Exception:
                pass

    # 2. Delete all matching thumbnails in THUMBNAILS (e.g. slug_thumb.jpg)
    thumb_dir = _DATA / "thumbnails"
    if thumb_dir.exists():
        for t in thumb_dir.glob(f"{slug}*"):
            if t.is_file():
                try:
                    t.unlink()
                except Exception:
                    pass

    # 3. Delete conversation profile JSON
    conv_fp = CONVOS / f"{slug}.json"
    if conv_fp.exists():
        try:
            conv_fp.unlink()
        except Exception:
            pass

    # 4. Delete summaries directory for this person (e.g. backend/data/summaries/slug/)
    person_summaries_dir = _DATA / "summaries" / slug
    if person_summaries_dir.exists():
        shutil.rmtree(person_summaries_dir, ignore_errors=True)

    # 5. Invalidate ArcFace PKL cache & clear model_loader identity cache
    _invalidate_deepface()
    try:
        from ..cv.model_loader import model_loader
        model_loader._identity_cache.clear()
    except Exception:
        pass

    return {"success": True, "name": slug, "deleted_images": deleted_images}


@router.get("/{name}/conversations")
async def get_conversations(name: str):
    """Return full conversation log for a person."""
    slug    = _safe_name(name)
    profile = _read_profile(slug)
    return {
        "name":    slug,
        "entries": profile.get("entries", []),
        "total":   len(profile.get("entries", [])),
    }


@router.post("/{name}/conversations")
async def add_conversation_note(name: str, note: str = Form(...)):
    """Manually add a conversation note for a person."""
    slug    = _safe_name(name)
    profile = _read_profile(slug)
    profile.setdefault("entries", []).append({
        "timestamp": datetime.now().isoformat(),
        "note":      note,
        "source":    "ui-manual",
    })
    profile["last_seen"] = datetime.now().isoformat()
    profile["name"]      = slug
    _write_profile(profile)
    return {"success": True, "entries": profile["entries"]}


# ══════════════════════════════════════════════════════════════════════════════
#  Session Summary Endpoints (uses core/summary_manager.py)
# ══════════════════════════════════════════════════════════════════════════════

class FinalizeSessionPayload(BaseModel):
    session_id: str


@router.post("/{name}/finalize-session")
async def finalize_person_session(name: str, payload: FinalizeSessionPayload):
    """
    Generates and stores a session summary for a person.
    Called when the user clicks End Session, or when triggered by voice.
    """
    from ..core.summary_manager import generate_and_save
    slug    = _safe_name(name)
    profile = _read_profile(slug)
    entries = profile.get("entries", [])

    result = await generate_and_save(slug, payload.session_id, entries)
    if result is None:
        return {"success": False, "reason": "No entries found for this session"}
    return {"success": True, "summary": result}


@router.get("/{name}/sessions")
async def list_person_sessions(name: str, limit: int = 20):
    """
    Lists all session summaries for a person, newest first.
    Each entry has session_code, date, summary, entry_count.
    """
    from ..core.summary_manager import list_sessions
    slug    = _safe_name(name)
    sessions = list_sessions(slug, limit=limit)
    return {"person": slug, "sessions": sessions, "total": len(sessions)}


@router.get("/{name}/last-session")
async def get_last_session_summary(name: str, session_id: Optional[str] = None, exclude_session_id: Optional[str] = None):
    """
    Returns the most recent COMPLETED session summary.
    Pass session_id (current live session) to auto-finalize it before fetching the
    PREVIOUS session — so the card shows the last completed session, not the current one.
    """
    from ..core.summary_manager import get_last_summary, auto_finalize_if_new
    slug    = _safe_name(name)
    profile = _read_profile(slug)
    entries = profile.get("entries", [])

    # Determine which session to exclude (current live session)
    live_sid = exclude_session_id or session_id

    # Auto-finalize the live session so it becomes available as previous next time
    if live_sid and entries:
        await auto_finalize_if_new(slug, live_sid, entries)

    # Return the most recent session that ISN'T the live session
    result = get_last_summary(slug, exclude_session_id=live_sid)
    if result is None:
        return {"found": False, "person": slug}
    return {"found": True, "person": slug, **result}


@router.get("/{name}/sessions-by-date")
async def get_sessions_by_date(name: str, date: str):
    """
    Returns all session summaries for a person on a given date.
    date can be: "2026-08-25", "Aug 25", "yesterday", "today"
    """
    from ..core.summary_manager import get_by_date
    slug    = _safe_name(name)
    results = get_by_date(slug, date)
    return {
        "person":   slug,
        "date_query": date,
        "sessions": results,
        "found":    len(results) > 0,
    }

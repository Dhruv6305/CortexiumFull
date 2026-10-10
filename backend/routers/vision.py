"""
Cortexium 2.0 — Vision Router
Handles frame processing, face registration, and video analysis.
All processed events are broadcast to WebSocket clients in real time.

Multi-person: process_frame now returns and broadcasts ALL detected persons,
not just the first one. Each person gets their own EncounterRecord.
"""
import asyncio
import base64
import numpy as np
import cv2
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import shutil
import tempfile
import os

from ..cv.model_loader import model_loader
from ..ai.llm_client import vlm_client
from ..auth.supabase_auth import get_current_user
from ..routers.ws_hub import connection_manager
from ..core.session_manager import session_manager
from ..models.events import SceneEvent, EncounterRecord

router = APIRouter(prefix="/api/vision", tags=["vision"])


class FrameData(BaseModel):
    frame_b64: str
    session_id: str
    timestamp: float
    name: Optional[str] = None  # Optional name for auto-registration
    use_vlm: bool = False  # Enable VLM scene analysis for this frame


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

@router.get("/status")
async def vision_status():
    return {
        "status": "active",
        "engine": f"OpenCV + YOLOv8 + DeepFace ({model_loader.status.get('face_recognition_model', 'ArcFace')}) + qwen2.5vl",
        **model_loader.status,
        "vlm": vlm_client.status,
    }


# ------------------------------------------------------------------
# VLM Scene Analysis (qwen2.5vl)
# ------------------------------------------------------------------

@router.post("/scene")
async def analyze_scene(data: FrameData, current_user=Depends(get_current_user)):
    """
    Send a frame to qwen2.5vl for full natural-language scene understanding.
    Returns: description, objects, persons, hazards, mood, suggested_action.
    """
    try:
        frame = _decode_frame(data.frame_b64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")

    scene = await vlm_client.describe_scene(
        frame,
        context=f"session_id={data.session_id}"
    )

    if scene.get("available"):
        await connection_manager.broadcast({
            "event_type": "scene_analyzed",
            "timestamp": data.timestamp,
            "session_id": data.session_id,
            "data": scene,
        })

        if scene.get("hazards"):
            from ..models.events import SceneEvent
            event = SceneEvent(
                event_type="hazard_detected",
                session_id=data.session_id,
                timestamp=data.timestamp,
                data={"hazards": scene["hazards"], "source": "vlm"},
                confidence=0.85,
            )
            session_manager.record_event(data.session_id, event)

    return {
        "session_id": data.session_id,
        "timestamp": data.timestamp,
        "vlm_available": scene.get("available", False),
        "model": scene.get("model"),
        **{k: v for k, v in scene.items() if k not in ("available", "model")},
    }


# ------------------------------------------------------------------
# Frame Processing (Main Pipeline) — Multi-Person
# ------------------------------------------------------------------

@router.post("/frame")
async def process_frame(data: FrameData, current_user=Depends(get_current_user)):
    """
    Receives a base64-encoded frame, runs full CV inference,
    broadcasts events via WebSocket, and returns results.
    Supports simultaneous detection of multiple persons.
    """
    try:
        frame = _decode_frame(data.frame_b64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")

    # Ensure session exists
    session_manager.get_or_create(data.session_id)

    # Run inference pipeline � offloaded to thread pool to avoid blocking asyncio event loop
    objects = await asyncio.to_thread(model_loader.predict_objects, frame)
    faces   = await asyncio.to_thread(model_loader.recognize_faces, frame)   # emotion/age/gender per face
    persons = await asyncio.to_thread(model_loader.identify_persons, frame)  # [{name, bbox, confidence, region}]

    # ── Auto-register if a name was provided and no match was found ──
    registration_result = None
    if data.name and not persons:
        registration_result = model_loader.register_person(frame, data.name)
        if registration_result.get("success"):
            # Treat newly registered person as recognized this frame
            persons = [{
                "name": registration_result["name"],
                "confidence": 1.0,
                "region": {"x": 0, "y": 0, "w": frame.shape[1], "h": frame.shape[0]},
            }]
            encounter = EncounterRecord(
                person_name=registration_result["name"],
                session_id=data.session_id,
                timestamp=data.timestamp,
                emotion=faces[0].get("dominant_emotion") if faces else None,
                context="auto-registered via voice introduction",
            )
            session_manager.record_encounter(data.session_id, encounter)

    # ── Record CV events in session ──
    if objects:
        event = SceneEvent(
            event_type="object_detected",
            session_id=data.session_id,
            timestamp=data.timestamp,
            data={"objects": objects},
            confidence=max((o["confidence"] for o in objects), default=0),
        )
        session_manager.record_event(data.session_id, event)

    # ── Record encounter for EACH detected person ──
    for person in persons:
        person_name = person.get("name")
        if not person_name:
            continue

        event = SceneEvent(
            event_type="face_recognized",
            session_id=data.session_id,
            timestamp=data.timestamp,
            data={
                "identity": person_name,
                "confidence": person.get("confidence", 0),
                "region": person.get("region"),
                "face_analysis": faces,
            },
            confidence=person.get("confidence", 0.9),
        )
        session_manager.record_event(data.session_id, event)

        # Match face analysis to person by region proximity (best effort)
        matched_emotion = _match_emotion(person.get("region"), faces)

        encounter = EncounterRecord(
            person_name=person_name,
            session_id=data.session_id,
            timestamp=data.timestamp,
            emotion=matched_emotion,
            context="recognized in frame",
        )
        session_manager.record_encounter(data.session_id, encounter)

    # ── Build response ──
    result = {
        "session_id": data.session_id,
        "timestamp": data.timestamp,
        "detected_objects": objects,
        "face_analysis": faces,
        "persons": persons,                        # full multi-person list
        "identity": persons[0]["name"] if persons else None,  # legacy compat
        "user_id": current_user.id,
    }

    # ── Broadcast to WebSocket clients ──
    await connection_manager.broadcast({
        "event_type": "frame_processed",
        "timestamp": data.timestamp,
        "session_id": data.session_id,
        "data": {
            "detected_objects": objects,
            "persons": persons,                    # multi-person list for UI
            "identity": persons[0]["name"] if persons else None,  # legacy
            "face_analysis": faces[:max(1, len(persons))] if faces else [],
            "object_count": len(objects),
            "person_count": len(persons),
        },
    })

    return result


# ------------------------------------------------------------------
# Video Processing (Background Task)
# ------------------------------------------------------------------

@router.post("/video/process")
async def process_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """
    Accepts a video file and processes every 30th frame for object/person detection.
    """
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, file.filename or "upload.mp4")

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    results = []
    cap = cv2.VideoCapture(temp_path)
    frame_count = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_count % 30 == 0:
            objects = model_loader.predict_objects(frame)
            persons = model_loader.identify_persons(frame)
            results.append({
                "frame": frame_count,
                "objects": objects,
                "persons": persons,
                "identity": persons[0]["name"] if persons else None,
            })

        frame_count += 1
        if frame_count > 900:  # Limit to 30s at 30fps
            break

    cap.release()
    try:
        os.remove(temp_path)
    except Exception:
        pass

    all_persons = list({p["name"] for r in results for p in r.get("persons", [])})

    await connection_manager.broadcast({
        "event_type": "video_analysis_complete",
        "timestamp": datetime.utcnow().timestamp(),
        "data": {
            "filename": file.filename,
            "processed_frames": len(results),
            "persons_detected": all_persons,
            "total_frames_scanned": frame_count,
        },
    })

    return {
        "filename": file.filename,
        "processed_frames": len(results),
        "total_frames_scanned": frame_count,
        "results": results,
    }


# ------------------------------------------------------------------
# Manual Face Registration
# ------------------------------------------------------------------

@router.post("/register")
async def register_face(data: FrameData, current_user=Depends(get_current_user)):
    """
    Manually register a face from a frame with an explicit name.
    Supports multiple images per person (auto-indexes).
    """
    if not data.name:
        raise HTTPException(status_code=400, detail="Name is required for registration")

    try:
        frame = _decode_frame(data.frame_b64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")

    result = model_loader.register_person(frame, data.name)

    if result["success"]:
        await connection_manager.broadcast({
            "event_type": "person_registered",
            "timestamp": datetime.utcnow().timestamp(),
            "session_id": data.session_id,
            "data": {
                "name": result["name"],
                "message": result["message"],
                "image_index": result.get("image_index", 0),
            },
        })

    return result


# ------------------------------------------------------------------
# List Registered Persons
# ------------------------------------------------------------------

@router.get("/persons")
async def list_persons(current_user=Depends(get_current_user)):
    """Returns the list of all registered persons in the face DB."""
    persons = session_manager.get_registered_persons()
    face_files = [
        f for f in os.listdir(model_loader.face_db_path)
        if f.lower().endswith((".jpg", ".png", ".jpeg"))
    ] if os.path.exists(model_loader.face_db_path) else []
    import re
    registered = sorted(set(
        re.sub(r"_\d+$", "", os.path.splitext(f)[0]) for f in face_files
    ))
    return {
        "registered_persons": registered,
        "persons_seen_this_run": persons,
        "total": len(registered),
        "total_images": len(face_files),
    }


# ------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------

def _decode_frame(frame_b64: str) -> np.ndarray:
    encoded = frame_b64.split(",")[1] if "," in frame_b64 else frame_b64
    nparr = np.frombuffer(base64.b64decode(encoded), np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Could not decode image from base64 data")
    return frame


def _match_emotion(region: dict | None, faces: list) -> str | None:
    """
    Find the face analysis entry whose bounding box best overlaps the given region.
    Returns dominant_emotion or None.
    """
    if not region or not faces:
        return faces[0].get("dominant_emotion") if faces else None

    rx, ry, rw, rh = region.get("x", 0), region.get("y", 0), region.get("w", 0), region.get("h", 0)
    best_overlap = -1
    best_emotion = None

    for face in faces:
        fr = face.get("region", {})
        fx, fy, fw, fh = fr.get("x", 0), fr.get("y", 0), fr.get("w", 0), fr.get("h", 0)
        # Simple overlap metric: distance between centers
        cx1, cy1 = rx + rw / 2, ry + rh / 2
        cx2, cy2 = fx + fw / 2, fy + fh / 2
        dist = ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5
        overlap = 1.0 / (dist + 1.0)
        if overlap > best_overlap:
            best_overlap = overlap
            best_emotion = face.get("dominant_emotion")

    return best_emotion

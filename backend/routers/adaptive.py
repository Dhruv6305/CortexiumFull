"""
Cortexium 2.0 — Adaptive Learning Router
Provides behavioral predictions and pattern summaries based on accumulated session data.
This is Phase 4 of the MCP — lightweight implementation using heuristic analysis.
"""
from datetime import datetime
from collections import Counter
from fastapi import APIRouter, Depends, Query
from typing import Optional

from ..auth.supabase_auth import get_current_user
from ..core.session_manager import session_manager

router = APIRouter(prefix="/api/adaptive", tags=["adaptive"])


@router.get("/predictions")
async def get_predictions(
    session_id: Optional[str] = Query(default=None),
    current_user=Depends(get_current_user),
):
    """
    Returns behavioral predictions based on current session activity.
    Uses heuristic pattern matching (ML upgrade path documented in MCP).
    """
    stats = session_manager.get_stats()
    session = session_manager.get_session(session_id) if session_id else None

    # Heuristic predictions based on what's been seen
    predictions = []
    confidence_base = 0.65

    if session:
        objects = session.objects_seen
        persons = session.persons_seen

        # Navigation prediction
        vehicle_objects = {"car", "truck", "bus", "motorcycle", "bicycle"}
        if any(o.lower() in vehicle_objects for o in objects):
            predictions.append({
                "type": "navigation",
                "prediction": "Vehicle activity detected — GPS navigation may be needed",
                "confidence": round(confidence_base + 0.1, 2),
                "trigger": "vehicle_object_seen",
            })

        # Social prediction
        if persons:
            predictions.append({
                "type": "social",
                "prediction": f"Social context active — {len(persons)} person(s) recognized this session",
                "confidence": round(confidence_base + 0.15, 2),
                "trigger": "face_recognized",
                "persons": persons,
            })

        # Environment hazard prediction
        hazard_objects = {"knife", "scissors", "fire", "smoke", "traffic light", "stop sign"}
        hazards = [o for o in objects if o.lower() in hazard_objects]
        if hazards:
            predictions.append({
                "type": "environment",
                "prediction": f"Potential hazards in scene: {', '.join(hazards)}",
                "confidence": round(confidence_base + 0.2, 2),
                "trigger": "hazard_object_seen",
                "hazards": hazards,
            })

    return {
        "session_id": session_id,
        "timestamp": datetime.utcnow().timestamp(),
        "predictions": predictions,
        "system_stats": stats,
    }


@router.get("/insights")
async def get_insights(current_user=Depends(get_current_user)):
    """
    Returns aggregate insights across all sessions — the 'learning summary'.
    """
    all_encounters = session_manager.get_all_encounters(limit=200)
    stats = session_manager.get_stats()

    # Encounter frequency by person
    person_counts = Counter(e.person_name for e in all_encounters)
    emotion_counts = Counter(e.emotion for e in all_encounters if e.emotion)

    frequent_people = [
        {"name": name, "encounter_count": count}
        for name, count in person_counts.most_common(10)
    ]

    dominant_emotions = [
        {"emotion": emotion, "count": count}
        for emotion, count in emotion_counts.most_common(5)
    ]

    return {
        "timestamp": datetime.utcnow().timestamp(),
        "total_encounters": len(all_encounters),
        "unique_persons_seen": stats["unique_persons_seen"],
        "unique_objects_detected": stats["unique_objects_seen"],
        "frequent_people": frequent_people,
        "dominant_emotions": dominant_emotions,
        "objects_catalogue": stats["objects"],
        "system_uptime_events": stats["total_events_this_run"],
    }


@router.get("/status")
async def adaptive_status(current_user=Depends(get_current_user)):
    return {
        "status": "active",
        "mode": "heuristic",
        "upgrade_path": "scikit-learn KMeans clustering (Phase 4 ML)",
        "stats": session_manager.get_stats(),
    }

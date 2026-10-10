"""
server.py — Cortexium XR FastAPI Backend

Exposes the adaptive organizer logic (YOLO detection, ML prediction,
learning, retraining) over HTTP REST endpoints and a WebSocket stream
that the React frontend can consume.

Run with:
    uvicorn server:app --host 0.0.0.0 --port 8000 --reload

Dependencies:
    pip install fastapi uvicorn[standard] opencv-python ultralytics
"""

import asyncio
import csv
import json
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from ml_pipeline import (
    DataCollector,
    PlacementPredictor,          # legacy shim → PersonalizedCatBoostPredictor
    BaselineCatBoostPredictor,
    PersonalizedCatBoostPredictor,
    train_and_evaluate,          # → train_personalized_model
    get_active_metrics,
    PERSONALIZED_MODEL_PATH,
    PERSONALIZED_METRICS_PATH,
)

# ─────────────────────────────────────────────
# Paths & constants
# ─────────────────────────────────────────────
LEARNED_RULES_PATH = "learned_rules.json"
USAGE_DATA_PATH = "usage_data.csv"
# METRICS_PATH now points to the active model's metrics (personalized or baseline)
# The old root-level metrics.json is no longer the source of truth.
METRICS_PATH = PERSONALIZED_METRICS_PATH   # written by personalized retraining
# Use system default camera (index 0) — browser/OS permission model
CAMERA_INDEX = 0

DEFAULT_RULES = {
    "laptop": "table",
    "cell phone": "table",
    "book": "table",
    "bottle": "table",
    "cup": "table",
    "backpack": "chair",
    "handbag": "chair",
    "remote": "sofa",
    "keyboard": "table",
    "mouse": "table",
}

SURFACE_ALIASES = {
    "dining table": "table",
    "bench": "table",
    "couch": "sofa",
}

SURFACES = ["dining table", "table", "chair", "couch", "bench", "bed"]


# ─────────────────────────────────────────────
# Shared mutable state (guarded by a lock)
# ─────────────────────────────────────────────
class AppState:
    def __init__(self):
        self.lock = threading.Lock()
        # Camera
        self.camera_active = False
        self.cap: Optional[cv2.VideoCapture] = None
        # Mode
        self.mode = "predict"  # "learn" | "predict"
        # Model status
        self.model_status = "Ready"  # "Ready" | "Training" | "Not Loaded"
        # Last detection results (updated by the detector thread)
        self.detected_objects: list[dict] = []
        self.surface_boxes: dict[str, tuple] = {}
        self.last_surface_boxes: dict[str, tuple] = {}
        self.fps = 0.0
        self.inference_time_ms = 0.0
        self.frame_count = 0
        # Event log (newest first, capped at 50)
        self.events: list[dict] = []
        # ML components
        self.learned_rules: dict = {}
        self.data_collector = DataCollector(USAGE_DATA_PATH)
        # Personalized CatBoost model (written to models/personalized/ on retrain)
        self.personalized_predictor = PersonalizedCatBoostPredictor()
        # Immutable baseline CatBoost model (models/baseline/catboost_baseline.cbm)
        self.baseline_predictor = BaselineCatBoostPredictor()
        # Legacy shim kept for backward-compat — delegates to personalized predictor
        self.predictor = self.personalized_predictor
        # YOLO model (lazy-loaded)
        self.yolo = None
        # WebSocket clients
        self.ws_clients: list[WebSocket] = []
        # Last annotated JPEG bytes for the MJPEG stream endpoint.
        # Written by the detector thread, read by the stream endpoint.
        # Using bytes avoids any OpenCV Mat sharing issues.
        self.last_jpeg: Optional[bytes] = None
        # Auto-retrain tracking
        self.new_samples_since_retrain: int = 0   # incremented every time a sample is logged
        self.retrain_threshold: int = 5          # auto-retrain after this many new samples
        self.last_retrain_time: str = "Never"

    # ── helpers ──

    def log_event(self, type_: str, message: str):
        """Prepend a new event, keep the list at ≤ 50 items."""
        with self.lock:
            self.events.insert(
                0,
                {
                    "type": type_,
                    "message": message,
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                },
            )
            if len(self.events) > 50:
                self.events.pop()

    def load_learned_rules(self):
        try:
            with open(LEARNED_RULES_PATH, "r") as f:
                self.learned_rules = json.load(f)
        except Exception:
            self.learned_rules = {}

    def save_learned_rules(self):
        with open(LEARNED_RULES_PATH, "w") as f:
            json.dump(self.learned_rules, f, indent=2)

    def get_snapshot(self) -> dict:
        """Return a JSON-serialisable snapshot of the current state."""
        with self.lock:
            objects = list(self.detected_objects)
            events = list(self.events[:20])
            fps = self.fps
            inference_ms = self.inference_time_ms
            new_samples = self.new_samples_since_retrain
            retrain_threshold = self.retrain_threshold
            last_retrain = self.last_retrain_time

        # Strip internal-only fields before sending to frontend
        objects_for_ws = [
            {k: v for k, v in o.items() if k != "box"}
            for o in objects
        ]

        correctly_placed = sum(1 for o in objects if o.get("status") == "Correct")
        misplaced = sum(1 for o in objects if o.get("status") == "Misplaced")
        confidences = [o.get("confidence", 0.0) for o in objects]
        avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

        misplaced_obj = None
        for o in objects:
            if o.get("status") == "Misplaced":
                misplaced_obj = {
                    **o,
                    "recommendedSurface": o.get("predictedSurface", ""),
                    "explanation": (
                        f"Historical data shows {o.get('name', '')} is usually "
                        f"placed on the {o.get('predictedSurface', '')}."
                    ),
                }
                break

        # ── Learning data ──
        total_relationships = len(self.learned_rules)
        dataset_size = 0
        try:
            with open(USAGE_DATA_PATH, "r") as f:
                dataset_size = max(0, sum(1 for _ in f) - 1)
        except FileNotFoundError:
            pass

        learning_data = {
            "totalRelationships": total_relationships,
            "datasetSize": dataset_size,
            "newSamples": new_samples,
            "lastRetrainTime": last_retrain,
            "retrainThreshold": retrain_threshold,
        }

        # ── Active model info ──
        is_personalized = self.personalized_predictor.is_loaded
        if is_personalized:
            active_model = "personalized_model"
        elif self.baseline_predictor.is_loaded:
            active_model = "baseline_model"
        else:
            active_model = "default_rules"

        # ── Metrics: use active-model helper (personalized → baseline) ──
        metrics_data = get_active_metrics()

        return {
            "objects": objects,
            "events": events,
            "misplacedObject": misplaced_obj,
            "stats": {
                "totalObjects": len(objects),
                "totalSurfaces": len(self.surface_boxes),
                "correctlyPlaced": correctly_placed,
                "misplaced": misplaced,
                "fps": round(fps, 1),
                "inferenceTime": round(inference_ms, 1),
                "avgConfidence": avg_conf,
            },
            "mode": self.mode,
            "cameraActive": self.camera_active,
            "modelStatus": self.model_status,
            "activeModel": active_model,
            "learningData": learning_data,
            "metrics": metrics_data,
        }


state = AppState()

# Event loop reference — set during lifespan startup so the detector
# thread can schedule coroutines onto the asyncio thread safely.
_event_loop: Optional[asyncio.AbstractEventLoop] = None


# ─────────────────────────────────────────────
# Helper: overlap ratio (same logic as adaptive_organizer.py)
# ─────────────────────────────────────────────
def overlap_ratio(boxA, boxB) -> float:
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    inter_area = max(0, xB - xA) * max(0, yB - yA)
    boxA_area = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    return (inter_area / boxA_area) if boxA_area > 0 else 0.0


# ─────────────────────────────────────────────
# Shared retrain helper (used by auto-retrain + API endpoint)
# ─────────────────────────────────────────────
def _trigger_retrain():
    """Kick off personalized model retraining in a background thread."""
    with state.lock:
        if state.model_status == "Training":
            return
        state.model_status = "Training"

    def _train():
        try:
            metrics = train_and_evaluate(
                USAGE_DATA_PATH,
                PERSONALIZED_MODEL_PATH,
                None,                     # encoder_path unused by CatBoost
                PERSONALIZED_METRICS_PATH,
            )
            ts = metrics.get("last_retrain_time", datetime.now().strftime("%H:%M:%S"))
            with state.lock:
                state.personalized_predictor.reload()
                state.predictor = state.personalized_predictor   # keep shim in sync
                state.model_status = "Ready"
                state.new_samples_since_retrain = 0
                state.last_retrain_time = ts
            state.log_event(
                "success",
                f"Personalized retraining complete! "
                f"Accuracy: {metrics.get('accuracy', 0):.4f}  "
                f"ROC-AUC: {metrics.get('roc_auc', 0):.4f}"
            )
        except Exception as e:
            with state.lock:
                state.model_status = "Ready"
            state.log_event("error", f"Retraining failed: {e}")

    threading.Thread(target=_train, daemon=True).start()


# ─────────────────────────────────────────────
# Detector background thread
# ─────────────────────────────────────────────
def detector_thread():
    """
    Continuously reads frames from the camera, runs YOLO, updates shared state,
    and broadcasts over WebSocket. Runs in a daemon thread.
    """
    from ultralytics import YOLO

    with state.lock:
        state.yolo = YOLO("yolov8s.pt")
        state.load_learned_rules()

    state.log_event("info", "Detector thread started. Waiting for camera.")

    fps_timer = time.time()
    fps_frames = 0

    while True:
        # Wait until camera is activated
        if not state.camera_active or state.cap is None:
            time.sleep(0.1)
            continue

        with state.lock:
            cap = state.cap

        ret, frame = cap.read()
        if not ret:
            state.log_event("error", "Camera read failed. Retrying…")
            time.sleep(0.5)
            continue

        # Resize
        h, w = frame.shape[:2]
        scale = 0.7
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

        with state.lock:
            state.frame_count += 1
            fc = state.frame_count

        # Skip frames for performance — process every 3rd frame,
        # but always draw the annotated JPEG from the last processed frame
        if fc % 3 != 0:
            fps_frames += 1
            # Re-emit the last JPEG so the stream stays live even on skipped frames
            continue

        # ── Inference ──
        t0 = time.time()
        with state.lock:
            yolo = state.yolo
            mode = state.mode
            learned_rules = dict(state.learned_rules)

        results = yolo(frame, imgsz=416, conf=0.25, verbose=False)
        inference_ms = (time.time() - t0) * 1000

        # FPS
        fps_frames += 1
        elapsed = time.time() - fps_timer
        if elapsed >= 1.0:
            fps = fps_frames / elapsed
            fps_timer = time.time()
            fps_frames = 0
        else:
            with state.lock:
                fps = state.fps

        # ── Parse detections ──
        surface_boxes: dict[str, tuple] = {}
        detected: list[dict] = []

        for r in results:
            for box in r.boxes:
                cls = int(box.cls)
                label = yolo.names[cls]
                det_conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                if label in SURFACES:
                    sname = SURFACE_ALIASES.get(label, label)
                    surface_boxes[sname] = (x1, y1, x2, y2)

        for r in results:
            for box in r.boxes:
                cls = int(box.cls)
                label = yolo.names[cls]
                det_conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                if label in SURFACES:
                    continue  # already handled

                obj_box = (x1, y1, x2, y2)
                current_surface = None

                # What surface is the object currently on?
                for sname, sbox in surface_boxes.items():
                    if overlap_ratio(obj_box, sbox) > 0.3:
                        current_surface = sname
                        break

                # ── Learn mode: record this placement ──
                if mode == "learn" and current_surface is not None:
                    with state.lock:
                        state.learned_rules[label] = current_surface
                        state.save_learned_rules()
                        state.data_collector.log_sample(
                            label,
                            current_surface,
                            obj_box,
                            surface_boxes[current_surface],
                            det_conf,
                            frame.shape[:2],
                            is_positive=True,
                        )
                        state.new_samples_since_retrain += 1
                        # Negative samples for other surfaces
                        for other_name, other_box in surface_boxes.items():
                            if other_name != current_surface:
                                state.data_collector.log_sample(
                                    label,
                                    other_name,
                                    obj_box,
                                    other_box,
                                    det_conf,
                                    frame.shape[:2],
                                    is_positive=False,
                                )
                        # ── Auto-retrain check ──
                        should_retrain = (
                            state.new_samples_since_retrain >= state.retrain_threshold
                            and state.model_status == "Ready"
                        )
                    if should_retrain:
                        state.log_event("info", f"Auto-retrain triggered after {state.retrain_threshold} new samples.")
                        _trigger_retrain()

                # ── Predict expected surface (four-tier priority) ──
                # TIER 1: learned_rule       — user-observed placements
                # TIER 2: personalized_model — CatBoost trained on usage_data.csv
                # TIER 3: baseline_model     — immutable CatBoost (Visual Genome)
                # TIER 4: default_rule       — hardcoded fallback table
                expected_surface  = None
                prediction_source = "default_rule"

                # Tier 1 — personalized rules (Learn Mode observations)
                if label in learned_rules:
                    expected_surface  = learned_rules[label]
                    prediction_source = "learned_rule"

                # Tier 2 — personalized CatBoost model
                if expected_surface is None and state.personalized_predictor.is_loaded and surface_boxes:
                    predicted, _ = state.personalized_predictor.predict(
                        label, surface_boxes, obj_box, det_conf, frame.shape[:2]
                    )
                    if predicted is not None:
                        expected_surface  = predicted
                        prediction_source = "personalized_model"

                # Tier 3 — CatBoost baseline (static general knowledge)
                if expected_surface is None and state.baseline_predictor.is_loaded and surface_boxes:
                    predicted, _ = state.baseline_predictor.predict(
                        label, surface_boxes, obj_box, det_conf, frame.shape[:2]
                    )
                    if predicted is not None:
                        expected_surface  = predicted
                        prediction_source = "baseline_model"

                # Tier 4 — hardcoded DEFAULT_RULES
                if expected_surface is None:
                    expected_surface = DEFAULT_RULES.get(label)
                    if expected_surface:
                        prediction_source = "default_rule"

                # ── Determine placement status ──
                is_correct = False
                if expected_surface and expected_surface in surface_boxes:
                    if overlap_ratio(obj_box, surface_boxes[expected_surface]) > 0.3:
                        is_correct = True
                elif expected_surface and current_surface == expected_surface:
                    is_correct = True

                detected.append(
                    {
                        "name": label,
                        "currentSurface": current_surface or "Unknown",
                        "predictedSurface": expected_surface or "Unknown",
                        "confidence": round(det_conf, 3),
                        "status": "Correct" if is_correct else "Misplaced",
                        "predictionSource": prediction_source,
                        # bbox carried for annotation drawing
                        "box": [x1, y1, x2, y2],
                    }
                )

                # Log misplacement event
                if not is_correct and expected_surface:
                    state.log_event(
                        "warning",
                        f"{label} detected on {current_surface or 'unknown'} "
                        f"(expected: {expected_surface})",
                    )

        # ── Update shared state ──
        with state.lock:
            state.detected_objects = detected
            # Keep surface boxes: use current detections; fall back to last known
            # so boxes don't vanish on a single missed frame
            if surface_boxes:
                state.surface_boxes = surface_boxes
                state.last_surface_boxes.update(surface_boxes)
            else:
                # no surfaces this frame — keep last known so drawing is stable
                state.surface_boxes = dict(state.last_surface_boxes)
            state.fps = fps
            state.inference_time_ms = inference_ms

        # ── Draw annotations on a copy and save as JPEG for the stream ──
        annotated = frame.copy()
        with state.lock:
            surf_boxes_copy = dict(state.surface_boxes)
            mode_copy = state.mode

        # ── Draw surface boxes ──
        for sname, (x1, y1, x2, y2) in surf_boxes_copy.items():
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 255, 0), 2)
            cv2.putText(annotated, f"[{sname}]", (x1, max(y1 - 4, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)

        # ── Draw object boxes (bbox stored in detected list) ──
        for obj in detected:
            box = obj.get("box")
            if not box:
                continue
            bx1, by1, bx2, by2 = box
            color = (0, 255, 0) if obj["status"] == "Correct" else (0, 0, 255)
            cv2.rectangle(annotated, (bx1, by1), (bx2, by2), color, 2)
            src_tag = obj.get("predictionSource", "")[:3].upper()
            tag = (f"{obj['name']} OK [{src_tag}]"
                   if obj["status"] == "Correct"
                   else f"{obj['name']}->{obj['predictedSurface']} [{src_tag}]")
            tag_y = max(by1 - 6, 12)
            (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(annotated, (bx1, tag_y - th - 2), (bx1 + tw + 2, tag_y + 2), (0, 0, 0), -1)
            cv2.putText(annotated, tag, (bx1 + 1, tag_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

        cv2.putText(annotated, f"MODE: {mode_copy.upper()}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(annotated, f"FPS: {fps:.1f}", (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            with state.lock:
                state.last_jpeg = buf.tobytes()

        # ── Broadcast over WebSocket (thread-safe via event loop) ──
        snapshot = state.get_snapshot()
        if _event_loop is not None and _event_loop.is_running():
            asyncio.run_coroutine_threadsafe(_broadcast(snapshot), _event_loop)


async def _broadcast(data: dict):
    """Send JSON snapshot to all connected WebSocket clients."""
    dead = []
    for ws in list(state.ws_clients):
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        try:
            state.ws_clients.remove(ws)
        except ValueError:
            pass


# ─────────────────────────────────────────────
# App lifespan — start detector thread
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _event_loop
    _event_loop = asyncio.get_running_loop()
    t = threading.Thread(target=detector_thread, daemon=True)
    t.start()
    yield


# ─────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────
app = FastAPI(title="Cortexium XR API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# REST Endpoints
# ─────────────────────────────────────────────

@app.get("/api/dashboard")
def get_dashboard():
    """
    Returns semi-static dashboard data: model metrics, learning info, and current stats.
    Called once on page load; live updates come via WebSocket.
    """
    # Stats (current snapshot)
    snap = state.get_snapshot()

    # Learning info
    state.load_learned_rules()
    total_relationships = len(state.learned_rules)
    dataset_size = 0
    try:
        with open(USAGE_DATA_PATH, "r") as f:
            dataset_size = max(0, sum(1 for _ in f) - 1)  # subtract header
    except FileNotFoundError:
        dataset_size = 0

    last_retrain_time = "Never"
    metrics_data = get_active_metrics() or {
        "accuracy": 0.0, "precision": 0.0, "recall": 0.0,
        "f1Score": 0.0, "cvScore": 0.0,
        "confusionMatrix": [], "classes": [], "featureImportance": {},
    }
    last_retrain_time = metrics_data.get("last_retrain_time", "Never")

    return {
        "stats": snap["stats"],
        "learningData": {
            "totalRelationships": total_relationships,
            "datasetSize": dataset_size,
            "lastRetrainTime": last_retrain_time,
        },
        "metrics": metrics_data,
    }


@app.post("/api/camera/start")
def start_camera():
    """Open the system default camera capture."""
    if state.camera_active and state.cap is not None:
        return {"status": "already_running", "message": "Camera is already active."}

    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        state.log_event("error", f"Failed to open system camera (index {CAMERA_INDEX})")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": f"Cannot open system camera (index {CAMERA_INDEX}). Check that a webcam is connected and permissions are granted."},
        )

    with state.lock:
        state.cap = cap
        state.camera_active = True

    state.log_event("success", f"System camera connected (index {CAMERA_INDEX}).")
    return {"status": "ok", "message": "Camera started."}


@app.post("/api/camera/stop")
def stop_camera():
    """Release the camera capture."""
    with state.lock:
        if state.cap is not None:
            state.cap.release()
            state.cap = None
        state.camera_active = False
        state.detected_objects = []
        state.surface_boxes = {}

    state.log_event("info", "Camera stopped.")
    return {"status": "ok", "message": "Camera stopped."}


@app.post("/api/mode")
async def set_mode(body: dict):
    """
    Switch between learn and predict modes.
    Body: { "mode": "learn" | "predict" }
    """
    new_mode = body.get("mode", "predict").lower()
    if new_mode not in ("learn", "predict"):
        return JSONResponse(status_code=400, content={"error": "mode must be 'learn' or 'predict'"})

    with state.lock:
        state.mode = new_mode

    state.log_event("info", f"Mode switched to: {new_mode.upper()}")
    return {"status": "ok", "mode": new_mode}


@app.post("/api/retrain")
async def retrain_model():
    """Trigger model retraining (manual fallback endpoint)."""
    with state.lock:
        if state.model_status == "Training":
            return {"status": "already_training", "message": "Training is already in progress."}
    state.log_event("info", "Manual retraining triggered.")
    _trigger_retrain()
    return {"status": "ok", "message": "Retraining started."}


@app.post("/api/reset")
def reset_learning():
    """Reset to baseline: clear learned rules and disable personalized model.

    - learned_rules.json is cleared (existing behaviour preserved)
    - Personalized model is disabled in memory and its file removed
    - Baseline CatBoost remains active
    - Baseline model file is NEVER touched
    """
    import os as _os
    with state.lock:
        state.learned_rules = {}
        state.new_samples_since_retrain = 0
        # Disable personalized model in memory
        state.personalized_predictor.disable()
    state.save_learned_rules()

    # Remove personalized model file so it doesn't reload on next restart
    for path in [PERSONALIZED_MODEL_PATH, PERSONALIZED_METRICS_PATH]:
        try:
            if _os.path.exists(path):
                _os.remove(path)
        except Exception:
            pass

    state.log_event(
        "warning",
        "Reset to baseline. Learned rules cleared. "
        "Baseline CatBoost is now active."
    )
    return {
        "status": "ok",
        "message": "Reset complete. Baseline CatBoost is active.",
        "activeModel": "baseline_model",
    }


@app.get("/api/metrics")
def get_metrics():
    """Download the latest metrics.json."""
    if not os.path.exists(METRICS_PATH):
        return JSONResponse(status_code=404, content={"error": "metrics.json not found. Run retraining first."})
    return FileResponse(METRICS_PATH, media_type="application/json", filename="cortexium_metrics.json")


@app.get("/api/export/dataset")
def export_dataset():
    """Download the usage_data.csv training dataset."""
    if not os.path.exists(USAGE_DATA_PATH):
        return JSONResponse(status_code=404, content={"error": "usage_data.csv not found."})
    return FileResponse(USAGE_DATA_PATH, media_type="text/csv", filename="cortexium_dataset.csv")


@app.get("/api/camera/stream")
def camera_stream():
    """
    MJPEG stream endpoint.

    The detector thread continuously updates state.last_jpeg with the
    latest annotated frame. This endpoint simply serves those bytes as
    a proper MJPEG stream — no second VideoCapture, no race condition.

    The <img> tag in CameraFeed can point its src directly here.
    """
    HEADER = (
        b"--cortexframe\r\n"
        b"Content-Type: image/jpeg\r\n"
        b"\r\n"
    )

    def generate():
        # Send a placeholder black frame until real frames arrive
        placeholder = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(placeholder, "Waiting for camera...", (120, 180),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (100, 100, 100), 2)
        _, placeholder_buf = cv2.imencode(".jpg", placeholder)
        placeholder_bytes = placeholder_buf.tobytes()

        last_sent: Optional[bytes] = None

        while True:
            with state.lock:
                jpeg = state.last_jpeg

            if jpeg is None:
                # No frame yet — send placeholder at ~5 fps
                yield HEADER + placeholder_bytes + b"\r\n"
                time.sleep(0.2)
                continue

            # Only send when a new frame is ready (avoids duplicate transmissions)
            if jpeg is not last_sent:
                last_sent = jpeg
                yield HEADER + jpeg + b"\r\n"

            time.sleep(0.033)  # cap at ~30 fps

    return StreamingResponse(
        generate(),
        media_type=f"multipart/x-mixed-replace; boundary=cortexframe",
    )


# ─────────────────────────────────────────────
# WebSocket endpoint
# ─────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket that pushes live detection data to connected clients every ~500 ms.
    Each message is a JSON object matching the shape expected by useLiveStream().
    """
    await websocket.accept()
    state.ws_clients.append(websocket)
    state.log_event("info", "Dashboard client connected via WebSocket.")

    try:
        # Send current snapshot immediately on connect
        await websocket.send_json(state.get_snapshot())

        # Keep the connection alive; the detector thread broadcasts updates.
        # Also push a heartbeat every 2 s in case no detections are happening.
        while True:
            await asyncio.sleep(2)
            await websocket.send_json(state.get_snapshot())

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        try:
            state.ws_clients.remove(websocket)
        except ValueError:
            pass
        state.log_event("info", "Dashboard client disconnected.")

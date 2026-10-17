"""
organizer.py — Cortexium Organizer Module Router

Mounts all Adaptive Organizer endpoints under /organizer/* prefix so the
organizer module can share the social module's backend (port 8005).

All organizer state is completely isolated from the social module state.
The detector thread and camera lifecycle are managed independently here.

Camera source can be:
  - An integer index (0, 1, 2 …) for local USB/built-in webcams
  - An HTTP/RTSP URL string for IP cameras (e.g. "http://192.168.1.106:8080/video")
  - A DroidCam/IP Webcam URL (e.g. "http://192.168.1.106:4747/video")

Endpoints:
    GET  /organizer/dashboard
    POST /organizer/camera/start
    POST /organizer/camera/stop
    GET  /organizer/camera/stream
    GET  /organizer/camera/source
    POST /organizer/camera/source
    POST /organizer/mode
    POST /organizer/retrain
    POST /organizer/reset
    GET  /organizer/metrics
    GET  /organizer/export/dataset
    GET  /organizer/rules
    POST /organizer/feedback
    WS   /organizer/ws
"""

import asyncio
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

# Suppress raw OpenCV/FFmpeg C-level console noise before importing cv2
os.environ["OPENCV_LOG_LEVEL"] = "SILENT"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;3000000|stimeout;3000000|rtsp_transport;tcp"

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

# ─────────────────────────────────────────────
# Add organizer clone directory to sys.path
# so ml_pipeline and related modules can be imported
# ─────────────────────────────────────────────
_ORGANIZER_DIR = Path(__file__).resolve().parent.parent.parent / "cortexium-organizer-clone"
if str(_ORGANIZER_DIR) not in sys.path:
    sys.path.insert(0, str(_ORGANIZER_DIR))

# All file-relative paths from the original server.py are resolved here absolutely.
_ORGANIZER_DATA_DIR = _ORGANIZER_DIR

LEARNED_RULES_PATH = str(_ORGANIZER_DATA_DIR / "learned_rules.json")
USAGE_DATA_PATH    = str(_ORGANIZER_DATA_DIR / "usage_data.csv")
CAMERA_CONFIG_PATH = str(_ORGANIZER_DATA_DIR / "camera_config.json")
YOLO_NANO_PATH     = str(_ORGANIZER_DATA_DIR / "yolov8n.pt")
YOLO_MODEL_PATH    = YOLO_NANO_PATH if os.path.exists(YOLO_NANO_PATH) else str(_ORGANIZER_DATA_DIR / "yolov8s.pt")

try:
    import torch
    if hasattr(torch, "set_num_threads"):
        torch.set_num_threads(min(8, os.cpu_count() or 4))
except Exception:
    pass

# ─────────────────────────────────────────────
# Camera source — integer index OR IP URL string
# This can be changed at runtime via POST /organizer/camera/source
# or patched by change_ports.py (--camera flag)
# ─────────────────────────────────────────────
# CAMERA_SOURCE = "http://10.207.120.163:8080/video"   ← local webcam (default)
# CAMERA_SOURCE = "http://10.207.120.163:8080/video"  ← Android IP Webcam
# CAMERA_SOURCE = "http://10.207.120.163:8080/video"  ← RTSP
_cam_env = os.environ.get("CAMERA_SOURCE", "")
CAMERA_SOURCE: Union[int, str] = _cam_env if _cam_env else 0

from ml_pipeline import (  # noqa: E402  (after sys.path update)
    DataCollector,
    BaselineCatBoostPredictor,
    PersonalizedCatBoostPredictor,
    train_and_evaluate,
    get_active_metrics,
    PERSONALIZED_MODEL_PATH,
    PERSONALIZED_METRICS_PATH,
)

METRICS_PATH = PERSONALIZED_METRICS_PATH

# ─────────────────────────────────────────────
# Constants (same as original server.py)
# ─────────────────────────────────────────────
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
# Isolated Organizer State
# ─────────────────────────────────────────────
class OrganizerState:
    def __init__(self):
        self.lock = threading.RLock()
        self.camera_lock = threading.RLock()
        # Camera
        self.camera_active = False
        self.cap: Optional[cv2.VideoCapture] = None
        # Camera source (mirrors the module-level CAMERA_SOURCE, or loads from saved camera_config.json)
        self.camera_source: Union[int, str] = CAMERA_SOURCE
        try:
            cfg_path = os.path.join(str(_ORGANIZER_DIR), "camera_config.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r") as f:
                    saved_s = json.load(f).get("source", "")
                    if saved_s != "":
                        self.camera_source = int(saved_s) if str(saved_s).isdigit() else saved_s
        except Exception:
            pass
        # Mode
        self.mode = "predict"
        # Model status
        self.model_status = "Ready"
        # Last detection results
        self.detected_objects: list[dict] = []
        self.surface_boxes: dict[str, tuple] = {}
        # FIX Bug 3: persist last known surface boxes so they don't vanish on missed frames
        self.last_surface_boxes: dict[str, tuple] = {}
        self.fps = 0.0
        self.inference_time_ms = 0.0
        self.frame_count = 0
        # Event log (newest first, capped at 50)
        self.events: list[dict] = []
        # ML components
        self.learned_rules: dict = {}
        self.data_collector = DataCollector(USAGE_DATA_PATH)
        self.personalized_predictor = PersonalizedCatBoostPredictor()
        self.baseline_predictor = BaselineCatBoostPredictor()
        # YOLO model (lazy-loaded by detector thread)
        self.yolo = None
        # WebSocket clients
        self.ws_clients: list[WebSocket] = []
        # Last annotated JPEG bytes for the MJPEG stream
        self.last_jpeg: Optional[bytes] = None
        # Auto-retrain tracking
        self.new_samples_since_retrain: int = 0
        self.retrain_threshold: int = 20
        self.last_retrain_time: str = "Never"
        self.dataset_size: int = 0
        self.update_dataset_size()

    def update_dataset_size(self):
        try:
            with open(USAGE_DATA_PATH, "r") as f:
                self.dataset_size = max(0, sum(1 for _ in f) - 1)
        except Exception:
            self.dataset_size = 0

    def safe_release_camera(self):
        """Thread-safe release of the camera capture to prevent FFmpeg C assertion race conditions."""
        with self.camera_lock:
            self.camera_active = False
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception as e:
                    print(f"[Organizer] cap.release error: {e}")
                self.cap = None

    def log_event(self, type_: str, message: str):
        with self.lock:
            self.events.insert(0, {
                "type": type_,
                "message": message,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            })
            if len(self.events) > 50:
                self.events.pop()

    def load_learned_rules(self):
        try:
            with open(LEARNED_RULES_PATH, "r") as f:
                self.learned_rules = json.load(f)
        except Exception:
            self.learned_rules = {}

    def save_learned_rules(self):
        try:
            with open(LEARNED_RULES_PATH, "w") as f:
                json.dump(self.learned_rules, f, indent=2)
        except Exception:
            pass

    def get_snapshot(self) -> dict:
        with self.lock:
            objects = list(self.detected_objects)
            events = list(self.events[:20])
            fps = self.fps
            inference_ms = self.inference_time_ms
            new_samples = self.new_samples_since_retrain
            retrain_threshold = self.retrain_threshold
            last_retrain = self.last_retrain_time
            camera_source = self.camera_source
            total_relationships = len(self.learned_rules)
            dataset_size = self.dataset_size
            curr_mode = self.mode
            curr_camera_active = self.camera_active
            curr_model_status = self.model_status
            surfaces_count = len(self.surface_boxes)

        # Strip internal-only fields before sending to frontend
        objects_for_ws = [{k: v for k, v in o.items() if k != "box"} for o in objects]

        correctly_placed = sum(1 for o in objects if o.get("status") == "Correct")
        misplaced = sum(1 for o in objects if o.get("status") == "Misplaced")
        confidences = [o.get("confidence", 0.0) for o in objects]
        avg_conf = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

        misplaced_obj = None
        for o in objects:
            if o.get("status") == "Misplaced":
                misplaced_obj = {
                    **{k: v for k, v in o.items() if k != "box"},
                    "recommendedSurface": o.get("predictedSurface", ""),
                    "explanation": (
                        f"Learned relationship shows {o.get('name', '')} belongs on "
                        f"the {o.get('predictedSurface', '')}."
                    ),
                }
                break

        learning_data = {
            "totalRelationships": total_relationships,
            "datasetSize": dataset_size,
            "newSamples": new_samples,
            "lastRetrainTime": last_retrain,
            "retrainThreshold": retrain_threshold,
        }

        is_personalized = self.personalized_predictor.is_loaded
        if is_personalized:
            active_model = "personalized_model"
        elif self.baseline_predictor.is_loaded:
            active_model = "baseline_model"
        else:
            active_model = "default_rules"

        metrics_data = get_active_metrics()

        return {
            "objects": objects_for_ws,
            "events": events,
            "misplacedObject": misplaced_obj,
            "stats": {
                "totalObjects": len(objects),
                "totalTracked": len(objects),
                "totalSurfaces": surfaces_count,
                "correctlyPlaced": correctly_placed,
                "correctCount": correctly_placed,
                "misplaced": misplaced,
                "misplacedCount": misplaced,
                "fps": round(fps, 1),
                "inferenceTime": round(inference_ms, 1),
                "inferenceTimeMs": round(inference_ms, 1),
                "avgConfidence": avg_conf,
            },
            "mode": curr_mode,
            "cameraActive": curr_camera_active,
            "modelStatus": curr_model_status,
            "activeModel": active_model,
            "learningData": learning_data,
            "metrics": metrics_data,
            "cameraSource": str(camera_source),
        }


org_state = OrganizerState()

# FIX Bug 1: store event loop reference — set from lifespan via start_organizer_background()
_org_event_loop: Optional[asyncio.AbstractEventLoop] = None


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def overlap_ratio(boxA, boxB) -> float:
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    inter_area = max(0, xB - xA) * max(0, yB - yA)
    boxA_area = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    return (inter_area / boxA_area) if boxA_area > 0 else 0.0


def _trigger_retrain():
    """Kick off personalized model retraining in a background thread."""
    with org_state.lock:
        if org_state.model_status == "Training":
            return
        org_state.model_status = "Training"

    def _train():
        try:
            metrics = train_and_evaluate(
                USAGE_DATA_PATH,
                PERSONALIZED_MODEL_PATH,
                None,
                PERSONALIZED_METRICS_PATH,
            )
            ts = metrics.get("last_retrain_time", datetime.now().strftime("%H:%M:%S"))
            with org_state.lock:
                org_state.personalized_predictor.reload()
                org_state.predictor = org_state.personalized_predictor
                org_state.model_status = "Ready"
                org_state.new_samples_since_retrain = 0
                org_state.last_retrain_time = ts
            org_state.log_event(
                "success",
                f"Personalized retraining complete! "
                f"Accuracy: {metrics.get('accuracy', 0):.4f}  "
                f"ROC-AUC: {metrics.get('roc_auc', 0):.4f}",
            )
        except Exception as e:
            with org_state.lock:
                org_state.model_status = "Ready"
            org_state.log_event("error", f"Retraining failed: {e}")

    threading.Thread(target=_train, daemon=True).start()


# ─────────────────────────────────────────────
# Decoupled High-Speed Pipeline
#   Thread 1: Camera capture & MJPEG streaming (smooth 25-30 FPS)
#   Thread 2: Asynchronous YOLO & ML Inference (runs on latest available frame)
# ─────────────────────────────────────────────
_inference_lock = threading.Lock()
_latest_inference_frame: Optional[np.ndarray] = None
_new_frame_event = threading.Event()
_inference_busy = False


def _inference_worker():
    """Background worker that continuously processes the newest captured frame with YOLO and CatBoost."""
    global _latest_inference_frame, _inference_busy

    while True:
        _new_frame_event.wait(timeout=0.1)
        if not org_state.camera_active:
            _new_frame_event.clear()
            time.sleep(0.05)
            continue

        frame_to_process = None
        with _inference_lock:
            if _latest_inference_frame is not None:
                frame_to_process = _latest_inference_frame
                _latest_inference_frame = None
                _inference_busy = True
            _new_frame_event.clear()

        if frame_to_process is None:
            continue

        try:
            t0 = time.time()
            with org_state.lock:
                yolo = org_state.yolo
                mode = org_state.mode
                learned_rules = dict(org_state.learned_rules)
                fc = org_state.frame_count

            if yolo is None:
                continue

            # Run YOLO with imgsz=320 for high-speed CPU inference (~60ms)
            results = yolo(frame_to_process, imgsz=320, conf=0.25, verbose=False)
            inference_ms = (time.time() - t0) * 1000

            h, w = frame_to_process.shape[:2]

            # ── Parse detections — surfaces first ──
            surface_boxes: dict[str, tuple] = {}
            detected: list[dict] = []

            for r in results:
                for box in r.boxes:
                    cls = int(box.cls)
                    label = yolo.names[cls]
                    if label in SURFACES:
                        sname = SURFACE_ALIASES.get(label, label)
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        surface_boxes[sname] = (x1, y1, x2, y2)

            with org_state.lock:
                if surface_boxes:
                    org_state.last_surface_boxes.update(surface_boxes)
                else:
                    surface_boxes = dict(org_state.last_surface_boxes)

            if not surface_boxes or "table" not in surface_boxes:
                surface_boxes["table"] = (0, int(h * 0.25), w, h)

            # ── Parse objects (non-surfaces) ──
            for r in results:
                for box in r.boxes:
                    cls = int(box.cls)
                    label = yolo.names[cls]
                    det_conf = float(box.conf[0])
                    x1, y1, x2, y2 = map(int, box.xyxy[0])

                    if label in SURFACES:
                        continue

                    obj_box = (x1, y1, x2, y2)

                    # Determine current surface
                    current_surface = None
                    best_overlap = 0.0
                    for sname, sbox in surface_boxes.items():
                        if sname == "table" and sbox == (0, int(h * 0.25), w, h):
                            continue
                        ov = overlap_ratio(obj_box, sbox)
                        if ov > 0.15 and ov > best_overlap:
                            best_overlap = ov
                            current_surface = sname

                    if current_surface is None and "table" in surface_boxes:
                        table_box = surface_boxes["table"]
                        if overlap_ratio(obj_box, table_box) > 0.15:
                            current_surface = "table"

                    # ── Learn mode: record placement ──
                    if mode == "learn" and current_surface is not None:
                        rule_changed = False
                        with org_state.lock:
                            prev_rule = org_state.learned_rules.get(label)
                            if prev_rule != current_surface:
                                rule_changed = True
                                org_state.learned_rules[label] = current_surface
                                learned_rules[label] = current_surface

                        if rule_changed:
                            org_state.save_learned_rules()
                            org_state.log_event("success", f"Learned rule: {label} belongs on {current_surface}")

                        if rule_changed or (fc % 10 == 0):
                            try:
                                sbox_to_log = surface_boxes.get(current_surface, (0, int(h * 0.25), w, h))
                                org_state.data_collector.log_sample(
                                    label,
                                    current_surface,
                                    obj_box,
                                    sbox_to_log,
                                    det_conf,
                                    frame_to_process.shape[:2],
                                    is_positive=True,
                                )
                                with org_state.lock:
                                    org_state.new_samples_since_retrain += 1
                                    org_state.dataset_size += 1
                            except Exception:
                                pass

                            for other_name, other_box in surface_boxes.items():
                                if other_name != current_surface:
                                    try:
                                        org_state.data_collector.log_sample(
                                            label,
                                            other_name,
                                            obj_box,
                                            other_box,
                                            det_conf,
                                            frame_to_process.shape[:2],
                                            is_positive=False,
                                        )
                                    except Exception:
                                        pass

                        should_retrain = False
                        with org_state.lock:
                            if (
                                org_state.new_samples_since_retrain >= org_state.retrain_threshold
                                and org_state.model_status == "Ready"
                            ):
                                should_retrain = True
                        if should_retrain:
                            org_state.log_event(
                                "info",
                                f"Auto-retrain triggered after {org_state.retrain_threshold} new samples.",
                            )
                            _trigger_retrain()

                    # ── Predict expected surface ──
                    expected_surface = None
                    prediction_source = "default_rule"

                    if label in learned_rules:
                        expected_surface = learned_rules[label]
                        prediction_source = "learned_rule"

                    if expected_surface is None and org_state.personalized_predictor.is_loaded and surface_boxes:
                        try:
                            predicted, _ = org_state.personalized_predictor.predict(
                                label, surface_boxes, obj_box, det_conf, frame_to_process.shape[:2]
                            )
                            if predicted is not None:
                                expected_surface = predicted
                                prediction_source = "personalized_model"
                        except Exception:
                            pass

                    if expected_surface is None and org_state.baseline_predictor.is_loaded and surface_boxes:
                        try:
                            predicted, _ = org_state.baseline_predictor.predict(
                                label, surface_boxes, obj_box, det_conf, frame_to_process.shape[:2]
                            )
                            if predicted is not None:
                                expected_surface = predicted
                                prediction_source = "baseline_model"
                        except Exception:
                            pass

                    if expected_surface is None:
                        expected_surface = DEFAULT_RULES.get(label, "table")
                        prediction_source = "default_rule"

                    is_correct = False
                    if mode == "learn":
                        is_correct = True
                    elif expected_surface and current_surface == expected_surface:
                        is_correct = True
                    elif expected_surface and expected_surface in surface_boxes:
                        if overlap_ratio(obj_box, surface_boxes[expected_surface]) > 0.15:
                            is_correct = True

                    detected.append({
                        "name": label,
                        "confidence": round(det_conf, 3),
                        "currentSurface": current_surface or "unknown",
                        "predictedSurface": expected_surface or "table",
                        "status": "Correct" if is_correct else "Misplaced",
                        "predictionSource": prediction_source,
                        "box": (x1, y1, x2, y2),
                    })

                    if not is_correct and expected_surface and mode != "learn":
                        org_state.log_event(
                            "warning",
                            f"{label} detected on {current_surface or 'unknown'} "
                            f"(expected: {expected_surface})",
                        )

            # ── Atomically update shared detection results ──
            with org_state.lock:
                org_state.detected_objects = detected
                org_state.surface_boxes = surface_boxes
                org_state.inference_time_ms = inference_ms

            # Broadcast WebSocket snapshot with new detections immediately
            if org_state.ws_clients and MAIN_EVENT_LOOP and MAIN_EVENT_LOOP.is_running():
                snapshot = org_state.get_snapshot()
                asyncio.run_coroutine_threadsafe(_org_broadcast(snapshot), MAIN_EVENT_LOOP)

        except Exception as e:
            print(f"[Organizer] Inference error: {e}")
        finally:
            with _inference_lock:
                _inference_busy = False


def _detector_thread():
    """
    High-speed camera capture and streaming loop.
    Reads camera at native 30 FPS, overlays current detection bounding boxes,
    and dispatches frames asynchronously to the inference worker.
    """
    global _latest_inference_frame, _inference_busy

    from ultralytics import YOLO

    with org_state.lock:
        org_state.yolo = YOLO(YOLO_MODEL_PATH)
        org_state.load_learned_rules()

    # Launch inference worker thread
    inf_thread = threading.Thread(target=_inference_worker, daemon=True)
    inf_thread.start()

    org_state.log_event("info", f"Organizer detector initialized with {os.path.basename(YOLO_MODEL_PATH)}. Camera ready.")

    fps_timer = time.time()
    fps_frames = 0
    last_ws_broadcast = time.time()

    consecutive_failures = 0
    reconnect_attempts = 0

    while True:
        if not org_state.camera_active:
            consecutive_failures = 0
            reconnect_attempts = 0
            time.sleep(0.05)
            continue

        with org_state.camera_lock:
            if not org_state.camera_active or org_state.cap is None or not org_state.cap.isOpened():
                time.sleep(0.05)
                continue
            ret, frame = org_state.cap.read()

        if not ret or frame is None:
            consecutive_failures += 1
            if consecutive_failures >= 60:  # ~3-4 seconds of failures
                consecutive_failures = 0
                reconnect_attempts += 1
                if reconnect_attempts <= 5:
                    org_state.log_event("warning", f"Camera read stutter. Attempting background reconnect ({reconnect_attempts}/5)...")
                    with org_state.camera_lock:
                        if org_state.cap is not None:
                            try:
                                org_state.cap.release()
                            except Exception:
                                pass
                            org_state.cap = None
                        source = org_state.camera_source
                        if isinstance(source, str) and (source.startswith("http://") or source.startswith("https://") or source.startswith("rtsp://")):
                            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;8000000|stimeout;8000000|rtsp_transport;tcp"
                        new_cap = cv2.VideoCapture(source)
                        if not isinstance(source, str) or not (source.startswith("http://") or source.startswith("https://")):
                            new_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        if new_cap.isOpened():
                            org_state.cap = new_cap
                            org_state.log_event("success", "Camera background reconnected successfully.")
                            reconnect_attempts = 0
                            continue
                org_state.log_event("error", "Camera stream disconnected after retries. Stopping camera.")
                org_state.safe_release_camera()
                reconnect_attempts = 0
            time.sleep(0.05)
            continue

        consecutive_failures = 0
        reconnect_attempts = 0

        h, w = frame.shape[:2]
        scale = 0.7
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))

        with org_state.lock:
            org_state.frame_count += 1

        # Dispatch newest frame to inference worker if worker is ready
        with _inference_lock:
            if not _inference_busy:
                _latest_inference_frame = frame.copy()
                _new_frame_event.set()

        # Update FPS rolling counter
        fps_frames += 1
        now = time.time()
        elapsed = now - fps_timer
        if elapsed >= 0.5:
            stream_fps = fps_frames / elapsed
            fps_timer = now
            fps_frames = 0
            with org_state.lock:
                org_state.fps = round(stream_fps, 1)

        # Snapshot detection data for annotation
        with org_state.lock:
            draw_surfaces = dict(org_state.surface_boxes)
            draw_objects = list(org_state.detected_objects)
            draw_mode = org_state.mode
            draw_fps = org_state.fps

        # ── Draw annotations at full frame rate ──
        annotated = frame.copy()
        for sname, sbox in draw_surfaces.items():
            if sname == "table" and sbox == (0, int(h * 0.25), w, h):
                continue
            cv2.rectangle(annotated, sbox[:2], sbox[2:], (255, 255, 0), 2)
            cv2.putText(annotated, f"[{sname}]", (sbox[0], max(sbox[1] - 4, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)

        for obj in draw_objects:
            box = obj.get("box")
            if not box:
                continue
            bx1, by1, bx2, by2 = box
            color = (0, 255, 0) if obj.get("status") == "Correct" else (0, 0, 255)
            if draw_mode == "learn":
                color = (0, 200, 255)  # Cyan/Amber during learn mode
            cv2.rectangle(annotated, (bx1, by1), (bx2, by2), color, 2)
            src_tag = obj.get("predictionSource", "")[:3].upper()
            tag = (f"{obj['name']} [LEARN->{obj.get('currentSurface', 'unknown')}]"
                   if draw_mode == "learn"
                   else f"{obj['name']} OK [{src_tag}]"
                   if obj.get("status") == "Correct"
                   else f"{obj['name']}->{obj.get('predictedSurface', 'table')} [{src_tag}]")
            tag_y = max(by1 - 6, 12)
            (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(annotated, (bx1, tag_y - th - 2), (bx1 + tw + 2, tag_y + 2), (0, 0, 0), -1)
            cv2.putText(annotated, tag, (bx1 + 1, tag_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

        cv2.putText(annotated, f"MODE: {draw_mode.upper()}", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(annotated, f"FPS: {draw_fps:.1f}", (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            with org_state.lock:
                org_state.last_jpeg = buf.tobytes()

        # Periodic WebSocket sync for FPS card (every 1.0s)
        if now - last_ws_broadcast >= 1.0:
            last_ws_broadcast = now
            if org_state.ws_clients and MAIN_EVENT_LOOP and MAIN_EVENT_LOOP.is_running():
                snapshot = org_state.get_snapshot()
                asyncio.run_coroutine_threadsafe(_org_broadcast(snapshot), MAIN_EVENT_LOOP)

        time.sleep(0.01)  # short pause to cap at ~30 FPS smoothly


# ─────────────────────────────────────────────
# WebSocket Broadcast Helper & Startup
# ─────────────────────────────────────────────
MAIN_EVENT_LOOP: Optional[asyncio.AbstractEventLoop] = None


async def _org_broadcast(data: dict):
    with org_state.lock:
        clients = list(org_state.ws_clients)
    dead = []
    msg = json.dumps(data)
    for ws in clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    if dead:
        with org_state.lock:
            for d in dead:
                if d in org_state.ws_clients:
                    org_state.ws_clients.remove(d)


def start_organizer_background(loop: asyncio.AbstractEventLoop):
    global MAIN_EVENT_LOOP
    MAIN_EVENT_LOOP = loop
    threading.Thread(target=_detector_thread, daemon=True).start()


# ─────────────────────────────────────────────
# FastAPI Router
# ─────────────────────────────────────────────
router = APIRouter(prefix="/organizer", tags=["organizer"])


@router.get("/dashboard")
def org_get_dashboard():
    """Returns dashboard snapshot: stats, learning data, metrics."""
    snap = org_state.get_snapshot()
    org_state.load_learned_rules()
    total_relationships = len(org_state.learned_rules)
    dataset_size = 0
    try:
        with open(USAGE_DATA_PATH, "r") as f:
            dataset_size = max(0, sum(1 for _ in f) - 1)
    except FileNotFoundError:
        pass

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
        "cameraSource": str(org_state.camera_source),
    }


# ─────────────────────────────────────────────
# Camera source endpoints (IP camera support)
# ─────────────────────────────────────────────

@router.get("/camera/source")
def org_get_camera_source():
    """
    Return the current camera source.
    Response: { "source": "0" }  or  { "source": "http://192.168.1.x:8080/video" }
    """
    with org_state.lock:
        source = org_state.camera_source
    return {"source": str(source)}


@router.post("/camera/source")
async def org_set_camera_source(body: dict):
    """
    Set the camera source.
    If camera was active or auto_start is true, it automatically reconnects immediately.

    Body: { "source": "0" }                          — local webcam index 0
          { "source": "1" }                          — local webcam index 1
          { "source": "http://192.168.1.106:8080/video" }  — Android IP Webcam
          { "source": "http://192.168.1.106:4747/video" }  — DroidCam
          { "source": "rtsp://user:pass@host/stream" }      — RTSP camera
    """
    raw = body.get("source", "").strip()
    if not raw:
        return JSONResponse(status_code=400, content={"error": "source is required"})

    # Parse: if it's a pure integer string, convert to int (webcam index)
    if raw.isdigit():
        new_source: Union[int, str] = int(raw)
    else:
        new_source = raw
        # If user entered an IP address like "192.168.1.100:8080" without http://, prepend http://
        if not (new_source.startswith("http://") or new_source.startswith("https://") or new_source.startswith("rtsp://")):
            if ":" in new_source and not os.path.exists(new_source):
                new_source = f"http://{new_source}"

        # If it is an HTTP/HTTPS stream URL without a video path endpoint, auto-append /video
        if new_source.startswith("http://") or new_source.startswith("https://"):
            url_clean = new_source.rstrip("/")
            url_lower = url_clean.lower()
            if not any(url_lower.endswith(ep) for ep in ("/video", "/videofeed", "/mjpegfeed", ".mjpg", ".mjpeg")):
                new_source = f"{url_clean}/video"

    with org_state.lock:
        was_running = org_state.camera_active
        org_state.camera_source = new_source

    org_state.safe_release_camera()

    # Also update the module-level constant so future starts use the new source
    global CAMERA_SOURCE
    CAMERA_SOURCE = new_source

    # Persist camera source to disk so it survives restarts
    try:
        with open(CAMERA_CONFIG_PATH, "w") as f:
            json.dump({"source": str(new_source)}, f)
    except Exception:
        pass

    # Auto-reconnect ONLY if camera was already running, or if auto_start was explicitly requested as true
    should_auto_start = was_running or body.get("auto_start") is True
    if should_auto_start:
        res = org_start_camera()
        if isinstance(res, JSONResponse):
            return res
        return {
            "status": "ok",
            "source": str(new_source),
            "was_running": was_running,
            "message": f"Camera source updated to {new_source} and reconnected successfully.",
        }

    org_state.log_event("info", f"Camera source updated to: {new_source}")

    # Broadcast updated source to WebSocket clients immediately
    if MAIN_EVENT_LOOP and MAIN_EVENT_LOOP.is_running():
        try:
            asyncio.run_coroutine_threadsafe(_org_broadcast(org_state.get_snapshot()), MAIN_EVENT_LOOP)
        except Exception:
            pass

    return {
        "status": "ok",
        "source": str(new_source),
        "was_running": False,
        "message": f"Camera source set to: {new_source}",
    }


@router.post("/camera/start")
def org_start_camera():
    """Open the camera capture (local webcam or IP camera URL)."""
    with org_state.camera_lock:
        # If camera was previously running or open, cleanly release it first to ensure a fresh connection
        if org_state.cap is not None:
            try:
                org_state.cap.release()
            except Exception:
                pass
            org_state.cap = None
        org_state.camera_active = False

        source = org_state.camera_source

        # Ensure source is normalized if it is a string URL
        if isinstance(source, str) and not source.isdigit():
            # If user entered an IP address like "192.168.1.100:8080" without http://, prepend http://
            if not (source.startswith("http://") or source.startswith("https://") or source.startswith("rtsp://")):
                if ":" in source and not os.path.exists(source):
                    source = f"http://{source}"

            # If it is an HTTP/HTTPS stream URL without a video path endpoint, auto-append /video
            if source.startswith("http://") or source.startswith("https://"):
                url_clean = source.rstrip("/")
                url_lower = url_clean.lower()
                if not any(url_lower.endswith(ep) for ep in ("/video", "/videofeed", "/mjpegfeed", ".mjpg", ".mjpeg")):
                    source = f"{url_clean}/video"

            org_state.camera_source = source

        # For IP/RTSP streams, configure FFmpeg timeouts (8s) so connection attempts don't fail on brief Wi-Fi jitter
        if isinstance(source, str) and (source.startswith("http://") or source.startswith("https://") or source.startswith("rtsp://")):
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;8000000|stimeout;8000000|rtsp_transport;tcp"

        if isinstance(source, int) or (isinstance(source, str) and source.isdigit()):
            cam_idx = int(source)
            cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(cam_idx)
        else:
            cap = cv2.VideoCapture(source)

        if not isinstance(source, str) or not (source.startswith("http://") or source.startswith("https://")):
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            org_state.camera_active = False
            org_state.cap = None
            org_state.log_event("error", f"Failed to open camera source: {source}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "message": (
                        f"Cannot open camera source: {source!r}. "
                        "For local webcam: make sure it is connected. "
                        "For IP camera: check the IP address, ensure phone is on the same network, "
                        "and that the IP Webcam app is running ('Start server')."
                    ),
                },
            )

        org_state.cap = cap
        org_state.camera_active = True
        with org_state.lock:
            org_state.last_jpeg = None

    source_label = f"index {source}" if isinstance(source, int) else f"IP stream {source}"
    org_state.log_event("success", f"Camera connected ({source_label}).")

    # Broadcast immediately so WebSocket clients don't have to wait up to 2 seconds
    if MAIN_EVENT_LOOP and MAIN_EVENT_LOOP.is_running():
        asyncio.run_coroutine_threadsafe(_org_broadcast(org_state.get_snapshot()), MAIN_EVENT_LOOP)

    return {"status": "ok", "message": f"Camera started ({source_label}).", "source": str(source)}


@router.post("/camera/stop")
def org_stop_camera():
    """Release the camera capture."""
    org_state.safe_release_camera()
    with org_state.lock:
        org_state.detected_objects = []
        org_state.surface_boxes = {}
        org_state.last_jpeg = None
        org_state.fps = 0.0

    org_state.log_event("info", "Camera stopped.")

    # Broadcast immediately
    if MAIN_EVENT_LOOP and MAIN_EVENT_LOOP.is_running():
        asyncio.run_coroutine_threadsafe(_org_broadcast(org_state.get_snapshot()), MAIN_EVENT_LOOP)

    return {"status": "ok", "message": "Camera stopped."}


@router.get("/camera/stream")
def org_camera_stream():
    """MJPEG stream — serves annotated frames from the detector thread."""
    HEADER = (
        b"--cortexorgframe\r\n"
        b"Content-Type: image/jpeg\r\n"
        b"\r\n"
    )

    def generate():
        placeholder = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(placeholder, "Waiting for camera...", (120, 180),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (100, 100, 100), 2)
        _, placeholder_buf = cv2.imencode(".jpg", placeholder)
        placeholder_bytes = placeholder_buf.tobytes()
        last_sent: Optional[bytes] = None

        while True:
            with org_state.lock:
                jpeg = org_state.last_jpeg

            if jpeg is None:
                yield HEADER + placeholder_bytes + b"\r\n"
                time.sleep(0.1)
                continue

            if jpeg is not last_sent:
                last_sent = jpeg
                yield HEADER + jpeg + b"\r\n"

            time.sleep(0.015)  # responsive delivery up to 35-40 fps without timer stutter

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=cortexorgframe",
    )


@router.post("/mode")
async def org_set_mode(body: dict):
    """Switch between learn and predict modes."""
    new_mode = body.get("mode", "predict").lower()
    if new_mode not in ("learn", "predict"):
        return JSONResponse(status_code=400, content={"error": "mode must be 'learn' or 'predict'"})

    with org_state.lock:
        org_state.mode = new_mode
        org_state.load_learned_rules()

    org_state.log_event("info", f"Mode switched to: {new_mode.upper()}")

    # Broadcast immediately to all connected clients
    try:
        await _org_broadcast(org_state.get_snapshot())
    except Exception:
        pass

    return {"status": "ok", "mode": new_mode, "learnedRulesCount": len(org_state.learned_rules)}


@router.post("/retrain")
async def org_retrain_model():
    """Trigger personalized model retraining."""
    with org_state.lock:
        if org_state.model_status == "Training":
            return {"status": "already_training", "message": "Training already in progress."}
    org_state.log_event("info", "Manual retraining triggered.")
    _trigger_retrain()
    return {"status": "ok", "message": "Retraining started."}


@router.post("/reset")
def org_reset_learning():
    """Reset to baseline: clear learned rules, disable personalized model."""
    import os as _os
    with org_state.lock:
        org_state.learned_rules = {}
        org_state.new_samples_since_retrain = 0
        org_state.personalized_predictor.disable()
        org_state.predictor = org_state.baseline_predictor

    try:
        with open(LEARNED_RULES_PATH, "w") as f:
            json.dump({}, f)
    except Exception:
        pass

    pers_path = PERSONALIZED_MODEL_PATH
    if pers_path and _os.path.exists(pers_path):
        try:
            _os.remove(pers_path)
        except Exception:
            pass

    org_state.log_event("info", "Learning reset. Baseline model active.")

    # Broadcast immediately to all connected clients
    if MAIN_EVENT_LOOP and MAIN_EVENT_LOOP.is_running():
        try:
            asyncio.run_coroutine_threadsafe(_org_broadcast(org_state.get_snapshot()), MAIN_EVENT_LOOP)
        except Exception:
            pass

    return {"status": "ok", "message": "Learned rules cleared. Baseline model active."}


@router.get("/metrics")
def org_get_metrics():
    """Download the latest organizer metrics JSON."""
    if not os.path.exists(METRICS_PATH):
        return JSONResponse(
            status_code=404,
            content={"error": "metrics.json not found. Run retraining first."},
        )
    return FileResponse(METRICS_PATH, media_type="application/json", filename="organizer_metrics.json")


@router.get("/export/dataset")
def org_export_dataset():
    """Download the usage_data.csv training dataset."""
    if not os.path.exists(USAGE_DATA_PATH):
        return JSONResponse(status_code=404, content={"error": "usage_data.csv not found."})
    return FileResponse(USAGE_DATA_PATH, media_type="text/csv", filename="organizer_dataset.csv")


@router.get("/rules")
def org_get_rules():
    """Return current learned rules."""
    org_state.load_learned_rules()
    return {"rules": org_state.learned_rules, "defaultRules": DEFAULT_RULES}


@router.websocket("/ws")
async def org_websocket_endpoint(websocket: WebSocket):
    """WebSocket — pushes live detection data to connected organizer clients."""
    await websocket.accept()
    org_state.ws_clients.append(websocket)
    org_state.log_event("info", "Organizer dashboard client connected via WebSocket.")

    try:
        await websocket.send_json(org_state.get_snapshot())
        while True:
            await asyncio.sleep(2)
            await websocket.send_json(org_state.get_snapshot())
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        try:
            org_state.ws_clients.remove(websocket)
        except ValueError:
            pass
        org_state.log_event("info", "Organizer dashboard client disconnected.")

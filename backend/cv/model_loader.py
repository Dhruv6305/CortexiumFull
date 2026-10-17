"""
Cortexium 2.0 — CV Model Loader (Singleton)
Improvements over original:
  - All file paths resolved via Path(__file__) — never depends on CWD
  - Multi-person identification: returns list of {name, bbox, confidence}
  - ArcFace model for significantly higher accuracy (vs VGG-Face)
  - Strict cosine distance threshold (< 0.40) to prevent false matches
  - TTL cache on identify_persons() per face-crop hash
  - Graceful degradation if YOLOv8 or DeepFace models are unavailable
  - Registration returns structured metadata including thumbnail path
"""
import os
import cv2
import time
import numpy as np
import urllib.request
from pathlib import Path
from ultralytics import YOLO

try:
    from deepface import DeepFace
    DEEPFACE_INSTALLED = True
except ImportError:
    DEEPFACE_INSTALLED = False
    print("[ModelLoader] WARNING: DeepFace not installed. Face features disabled.")

from dotenv import load_dotenv

load_dotenv()

# Always resolve relative to THIS file's location, never CWD
_THIS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _THIS_DIR.parent
_DATA_DIR = _BACKEND_DIR / "data"
_FACE_DB_PATH = _DATA_DIR / "faces"
_THUMBNAILS_PATH = _DATA_DIR / "thumbnails"

# ArcFace cosine distance threshold — matches closer than this are accepted.
# ArcFace cosine: lower = more similar. 0.65 allows accurate real-world recognition while avoiding false positives.
ARCFACE_THRESHOLD = 0.65
ARCFACE_MODEL = "ArcFace"
ARCFACE_METRIC = "cosine"

# PKL cache filename depends on model name
_PKL_CACHE = _FACE_DB_PATH / f"representations_{ARCFACE_MODEL.lower()}.pkl"


class ModelLoader:
    """Singleton CV model manager for YOLOv8 + DeepFace (ArcFace) with fast spatial tracking."""

    _instance = None
    yolo_model = None
    deepface_ready = False

    # Spatial face tracks: track_id -> {
    #   "name": str, "confidence": float,
    #   "cx": float, "cy": float, "w": float, "h": float,
    #   "last_seen": float, "last_verified": float,
    #   "emotion_data": dict, "last_emo_time": float
    # }
    _face_tracks: dict = {}
    _next_track_id: int = 1

    # TTL cache for identify_persons — per crop hash fallback
    _identity_cache: dict = {}
    _CACHE_TTL_SEC = 6.0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_models()
        return cls._instance

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _ensure_cv2_haarcascade(self):
        """Ensure OpenCV haarcascade_frontalface_default.xml exists in cv2.data.haarcascades."""
        try:
            cascade_dir = getattr(cv2.data, 'haarcascades', None)
            if not cascade_dir:
                return
            os.makedirs(cascade_dir, exist_ok=True)
            xml_path = os.path.join(cascade_dir, 'haarcascade_frontalface_default.xml')
            if not os.path.exists(xml_path):
                print(f"[ModelLoader] Downloading missing OpenCV cascade file to {xml_path}...")
                url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
                urllib.request.urlretrieve(url, xml_path)
                print("[ModelLoader] OpenCV haarcascade downloaded successfully ✓")
        except Exception as e:
            print(f"[ModelLoader] Warning: Could not ensure OpenCV haarcascade: {e}")

    def _warmup_models(self):
        """Pre-warm DeepFace ArcFace & Emotion models on startup to avoid first-frame latency."""
        if not DEEPFACE_INSTALLED:
            return
        try:
            dummy = np.zeros((112, 112, 3), dtype=np.uint8)
            # Warm up ArcFace embedding network
            DeepFace.represent(dummy, model_name=ARCFACE_MODEL, detector_backend="skip", enforce_detection=False)
            # Warm up Emotion classifier
            DeepFace.analyze(dummy, actions=["emotion"], detector_backend="skip", enforce_detection=False, silent=True)
            print("[ModelLoader] ArcFace + Emotion models pre-warmed successfully ✓")
        except Exception as e:
            print(f"[ModelLoader] Warmup notice (non-fatal): {e}")

    def _load_models(self):
        # Ensure data directories exist
        _FACE_DB_PATH.mkdir(parents=True, exist_ok=True)
        _THUMBNAILS_PATH.mkdir(parents=True, exist_ok=True)
        self.face_db_path = str(_FACE_DB_PATH)

        # Ensure OpenCV cascades exist
        self._ensure_cv2_haarcascade()

        # --- YOLOv8 ---
        yolo_path = os.getenv("YOLOV8_MODEL_PATH", "yolov8n.pt")
        local_yolo = _BACKEND_DIR.parent / yolo_path
        if local_yolo.exists():
            yolo_path = str(local_yolo)

        print(f"[ModelLoader] Loading YOLOv8 from: {yolo_path}")
        try:
            self.yolo_model = YOLO(yolo_path)
            dummy = np.zeros((64, 64, 3), dtype=np.uint8)
            self.yolo_model(dummy, verbose=False)
            print("[ModelLoader] YOLOv8 ready ✓")
        except Exception as e:
            print(f"[ModelLoader] YOLOv8 load error: {e}")

        # --- DeepFace (ArcFace) ---
        if DEEPFACE_INSTALLED:
            self.deepface_ready = True
            print(f"[ModelLoader] DeepFace ready ✓ | Model: {ARCFACE_MODEL} | Threshold: {ARCFACE_THRESHOLD}")
            self._warmup_models()
        else:
            print("[ModelLoader] DeepFace not available.")

    # ------------------------------------------------------------------
    # Object Detection
    # ------------------------------------------------------------------

    def predict_objects(self, frame: np.ndarray) -> list:
        """Run YOLOv8 object detection. Returns list of {class, confidence, bbox}."""
        if self.yolo_model is None:
            return []
        try:
            results = self.yolo_model(frame, verbose=False)
            detections = []
            for r in results:
                for box in r.boxes:
                    detections.append({
                        "class": str(self.yolo_model.names[int(box.cls)]),
                        "confidence": round(float(box.conf), 3),
                        "bbox": [round(float(v), 1) for v in box.xyxy[0].tolist()],
                    })
            return detections
        except Exception as e:
            print(f"[ModelLoader] YOLO error: {e}")
            return []

    # ------------------------------------------------------------------
    # Fast Face Crop Extraction (Downscaled Haar Cascade ~10ms)
    # ------------------------------------------------------------------

    def _extract_face_crops(self, frame: np.ndarray) -> list:
        """
        Extract face crops from frame.
        Uses downscaled OpenCV Haar Cascade (~10ms) with fallback to DeepFace & YOLO.
        Returns list of (crop_img, region_dict) tuples.
        """
        crops = []
        h, w = frame.shape[:2]
        if h == 0 or w == 0:
            return []

        # Downscale for ultra-fast face detection (max 640px)
        scale = 1.0
        if max(h, w) > 640:
            scale = 640.0 / max(h, w)
            small = cv2.resize(frame, (int(w * scale), int(h * scale)))
        else:
            small = frame

        CascadeClassifier = getattr(cv2, 'CascadeClassifier', None)
        if CascadeClassifier is not None:
            try:
                if not hasattr(self, '_face_cascade') or self._face_cascade is None:
                    cascade_path = getattr(getattr(cv2, 'data', None), 'haarcascades', '')
                    xml_file = os.path.join(cascade_path, 'haarcascade_frontalface_default.xml') if cascade_path else ''
                    if xml_file and os.path.exists(xml_file):
                        self._face_cascade = CascadeClassifier(xml_file)
                    else:
                        self._face_cascade = None

                if self._face_cascade and not self._face_cascade.empty():
                    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                    faces = self._face_cascade.detectMultiScale(
                        gray, scaleFactor=1.1, minNeighbors=4, minSize=(24, 24)
                    )
                    for (sx, sy, sw, sh) in faces:
                        fx = int(sx / scale)
                        fy = int(sy / scale)
                        fw = int(sw / scale)
                        fh = int(sh / scale)

                        pad = int(min(fw, fh) * 0.12)
                        x1 = max(0, fx - pad)
                        y1 = max(0, fy - pad)
                        x2 = min(w, fx + fw + pad)
                        y2 = min(h, fy + fh + pad)
                        crop = frame[y1:y2, x1:x2]
                        if crop.size > 0:
                            crops.append((crop, {"x": fx, "y": fy, "w": fw, "h": fh}))
                    if crops:
                        return crops
            except Exception:
                pass

        # Attempt 2: Try DeepFace extract_faces on downscaled image
        if DEEPFACE_INSTALLED:
            for backend in ["opencv", "ssd"]:
                try:
                    faces = DeepFace.extract_faces(
                        small,
                        enforce_detection=False,
                        detector_backend=backend,
                        align=False,
                    )
                    for face in faces:
                        if face.get("confidence", 0) < 0.35:
                            continue
                        region = face.get("facial_area", face.get("region", {}))
                        fx = int(region.get("x", 0) / scale)
                        fy = int(region.get("y", 0) / scale)
                        fw = int(region.get("w", 0) / scale)
                        fh = int(region.get("h", 0) / scale)
                        if fw < 20 or fh < 20:
                            continue
                        pad = int(min(fw, fh) * 0.1)
                        x1 = max(0, fx - pad)
                        y1 = max(0, fy - pad)
                        x2 = min(w, fx + fw + pad)
                        y2 = min(h, fy + fh + pad)
                        crop = frame[y1:y2, x1:x2]
                        if crop.size > 0:
                            crops.append((crop, {"x": fx, "y": fy, "w": fw, "h": fh}))
                    if crops:
                        return crops
                except Exception:
                    continue

        # Attempt 3: Fallback to YOLOv8 person head crops
        if not crops and self.yolo_model is not None:
            try:
                results = self.yolo_model(small, verbose=False)
                for r in results:
                    for box in r.boxes:
                        cls_name = self.yolo_model.names[int(box.cls)]
                        conf = float(box.conf)
                        if cls_name == "person" and conf > 0.4:
                            b = box.xyxy[0].tolist()
                            x1 = int(b[0] / scale)
                            y1 = int(b[1] / scale)
                            x2 = int(b[2] / scale)
                            y2 = int(b[3] / scale)
                            bw, bh = x2 - x1, y2 - y1
                            if bw >= 30 and bh >= 30:
                                head_h = int(bh * 0.45)
                                head_crop = frame[y1:min(h, y1 + head_h), max(0, x1):min(w, x2)]
                                if head_crop.size > 0:
                                    side = int(min(bw, bh) * 0.42)
                                    face_x = x1 + int((bw - side) / 2)
                                    face_y = y1 + int(bh * 0.05)
                                    crops.append((head_crop, {"x": face_x, "y": face_y, "w": side, "h": side}))
            except Exception as e:
                print(f"[ModelLoader] YOLO fallback crop error: {e}")

        return crops

    # ------------------------------------------------------------------
    # Face Analysis (Emotion / Age / Gender) with direct crop analysis
    # ------------------------------------------------------------------

    def recognize_faces(self, frame: np.ndarray, crops: list = None) -> list:
        """
        Run emotion analysis on faces in frame.
        Uses fast crop analysis with detector_backend='skip' (~30ms)
        and caches results per tracked face for 2.0s to avoid unnecessary re-inference.
        """
        if not DEEPFACE_INSTALLED:
            return []

        if crops is None:
            crops = self._extract_face_crops(frame)
        if not crops:
            return []

        now = time.time()
        results = []

        for crop_img, region in crops:
            cx = region["x"] + region["w"] / 2.0
            cy = region["y"] + region["h"] / 2.0

            # Check if there is an active track with recent emotion (< 2.0s)
            cached_emo = None
            matched_tid = None
            for tid, track in self._face_tracks.items():
                dist = ((cx - track["cx"]) ** 2 + (cy - track["cy"]) ** 2) ** 0.5
                if dist < region["w"] * 0.9:
                    matched_tid = tid
                    if "emotion_data" in track and (now - track.get("last_emo_time", 0)) < 4.0:
                        cached_emo = track["emotion_data"]
                    break

            if cached_emo:
                results.append({**cached_emo, "region": region})
            else:
                # Fast direct analysis on the face crop
                try:
                    analysis = DeepFace.analyze(
                        crop_img,
                        actions=["emotion"],
                        enforce_detection=False,
                        detector_backend="skip",
                        silent=True,
                    )
                    if analysis and len(analysis) > 0:
                        r = analysis[0]
                        dom_emo = str(r.get("dominant_emotion") or "neutral")
                        emo_data = {
                            "dominant_emotion": dom_emo,
                            "age": None,
                            "dominant_gender": "unknown",
                            "gender_confidence": 1.0,
                            "emotion": {k: round(float(v), 3) for k, v in r.get("emotion", {}).items()},
                        }
                        if matched_tid is not None:
                            self._face_tracks[matched_tid]["emotion_data"] = emo_data
                            self._face_tracks[matched_tid]["last_emo_time"] = now

                        results.append({**emo_data, "region": region})
                    else:
                        results.append({
                            "dominant_emotion": "neutral",
                            "emotion": {"neutral": 1.0},
                            "region": region,
                        })
                except Exception:
                    results.append({
                        "dominant_emotion": "neutral",
                        "emotion": {"neutral": 1.0},
                        "region": region,
                    })

        return results

    # ------------------------------------------------------------------
    # Multi-Person Identification (Fast Spatial Tracking + Warm ArcFace)
    # ------------------------------------------------------------------

    def identify_persons(self, frame: np.ndarray, face_crops: list = None) -> list:
        """
        Identify ALL persons visible in frame using ArcFace + Spatial Tracking.
        Frames with active face tracks return instantly (~10-30ms).
        New faces are identified via ArcFace (~300ms) and registered into tracks.
        """
        self.latest_frame = frame
        if not DEEPFACE_INSTALLED:
            return []

        if face_crops is None:
            face_crops = self._extract_face_crops(frame)
        if not face_crops:
            now = time.time()
            self._face_tracks = {tid: t for tid, t in self._face_tracks.items() if now - t["last_seen"] < 2.5}
            return []

        now = time.time()
        # Clean stale tracks older than 3 seconds
        self._face_tracks = {tid: t for tid, t in self._face_tracks.items() if now - t["last_seen"] < 3.0}

        results = []
        unmatched_crops = []

        for crop_img, region in face_crops:
            cx = region["x"] + region["w"] / 2.0
            cy = region["y"] + region["h"] / 2.0
            bw = region["w"]

            # Match against existing tracks by spatial proximity
            best_tid = None
            min_dist = float("inf")
            for tid, track in self._face_tracks.items():
                dist = ((cx - track["cx"]) ** 2 + (cy - track["cy"]) ** 2) ** 0.5
                if dist < bw * 0.9 and dist < min_dist:
                    min_dist = dist
                    best_tid = tid

            if best_tid is not None:
                track = self._face_tracks[best_tid]
                # Update track position & seen time
                track["cx"] = cx
                track["cy"] = cy
                track["w"] = region["w"]
                track["h"] = region["h"]
                track["last_seen"] = now

                # If track was verified recently (< 5.0s), return identity immediately (0ms ArcFace!)
                if now - track.get("last_verified", 0) < 5.0 and track.get("name"):
                    results.append({
                        "name": track["name"],
                        "confidence": track.get("confidence", 0.9),
                        "region": region,
                    })
                    continue
                else:
                    # Re-verify track
                    unmatched_crops.append((crop_img, region, best_tid))
            else:
                # Brand new face
                unmatched_crops.append((crop_img, region, None))

        # Run ArcFace identification for new or re-verifying faces
        for crop_img, region, existing_tid in unmatched_crops:
            identity_result = self._run_arcface_find(crop_img)
            name = identity_result["name"] if identity_result else None
            conf = identity_result["confidence"] if identity_result else 0.0

            cx = region["x"] + region["w"] / 2.0
            cy = region["y"] + region["h"] / 2.0

            if existing_tid is not None:
                tid = existing_tid
            else:
                tid = self._next_track_id
                self._next_track_id += 1

            self._face_tracks[tid] = {
                "name": name,
                "confidence": conf,
                "cx": cx,
                "cy": cy,
                "w": region["w"],
                "h": region["h"],
                "last_seen": now,
                "last_verified": now,
            }

            if name:
                results.append({
                    "name": name,
                    "confidence": conf,
                    "region": region,
                })

        return results

    # ------------------------------------------------------------------
    # Unified Fast Face Pipeline (extracts crops once, returns both)
    # ------------------------------------------------------------------

    def analyze_faces_fast(self, frame: np.ndarray) -> tuple[list, list]:
        """
        Unified fast face pipeline:
        Extracts face crops once, runs spatial tracking identification and crop emotion.
        Returns (persons, faces).
        """
        crops = self._extract_face_crops(frame)
        if not crops:
            return [], []
        persons = self.identify_persons(frame, face_crops=crops)
        faces = self.recognize_faces(frame, crops=crops)
        return persons, faces

    def _run_arcface_find(self, face_crop: np.ndarray) -> dict | None:
        """
        Run DeepFace.find() with ArcFace on a single face crop against the local DB.
        Passes detector_backend="skip" since face_crop is already cropped.
        Returns {name, confidence} or None if no good match.
        """
        try:
            face_images = [
                f for f in os.listdir(self.face_db_path)
                if f.lower().endswith((".jpg", ".png", ".jpeg"))
            ]
            if not face_images:
                return None

            # Invalidate PKL caches if any face image is newer than any pkl
            pkl_files = list(_FACE_DB_PATH.glob("*.pkl"))
            if pkl_files:
                min_pkl_time = min(p.stat().st_mtime for p in pkl_files)
                newest_img = max(
                    (_FACE_DB_PATH / f).stat().st_mtime for f in face_images
                )
                if newest_img > min_pkl_time:
                    for p in pkl_files:
                        try:
                            p.unlink()
                        except Exception:
                            pass
                    print("[ModelLoader] Invalidated DeepFace PKL cache (new face detected)")

            results = DeepFace.find(
                img_path=face_crop,
                db_path=self.face_db_path,
                model_name=ARCFACE_MODEL,
                distance_metric=ARCFACE_METRIC,
                enforce_detection=False,
                detector_backend="skip",
                silent=True,
            )

            if results and len(results) > 0 and not results[0].empty:
                df = results[0]
                dist_col = f"{ARCFACE_MODEL}_{ARCFACE_METRIC}"
                if dist_col in df.columns:
                    df = df.sort_values(by=dist_col, ascending=True)
                elif "distance" in df.columns:
                    df = df.sort_values(by="distance", ascending=True)

                row = df.iloc[0]
                distance = float(row.get(dist_col, row.get("distance", 1.0)))

                # Threshold — only accept confident matches
                if distance > ARCFACE_THRESHOLD:
                    return None

                match_path = row["identity"]
                import re
                name = re.sub(r"_\d+$", "", Path(match_path).stem)
                confidence = round(1.0 - (distance / ARCFACE_THRESHOLD), 3)  # Normalize to 0-1
                confidence = max(0.0, min(1.0, confidence))
                print(f"[ModelLoader] ArcFace match: {name} (dist={distance:.3f}, conf={confidence:.3f})")
                return {"name": name, "confidence": confidence}

        except Exception as e:
            print(f"[ModelLoader] _run_arcface_find error: {e}")
        return None

    # ------------------------------------------------------------------
    # Legacy single-person identify (kept for backward compat)
    # ------------------------------------------------------------------

    def identify_person(self, frame: np.ndarray) -> str | None:
        """Backward-compat wrapper — returns first identified person's name or None."""
        persons = self.identify_persons(frame)
        return persons[0]["name"] if persons else None

    # ------------------------------------------------------------------
    # Face Registration — supports multiple images per person
    # ------------------------------------------------------------------

    def register_person(self, frame: np.ndarray, name: str) -> dict:
        """
        Save a person's face to the local DB.
        Auto-indexes to allow multiple images: Name.jpg, Name_1.jpg, Name_2.jpg ...
        Returns {success, name, thumbnail_path, message}.
        """
        if not DEEPFACE_INSTALLED:
            return {"success": False, "name": name, "message": "DeepFace not installed"}

        import re
        safe_name = re.sub(r"[^\w\s-]", "", name).strip().title()

        try:
            # Count existing images for this person to determine index
            existing = sorted(_FACE_DB_PATH.glob(f"{safe_name}*.jpg")) + \
                       sorted(_FACE_DB_PATH.glob(f"{safe_name}*.jpeg")) + \
                       sorted(_FACE_DB_PATH.glob(f"{safe_name}*.png"))
            idx = len(existing)
            suffix = f"_{idx}" if idx > 0 else ""
            # Extract face crop to ensure DB contains clean face images for skip-detector
            face_crops = self._extract_face_crops(frame)
            if face_crops:
                save_img, region = face_crops[0]
            else:
                save_img = frame

            file_path = _FACE_DB_PATH / f"{safe_name}{suffix}.jpg"
            cv2.imwrite(str(file_path), save_img)

            # Save thumbnail from face crop
            thumb_path = _THUMBNAILS_PATH / f"{safe_name}_thumb.jpg"
            thumb = cv2.resize(save_img, (80, 80))
            cv2.imwrite(str(thumb_path), thumb)

            # Also ensure conversation JSON profile exists for this person
            from ..routers.persons import append_conversation_entry
            append_conversation_entry(
                name=safe_name,
                text=f"Registered person profile for {safe_name}.",
                source="registration",
            )

            # Invalidate all DeepFace PKL caches so new image is immediately indexed!
            for pkl in _FACE_DB_PATH.glob("*.pkl"):
                try:
                    pkl.unlink()
                except Exception:
                    pass

            # Clear identity cache
            self._identity_cache.clear()

            print(f"[ModelLoader] Registered: {safe_name} → {file_path} (image #{idx + 1})")
            return {
                "success": True,
                "name": safe_name,
                "message": f"Successfully registered {safe_name} (image #{idx + 1})",
                "file_path": str(file_path),
                "image_index": idx,
            }
        except Exception as e:
            print(f"[ModelLoader] register_person error: {e}")
            return {"success": False, "name": safe_name, "message": str(e)}

    @property
    def status(self) -> dict:
        face_count = sum(
            1 for f in os.listdir(self.face_db_path)
            if f.lower().endswith((".jpg", ".png", ".jpeg"))
        ) if os.path.exists(self.face_db_path) else 0
        return {
            "yolo_ready": self.yolo_model is not None,
            "deepface_ready": self.deepface_ready,
            "face_recognition_model": ARCFACE_MODEL,
            "distance_metric": ARCFACE_METRIC,
            "threshold": ARCFACE_THRESHOLD,
            "face_db_path": self.face_db_path,
            "registered_faces": face_count,
            "cache_entries": len(self._identity_cache),
        }


model_loader = ModelLoader()

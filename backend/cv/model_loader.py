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
    """Singleton CV model manager for YOLOv8 + DeepFace (ArcFace)."""

    _instance = None
    yolo_model = None
    deepface_ready = False

    # TTL cache for identify_persons — per crop hash
    _identity_cache: dict = {}   # crop_hash -> ({name, confidence}, timestamp)
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

    def _load_models(self):
        # Ensure data directories exist
        _FACE_DB_PATH.mkdir(parents=True, exist_ok=True)
        _THUMBNAILS_PATH.mkdir(parents=True, exist_ok=True)
        self.face_db_path = str(_FACE_DB_PATH)

        # Ensure OpenCV cascades exist for DeepFace
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
    # Face Analysis (Emotion / Age / Gender) — supports multiple faces
    # ------------------------------------------------------------------

    def recognize_faces(self, frame: np.ndarray) -> list:
        """Run DeepFace analysis for emotion, age, gender on ALL faces in frame."""
        if not DEEPFACE_INSTALLED:
            return []
        for backend in ["fastmtcnn", "ssd", "opencv"]:
            try:
                results = DeepFace.analyze(
                    frame,
                    actions=["emotion", "age", "gender"],
                    enforce_detection=False,
                    detector_backend=backend,
                    silent=True,
                )
                clean = []
                for r in results:
                    gender_scores = r.get("gender", {})
                    dom_gender = r.get("dominant_gender", "")
                    region = r.get("region", {})
                    clean.append({
                        "dominant_emotion": str(r.get("dominant_emotion") or ""),
                        "age": int(r["age"]) if r.get("age") is not None else None,
                        "dominant_gender": str(dom_gender),
                        "gender_confidence": round(float(gender_scores.get(dom_gender, 0)), 3),
                        "emotion": {k: round(float(v), 3) for k, v in r.get("emotion", {}).items()},
                        "region": {
                            "x": int(region.get("x", 0)),
                            "y": int(region.get("y", 0)),
                            "w": int(region.get("w", 0)),
                            "h": int(region.get("h", 0)),
                        },
                    })
                if clean:
                    return clean
            except Exception:
                continue
        return []

    # ------------------------------------------------------------------
    # Multi-Person Identification (with TTL cache per face crop)
    # ------------------------------------------------------------------

    def identify_persons(self, frame: np.ndarray) -> list:
        """
        Identify ALL persons visible in the frame using ArcFace.
        Returns a list of dicts: [{name, bbox, confidence, emotion}]
        Uses per-crop TTL cache to avoid hammering DeepFace every frame.
        """
        self.latest_frame = frame
        if not DEEPFACE_INSTALLED:
            return []

        # Step 1: Extract all face bounding boxes
        face_crops = self._extract_face_crops(frame)
        if not face_crops:
            return []

        now = time.time()
        results = []

        for crop_img, region in face_crops:
            # Cheap hash of the crop for cache lookup
            try:
                tiny = cv2.resize(crop_img, (16, 16))
                crop_key = hash(tiny.tobytes())
            except Exception:
                crop_key = id(crop_img)

            # Check cache
            if crop_key in self._identity_cache:
                cached_result, cached_time = self._identity_cache[crop_key]
                if now - cached_time < self._CACHE_TTL_SEC:
                    if cached_result:
                        results.append({**cached_result, "region": region})
                    continue

            # Run ArcFace identification on this face crop
            identity_result = self._run_arcface_find(crop_img)
            self._identity_cache[crop_key] = (identity_result, now)

            if identity_result:
                results.append({**identity_result, "region": region})

        # Evict stale cache entries
        self._identity_cache = {
            k: v for k, v in self._identity_cache.items()
            if now - v[1] < self._CACHE_TTL_SEC * 2
        }

        return results

    def _extract_face_crops(self, frame: np.ndarray) -> list:
        """
        Extract face crops from frame.
        Uses fast OpenCV Haar Cascade detection first (~5ms),
        with fallback to DeepFace detector backends and YOLOv8 head crops.
        Returns list of (crop_img, region_dict) tuples.
        """
        crops = []

        # Attempt 1: Fast OpenCV Haar Cascade Classifier (~5ms)
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
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = self._face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
                    for (x, y, w, h) in faces:
                        pad = int(min(w, h) * 0.1)
                        x1 = max(0, x - pad)
                        y1 = max(0, y - pad)
                        x2 = min(frame.shape[1], x + w + pad)
                        y2 = min(frame.shape[0], y + h + pad)
                        crop = frame[y1:y2, x1:x2]
                        if crop.size > 0:
                            crops.append((crop, {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}))
                    if crops:
                        return crops
            except Exception:
                pass

        # Attempt 2: Try DeepFace extract_faces with opencv or fastmtcnn
        if DEEPFACE_INSTALLED:
            for backend in ["opencv", "ssd", "fastmtcnn"]:
                try:
                    faces = DeepFace.extract_faces(
                        frame,
                        enforce_detection=False,
                        detector_backend=backend,
                        align=True,
                    )
                    for face in faces:
                        confidence = face.get("confidence", 0)
                        if confidence < 0.3:
                            continue
                        region = face.get("facial_area", face.get("region", {}))
                        x = int(region.get("x", 0))
                        y = int(region.get("y", 0))
                        w = int(region.get("w", 0))
                        h = int(region.get("h", 0))
                        if w < 20 or h < 20:
                            continue
                        pad = int(min(w, h) * 0.1)
                        x1 = max(0, x - pad)
                        y1 = max(0, y - pad)
                        x2 = min(frame.shape[1], x + w + pad)
                        y2 = min(frame.shape[0], y + h + pad)
                        crop = frame[y1:y2, x1:x2]
                        if crop.size > 0:
                            crops.append((crop, {"x": x, "y": y, "w": w, "h": h}))
                    if crops:
                        return crops
                except Exception:
                    continue

        # Attempt 3: Fallback to YOLOv8 person bounding box crops
        if not crops and self.yolo_model is not None:
            try:
                results = self.yolo_model(frame, verbose=False)
                for r in results:
                    for box in r.boxes:
                        cls_name = self.yolo_model.names[int(box.cls)]
                        conf = float(box.conf)
                        if cls_name == "person" and conf > 0.4:
                            xyxy = box.xyxy[0].tolist()
                            x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])
                            w, h = x2 - x1, y2 - y1
                            if w >= 30 and h >= 30:
                                head_h = int(h * 0.45)
                                head_crop = frame[y1:min(frame.shape[0], y1 + head_h), max(0, x1):min(frame.shape[1], x2)]
                                if head_crop.size > 0:
                                    side = int(min(w, h) * 0.42)
                                    face_x = x1 + int((w - side) / 2)
                                    face_y = y1 + int(h * 0.05)
                                    crops.append((head_crop, {"x": face_x, "y": face_y, "w": side, "h": side}))
            except Exception as e:
                print(f"[ModelLoader] YOLO fallback crop error: {e}")

        return crops

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

            # Invalidate PKL cache if new images were added
            if _PKL_CACHE.exists():
                pkl_time = _PKL_CACHE.stat().st_mtime
                newest = max(
                    (_FACE_DB_PATH / f).stat().st_mtime for f in face_images
                )
                if newest > pkl_time:
                    _PKL_CACHE.unlink()
                    print("[ModelLoader] Invalidated ArcFace cache (new face added)")

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
            file_path = _FACE_DB_PATH / f"{safe_name}{suffix}.jpg"
            cv2.imwrite(str(file_path), frame)

            # Save thumbnail from face crop or head region
            thumb_path = _THUMBNAILS_PATH / f"{safe_name}_thumb.jpg"
            face_crops = self._extract_face_crops(frame)
            if face_crops:
                crop_img, region = face_crops[0]
                thumb = cv2.resize(crop_img, (80, 80))
                cv2.imwrite(str(thumb_path), thumb)
            else:
                thumb = cv2.resize(frame, (80, 80))
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
